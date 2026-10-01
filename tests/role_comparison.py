import json
import unittest
from datetime import datetime, timezone, timedelta
import importlib.util, tempfile, sys, atexit
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packaging_cli',ROOT/'meshcrap.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
workspace=tempfile.TemporaryDirectory(prefix='role-comparison-');atexit.register(workspace.cleanup)
settings=json.loads((ROOT/'config.example.json').read_text());settings['data_dir']=str(Path(workspace.name)/'data');settings['receiver_id']='!12345678'
config=Path(workspace.name)/'config.json';config.write_text(json.dumps(settings))
settings,data=cli.load_config(config);runtime=cli.initialize(settings,data)
sys.path[:0]=[str(runtime),str(runtime/'dashboard')]
from role_compare import analyze, HQ, HQ_ID

class RoleTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,30,12,tzinfo=timezone.utc)
        self.profile={'favorites':[123]}

    def row(self, **kw):
        r=dict(collector_time=(self.now-timedelta(minutes=30)).isoformat(),from_num=456,
               to_num=0xffffffff,packet_id=99,hop_limit=3,portnum='TEXT_MESSAGE_APP',
               rx_snr=0.0,rx_rssi=-110,transport='TRANSPORT_LORA',
               raw_json=json.dumps({'_collectorReceiverId':HQ_ID}),
               channel_utilization=None,air_util_tx=None)
        r.update(kw);return r

    def run_rows(self,rows,profile=True):
        return analyze(rows,{456:'Example'},self.profile if profile else None,self.now,1)

    def test_favorites_and_unknown_profile(self):
        rows=[self.row(),self.row(from_num=123)]
        d=self.run_rows(rows)
        self.assertEqual(d['totals']['affected'],1)
        self.assertEqual(d['totals']['favorites'],1)
        self.assertNotIn('affected',self.run_rows(rows,False)['totals'])

    def test_dedupe_is_sender_scoped(self):
        d=self.run_rows([self.row(),self.row(),self.row(from_num=789)])
        self.assertEqual(d['totals']['affected'],2)
        self.assertEqual(d['totals']['duplicates'],1)

    def test_hops_unicast_and_diagnostics(self):
        cases=[('exhausted',dict(hop_limit=0)),('unknown_hops',dict(hop_limit=None)),
               ('non_broadcast',dict(to_num=12)),('diagnostic',dict(portnum='ADMIN_APP'))]
        for key,change in cases:
            d=self.run_rows([self.row(**change)])
            self.assertEqual(d['totals'][key],1)
            self.assertNotIn('affected',d['totals'])

    def test_mqtt_internal_other_receiver_and_rf_evidence(self):
        cases=[dict(transport='TRANSPORT_MQTT'),dict(transport='TRANSPORT_INTERNAL'),
               dict(raw_json=json.dumps({'_collectorReceiverId':HQ_ID,'viaMqtt':True})),
               dict(raw_json=json.dumps({'_collectorReceiverId':'!abcdef01'})),
               dict(raw_json='{}'),dict(rx_snr=None,rx_rssi=None)]
        for change in cases:
            self.assertNotIn('affected',self.run_rows([self.row(**change)])['totals'])

    def test_zero_snr_is_valid_and_own_telemetry_not_forwarded(self):
        d=self.run_rows([self.row(),self.row(from_num=HQ,channel_utilization=0,air_util_tx=.2)])
        self.assertEqual(d['totals']['affected'],1)
        self.assertEqual(d['bins'][0]['channel_max'],0)
        self.assertEqual(d['bins'][0]['tx_max'],.2)

    def test_empty_window_and_outside_window(self):
        d=self.run_rows([self.row(collector_time=(self.now-timedelta(hours=2)).isoformat())])
        self.assertEqual(d['totals'],{})
        self.assertIsNone(d['bins'][0]['channel_max'])

    def test_read_only_profile_dispatch(self):
        # Compile only Control to exercise the new branch with real protobuf config.
        import ast, threading
        from pathlib import Path
        from types import SimpleNamespace
        from google.protobuf.json_format import MessageToDict
        from meshtastic.protobuf import config_pb2, mesh_pb2
        tree=ast.parse((runtime/'node_control_bridge.py').read_text())
        klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Control')
        env={'MessageToDict':MessageToDict,'time':__import__('time')}
        exec(compile(ast.Module(body=[klass],type_ignores=[]),'Control','exec'),env)
        cfg=config_pb2.LocalConfig() if hasattr(config_pb2,'LocalConfig') else None
        from meshtastic.protobuf import localonly_pb2
        cfg=localonly_pb2.LocalConfig()
        cfg.device.role=config_pb2.Config.DeviceConfig.CLIENT_BASE
        iface=SimpleNamespace(localNode=SimpleNamespace(nodeNum=HQ,localConfig=cfg),
            metadata=mesh_pb2.DeviceMetadata(firmware_version='2.8.0.test'),
            nodesByNum={123:{'isFavorite':True},456:{}})
        obj=env['Control'].__new__(env['Control']);obj.lock=threading.Lock();obj.iface=lambda:iface
        d=obj.dispatch({'action':'role_profile'})
        self.assertEqual(d['favorites'],[123])
        self.assertEqual(d['device']['role'],'CLIENT_BASE')
        # Fake interface provides no send/get-radio methods: only memory can be read.

if __name__=='__main__':unittest.main()
