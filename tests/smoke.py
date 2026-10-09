"""Clean-install HTTP checks; no radio, external network, or production data."""
import importlib.util,json,os,sys,tempfile,sqlite3,urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packaging_cli',ROOT/'meshcrap.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
with tempfile.TemporaryDirectory(prefix='meshcrap-test-') as directory:
    base=Path(directory);path=base/'config.json'
    config=json.loads((ROOT/'config.example.json').read_text());config['data_dir']=str(base/'data')
    config['receiver_id']='!12345678';config['radio_host']='192.0.2.10'
    path.write_text(json.dumps(config));settings,data=cli.load_config(path)
    runtime=cli.initialize(settings,data)
    sys.path[:0]=[str(runtime),str(runtime/'dashboard')]
    with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected external HTTP request')):
        import app
        app.app.config['TESTING']=True
        client=app.app.test_client();failures=[]
        for route in ('/','/api/summary','/api/map','/api/coverage','/api/coverage-survey','/api/noc',
                      '/api/channel-messages','/api/rf-environment','/api/rf-health-hourly','/api/lna-experiment',
                      '/api/lna-analysis','/api/hq-weather','/api/recovery-health','/survey-companion',
                      '/api/node-control/session','/api/mobile-access','/api/potato-feed/status','/api/role-comparison?hours=24',
                      '/api/explorer/nodes','/api/explorer/topology','/api/explorer/routes',
                      '/api/explorer/telemetry?nodes=!23456789','/api/explorer/history',
                      '/api/explorer/delivery','/api/explorer/performance','/api/explorer/map-pack'):
            try:
                response=client.get(route,base_url='http://localhost')
                assert response.status_code==200,(route,response.status_code,response.get_json(silent=True))
            except Exception as error:
                failures.append((route,repr(error)))
        assert client.post('/api/coverage-survey',json={}).status_code in (401,403)
        assert client.get('/api/msp-ingestors').status_code==501
        assert client.get('/api/potato-feed/status').get_json()['enabled'] is False
        with sqlite3.connect(data/'mesh.db') as db:
            assert db.execute('SELECT count(*) FROM nodes').fetchone()[0]==0
            assert db.execute('SELECT count(*) FROM packets').fetchone()[0]==0
        # Feed a synthetic received packet through the real storage path, without a TCP connection.
        import collector,time
        from types import SimpleNamespace
        collector.db=collector.open_database()
        try:
            collector.on_receive({'from':0x23456789,'fromId':'!23456789','to':0xffffffff,
                'toId':'^all','id':123,'channel':0,'rxTime':int(time.time()),'rxSnr':3.0,'rxRssi':-95,
                'decoded':{'portnum':'NODEINFO_APP','user':{'id':'!23456789','longName':'Synthetic receiver','shortName':'TEST'}}},
                SimpleNamespace(localNode=SimpleNamespace(nodeNum=0x12345678)))
            assert collector.db.execute('SELECT count(*) FROM packets').fetchone()[0]==1
            assert collector.db.execute('SELECT node_id FROM nodes WHERE node_num=?',(0x23456789,)).fetchone()[0]=='!23456789'
            assert json.loads(collector.db.execute('SELECT raw_json FROM packets').fetchone()[0])['decoded']['user']['longName']=='Synthetic receiver'
            assert client.get('/api/summary').status_code==200
            assert client.get('/api/map').status_code==200
        finally:collector.db.close()
        assert not failures,failures
    print('PASS: empty-database dashboard, coverage, messages, surveys, LNA, auth defaults; no imported nodes or packets')
