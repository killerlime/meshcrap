"""Synthetic dual-receiver matching, bootstrap exclusion and control isolation."""
import importlib.util
import json
import math
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import meshcrap


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReceiverComparisonTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        config = json.loads((ROOT/'config.example.json').read_text())
        config.update(data_dir=str(self.base/'data'), receiver_id='!12345678', radio_host='192.0.2.10',
                      secondary_enabled=True, secondary_receiver_id='!23456789',
                      secondary_radio_host='192.0.2.11')
        path = self.base/'config.json'
        path.write_text(json.dumps(config))
        settings, self.data = meshcrap.load_config(path)
        runtime = meshcrap.initialize(settings, self.data)
        sys.path[:0] = [str(runtime), str(runtime/'dashboard')]
        self.addCleanup(lambda: sys.path.__delitem__(slice(0, 2)))
        self.provenance = load('comparison_provenance', runtime/'receiver_provenance.py')
        self.comparison = load('comparison_module', runtime/'dashboard/receiver_comparison.py')
        self.store = load('comparison_storage', runtime/'secondary_storage.py')
        self.store.BASE_DIR.mkdir(mode=0o700, exist_ok=True)
        self.store.db = self.store.open_database()
        self.addCleanup(self.store.db.close)
        self.primary_id = config['receiver_id']
        self.secondary_id = config['secondary_receiver_id']
        self.runtime = runtime

    def packet(self, at, sender=0x34567890, packet_id=1, payload='hello', hops=0, snr=0, channel=0):
        return dict(at=at, collector_time=self.comparison.iso(at), rx_time=int(at), from_num=sender,
                    packet_id=packet_id, to_num=0xffffffff, portnum='TEXT_MESSAGE_APP',
                    hops_used=hops, rx_snr=snr, rx_rssi=-100, channel=channel,
                    raw={'decoded': {'payload': payload}})

    def test_timestamp_provenance_is_conservative(self):
        classify = self.provenance.observation_type
        self.assertEqual(classify({'rxTime': 100}, 105, 110), 'LIVE')
        self.assertEqual(classify({'rxTime': 99}, 105, 110), 'BUFFERED')
        self.assertEqual(classify({'rxTime': 171}, 105, 110), 'CLOCK_SKEW')
        for value in (None, 0, -1, True, '100', float('nan'), float('inf')):
            self.assertEqual(classify({'rxTime': value}, 105, 110), 'UNDATED')

    def test_snapshot_is_metadata_not_rf(self):
        iface = SimpleNamespace(nodes={'!34567890': dict(num=0x34567890,
                    user=dict(id='!34567890', longName='Example mobile', hwModel='UNSET'), lastHeard=10)})
        self.store.snapshot_nodes(iface)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM nodes').fetchone()[0], 1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM packets').fetchone()[0], 0)

    def test_matching_uses_payload_sender_destination_not_local_slot(self):
        left, right = self.packet(100), self.packet(101, channel=7)
        self.assertEqual(self.comparison.packet_key(left), self.comparison.packet_key(right))
        for field, value in (('packet_id', 2), ('from_num', 0x45678901), ('to_num', 0x45678901)):
            changed = dict(right, **{field: value})
            self.assertNotEqual(self.comparison.packet_key(left), self.comparison.packet_key(changed))
        self.assertNotEqual(self.comparison.packet_key(left), self.comparison.packet_key(self.packet(101, payload='different')))
        for field, value in (('packet_id', 0), ('packet_id', None), ('from_num', 0xffffffff), ('to_num', None)):
            self.assertIsNone(self.comparison.packet_key(dict(left, **{field:value})))

    def test_duplicate_episodes_and_two_minute_window(self):
        left = [self.packet(100), self.packet(102), self.packet(300)]
        right = [self.packet(101)]
        result = self.comparison.compare(left, right, [(90, 400)], 90, 400)
        self.assertEqual(result['packets'], dict(both=1, primary_only=1, secondary_only=0))
        self.assertEqual(result['primary']['observations'], 3)
        self.assertEqual(result['signal']['direct_both']['snr_median_secondary_minus_primary'], 0)

    def test_linear_nearest_pair_matches_bruteforce(self):
        left = [self.packet(i*.9) for i in range(2000)]
        right = [self.packet(i*.95+.1) for i in range(2000)]
        a,b = self.comparison.closest_pair(left, right)
        self.assertAlmostEqual(abs(a['at']-b['at']), min(abs(a['at']-b['at']) for a in left[:30] for b in right[:30]), places=6)

    def test_direct_relayed_mixed_unknown_are_separate(self):
        left = [self.packet(100+i, packet_id=i+1, hops=h) for i,h in enumerate((0,1,0,-1))]
        right = [self.packet(100+i, packet_id=i+1, hops=h, snr=3) for i,h in enumerate((0,2,1,-1))]
        result = self.comparison.compare(left,right,[(90,200)],90,200)
        for key in ('direct_both','relayed_both','mixed','unknown'):
            self.assertEqual(result['signal'][key]['packets'], 1)

    def test_missing_payload_counts_as_unmatchable(self):
        row = self.packet(100);row['raw']={}
        result = self.comparison.compare([row],[],[(90,200)],90,200)
        self.assertEqual(result['unmatchable_observations'],1)
        self.assertEqual(result['packets']['primary_only'],0)

    def test_overlap_excludes_gaps_and_partial_correlation_bins(self):
        common = self.comparison.overlap([(0,100),(200,500)],[(50,300),(400,600)])
        self.assertEqual(common,[(50,100),(200,300),(400,500)])
        result = self.comparison.correlations([],[],[(30,750),(900,2100)],0,2100,300)
        self.assertEqual(result['complete_bins'],5)
        self.assertIsNone(result['packet_count_pearson'])

    def test_correlation_needs_twelve_varying_complete_bins(self):
        rows=[self.packet(i*300+10, packet_id=i+1) for i in range(0,12,2)]
        result=self.comparison.correlations(rows,rows,[(0,3600)],0,3600,300)
        self.assertEqual(result['packet_count_pearson'],1)
        self.assertIsNone(self.comparison.correlations(rows,rows,[(0,3300)],0,3300,300)['packet_count_pearson'])

    def test_status_identity_age_and_profile_secrets(self):
        path=self.data/'secondary/status.json'
        status=dict(receiver_id=self.secondary_id,connected=True,heartbeat=self.comparison.iso(100),
                    profile=dict(lora={'region':'US','psk':'must never leak'},channels=[dict(index=0,name='Example',enabled=True,psk='secret')]))
        path.write_text(json.dumps(status))
        result=self.comparison.read_status(self.data,110,self.secondary_id,True)
        self.assertTrue(result['connected']);self.assertNotIn('psk',json.dumps(result))
        self.assertFalse(self.comparison.read_status(self.data,126,self.secondary_id,True)['connected'])
        self.assertFalse(self.comparison.read_status(self.data,110,self.primary_id,True)['connected'])

    def test_session_coverage_stops_at_last_heartbeat(self):
        db=self.store.db;db.row_factory=sqlite3.Row
        db.execute('INSERT INTO collection_sessions(started_at,profile_json) VALUES (?,?)',(self.comparison.iso(10),'{}'));db.commit()
        intervals=self.comparison.secondary_intervals(db,{'heartbeat':self.comparison.iso(50)},0,100)
        self.assertEqual(intervals,[(10,50)])

    def test_rf_filters_preserve_only_verified_live_external_observations(self):
        iface=SimpleNamespace(localNode=SimpleNamespace(nodeNum=int(self.secondary_id[1:],16)))
        for index, (provenance, transport, sender, raw_update) in enumerate([
            ('LIVE','TRANSPORT_LORA',0x34567890,{}),
            ('BUFFERED','TRANSPORT_LORA',0x34567890,{}),
            ('UNDATED','TRANSPORT_LORA',0x34567890,{}),
            ('CLOCK_SKEW','TRANSPORT_LORA',0x34567890,{}),
            ('LIVE','TRANSPORT_MQTT',0x34567890,{}),
            ('LIVE','TRANSPORT_INTERNAL',0x34567890,{}),
            ('LIVE','TRANSPORT_LORA',int(self.secondary_id[1:],16),{}),
            ('LIVE','TRANSPORT_LORA',0x34567890,{'viaMqtt':True}),
            ('LIVE','TRANSPORT_LORA',0x34567890,{'rxTime':10}),
        ]):
            packet=dict(id=index+1,rxTime=110,**{'from':sender},to=0xffffffff,rxSnr=0,rxRssi=-100,
                        transportMechanism=transport,_collectorObservationType=provenance,
                        decoded=dict(portnum='NODEINFO_APP',payload=b'example',user=dict(id='!34567890',longName='Fresh RF node')))
            packet.update(raw_update)
            self.store.on_receive(packet,iface)
        # Retained rows stay auditable; synthetic arrival belongs to a session at epoch100.
        self.store.db.execute('UPDATE packets SET collector_time=?',(self.comparison.iso(115),));self.store.db.commit()
        self.store.db.row_factory=sqlite3.Row
        rows,truncated=self.comparison.load_packets(self.store.db,self.secondary_id,100,120,[(100,120)])
        self.assertEqual(len(rows),1);self.assertFalse(truncated)
        self.assertNotIn('raw',rows[0]);self.assertNotIn('raw_json',rows[0])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM packets').fetchone()[0],9)
        self.assertEqual(self.store.db.execute('PRAGMA quick_check').fetchone()[0],'ok')

    def test_disabled_comparison_has_no_files_sockets_or_database_reads(self):
        result=self.comparison.Comparison(self.data,self.data/'mesh.db',self.primary_id,self.secondary_id)
        with patch('sqlite3.connect',side_effect=AssertionError('No DB reads')),patch('socket.socket',side_effect=AssertionError('No sockets')):
            self.assertFalse(result.build(24)['enabled'])
        for hours in range(1,20):result.build(hours)
        self.assertEqual(len(result.cache),4)

    def test_api_windows_and_read_only_contract(self):
        from flask import Flask
        app=Flask(__name__)
        self.comparison.register_receiver_comparison(app,self.data/'mesh.db')
        client=app.test_client()
        for hours in (1,2,3,4,8,12,24,48,168,336,720):
            response=client.get('/api/receiver-comparison?hours='+str(hours))
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
        for hours in ('0','721','nan','1.5'):
            self.assertEqual(client.get('/api/receiver-comparison?hours='+hours).status_code,400)
        self.assertEqual(client.post('/api/receiver-comparison').status_code,405)

    def test_enabled_build_reads_only_separate_databases_and_matches_live_rf(self):
        now=time.time();start=now-1200;at=int(now-50)
        profile=dict(lora=dict(use_preset=True,modem_preset='MEDIUM_FAST',region='US',override_frequency=0,
                              frequency_offset=0,channel_num=20),channels=[])
        for path,identity in ((self.data/'receiver-status.json',self.primary_id),(self.data/'secondary/status.json',self.secondary_id)):
            path.write_text(json.dumps(dict(receiver_id=identity,connected=True,heartbeat=self.comparison.iso(now),profile=profile)))
        with sqlite3.connect(self.data/'mesh.db') as conn:
            conn.executemany('INSERT INTO collector_events(event_time,event_type,message) VALUES (?,?,?)',
                [(self.comparison.iso(start-1),'CONNECTED','Synthetic connection'),
                 (self.comparison.iso(start),'NODE_SNAPSHOT','Metadata snapshot')])
            raw=json.dumps(dict(_collectorReceiverId=self.primary_id,_collectorObservationType='LIVE',decoded=dict(payload='same')))
            conn.execute('INSERT INTO packets(collector_time,rx_time,packet_id,from_num,to_num,portnum,rx_snr,rx_rssi,hops_used,transport,raw_json,observation_type) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (self.comparison.iso(at),at,123,0x34567890,0xffffffff,'TEXT_MESSAGE_APP',0,-100,0,'TRANSPORT_LORA',raw,'LIVE'))
        self.store.db.execute('INSERT INTO collection_sessions(started_at,profile_json) VALUES (?,?)',(self.comparison.iso(start),json.dumps(profile)))
        raw=json.dumps(dict(_collectorReceiverId=self.secondary_id,_collectorObservationType='LIVE',decoded=dict(payload='same')))
        self.store.db.execute('INSERT INTO packets(collector_time,rx_time,packet_id,from_num,to_num,portnum,rx_snr,rx_rssi,hops_used,transport,raw_json,observation_type) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (self.comparison.iso(at+1),at+1,123,0x34567890,0xffffffff,'TEXT_MESSAGE_APP',2,-98,0,'TRANSPORT_LORA',raw,'LIVE'))
        self.store.db.commit()
        service=self.comparison.Comparison(self.data,self.data/'mesh.db',self.primary_id,self.secondary_id,enabled=True)
        with patch('socket.socket',side_effect=AssertionError('Comparison must not contact radios')):
            result=service.build(24)
        self.assertEqual(result['comparison']['packets']['both'],1)
        self.assertEqual(result['comparison']['signal']['direct_both']['snr_median_secondary_minus_primary'],2)
        self.assertTrue(result['compatibility']['verified']);self.assertNotIn('"payload":',json.dumps(result))

    def secondary(self):
        with patch.dict(sys.modules,secondary_storage=self.store):
            return load('synthetic_secondary',self.runtime/'secondary_collector.py')

    def test_secondary_ignores_unready_other_interface_and_wrong_identity(self):
        module=self.secondary();iface=SimpleNamespace(localNode=SimpleNamespace(nodeNum=module.EXPECTED))
        module.radio=iface
        with patch.object(self.store,'on_receive') as save:
            module.receive({'rxTime':110},iface);save.assert_not_called()
            module.ready=True
            module.receive({'rxTime':110},SimpleNamespace(localNode=SimpleNamespace(nodeNum=module.EXPECTED)));save.assert_not_called()
            iface.localNode.nodeNum=module.EXPECTED+1
            module.receive({'rxTime':110},iface);save.assert_not_called()
            self.assertIsNone(module.current())

    def test_secondary_disabled_does_not_open_connection(self):
        module=self.secondary();module.ENABLED=False
        with patch.object(module,'RecoveringInterface',side_effect=AssertionError('No connection')):
            with self.assertRaises(SystemExit) as error:module.main()
        self.assertEqual(error.exception.code,78)

    def test_secondary_wrong_identity_stops_without_retry_and_closes(self):
        module=self.secondary();module.CONTROLS=False
        candidate=SimpleNamespace(localNode=SimpleNamespace(nodeNum=module.EXPECTED+1),
                                  isConnected=threading.Event(),connect=Mock(),close=Mock())
        candidate.isConnected.set()
        with (patch.object(module,'RecoveringInterface',return_value=candidate) as opening,
              patch.object(module.pub,'subscribe'),patch.object(module.pub,'unsubscribe')):
            with self.assertRaises(SystemExit) as error:module.main()
        self.assertEqual(error.exception.code,78);self.assertEqual(opening.call_count,1);candidate.close.assert_called_once()

    def test_secondary_closes_even_if_status_write_fails(self):
        module=self.secondary();module.radio=SimpleNamespace(close=Mock());old=module.radio
        with patch.object(module,'publish_status',side_effect=OSError('Synthetic disk failure')):
            with self.assertRaises(OSError):module.disconnect()
        old.close.assert_called_once();self.assertIsNone(module.current())

    def test_secondary_send_history_and_feed_are_isolated(self):
        import node_control_bridge,sent_messages,mf_feed
        iface=SimpleNamespace(localNode=SimpleNamespace(nodeNum=0x23456789,channels=[SimpleNamespace(role=1)]),
                              nodes={},isConnected=threading.Event(),sendText=Mock(return_value=SimpleNamespace(id=42,channel=0,to=0xffffffff)))
        iface.isConnected.set()
        control=node_control_bridge.Control(lambda:iface,lambda *a:None,base_dir=self.store.BASE_DIR,feed_enabled=False,expected_receiver_id=0x23456789)
        with patch.object(control,'section'),patch.object(mf_feed,'capture_sent_text',side_effect=AssertionError('No feed')):
            request=dict(action='send',text='Synthetic test',channel=0,request_id='example-request-000001')
            control.dispatch(request);control.dispatch(request)
        iface.sendText.assert_called_once()
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM web_sent_messages').fetchone()[0],1)
        self.assertFalse(self.store.db.execute('SELECT count(*) FROM packets').fetchone()[0])
        control.expected_receiver_id=0x12345678
        with self.assertRaisesRegex(ValueError,'identity'):control.iface()

    def test_web_control_gates_keep_existing_origin_and_unlock_protection(self):
        application=load('comparison_dashboard',self.runtime/'dashboard/app.py').app
        application.config['TESTING']=True
        client=application.test_client()
        body=dict(action='state')
        self.assertEqual(client.post('/api/secondary-control/action',json=body,
                                    headers={'Origin':'http://localhost'},base_url='http://localhost').status_code,403)
        application.config['SECONDARY_CONTROLS_ENABLED']=True
        application.config['RADIO_CONTROLS_ENABLED']=True
        self.assertEqual(client.post('/api/secondary-control/action',json=body,base_url='http://localhost').status_code,403)
        self.assertEqual(client.post('/api/secondary-control/action',json=body,
                                    headers={'Origin':'http://localhost'},base_url='http://localhost').status_code,401)
        with client.session_transaction() as session:session['radio_until']=time.time()+3600
        import secondary_control_connection
        with patch.object(secondary_control_connection,'dispatch',return_value={'node_id':self.secondary_id}) as dispatch:
            response=client.post('/api/secondary-control/action',json=body,
                                 headers={'Origin':'http://localhost'},base_url='http://localhost')
        self.assertEqual(response.status_code,200);dispatch.assert_called_once_with(body)
        self.assertEqual(response.headers['Cache-Control'],'no-store')


if __name__=='__main__':unittest.main()
