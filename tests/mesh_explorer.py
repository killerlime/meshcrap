"""Evidence correctness, bounded history, incremental summaries and private API behavior."""
import sys,sqlite3,json,tempfile,time,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from contextlib import contextmanager
from flask import Flask
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source/dashboard'))
import mesh_explorer as m
from message_evidence import enrich
from performance_metrics import register_performance

@contextmanager
def connection(path):
 c=sqlite3.connect(path)
 try:
  with c:yield c
 finally:c.close()

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.db=Path(self.temp.name)/'mesh.db';self.now=datetime.now(timezone.utc)
  with connection(self.db) as c:
   c.execute('CREATE TABLE packets(row_id INTEGER PRIMARY KEY,collector_time TEXT,from_num INTEGER,to_num INTEGER,packet_id INTEGER,portnum TEXT,rx_snr REAL,rx_rssi REAL,hops_used INTEGER,transport TEXT,raw_json TEXT,observation_type TEXT,battery_level REAL,voltage REAL,channel INTEGER)')
   c.execute('CREATE TABLE nodes(node_num INTEGER,node_id TEXT,long_name TEXT,short_name TEXT,role TEXT)')
   c.executemany('INSERT INTO nodes VALUES (?,?,?,?,?)',[(1,'!00000001','One','O','CLIENT'),(2,'!00000002','Two','T','CLIENT'),(3,'!00000003','Receiver','R','CLIENT')])
   c.execute('CREATE TABLE web_sent_messages(sender_num INTEGER,packet_id INTEGER,channel INTEGER,destination_num INTEGER,text TEXT,submitted_at TEXT)')
  self.app=Flask(__name__);self.index=m.register_explorer(self.app,self.db,'!00000003',False);register_performance(self.app);self.client=self.app.test_client()
 def tearDown(self):self.temp.cleanup()
 def insert(self,id,origin=1,dest=3,port='NODEINFO_APP',raw=None,ago=10,**kw):
  r=dict(row_id=id,collector_time=(self.now-timedelta(seconds=ago)).isoformat(),from_num=origin,to_num=dest,packet_id=id,portnum=port,rx_snr=3,rx_rssi=-100,hops_used=0,transport='TRANSPORT_LORA',raw_json=json.dumps(raw or {}),observation_type='LIVE',battery_level=None,voltage=None,channel=0);r.update(kw)
  with connection(self.db) as c:c.execute('INSERT INTO packets VALUES ('+','.join('?' for _ in r)+')',tuple(r.values()))
 def test_topology_does_not_invent_links(self):
  self.insert(1);self.insert(2,hops_used=2,raw={'relayNode':234});self.insert(3,raw={'viaMqtt':True});self.insert(4,origin=3)
  data=self.client.get('/api/explorer/topology').json
  self.assertEqual(len(data['edges']),1);self.assertEqual(data['edges'][0]['evidence'],'direct reception');self.assertEqual(data['ambiguous'][0]['relay_byte'],'ea')
 def test_traceroute_direction_and_unknown_hops(self):
  self.insert(1,origin=1,dest=3,port='TRACEROUTE_APP',raw={'hopStart':3,'decoded':{'requestId':99,'traceroute':{'route':[2,4294967295],'snrBack':[4]}}})
  routes=self.client.get('/api/explorer/routes').json['routes'];self.assertEqual(routes[0]['path'],['!00000003','!00000002','Unknown hop','!00000001']);self.assertEqual(routes[1]['path'],['!00000001','!00000003'])
  edges=self.client.get('/api/explorer/topology').json['edges'];self.assertFalse(any('Unknown' in str(e) for e in edges))
 def test_routes_compare_equal_windows(self):
  for i,ago in enumerate((10,100,4000),1):self.insert(i,port='TRACEROUTE_APP',ago=ago,raw={'decoded':{'requestId':99,'traceroute':{'route':[2]}}})
  r=self.client.get('/api/explorer/routes?hours=1').json['routes'][0];self.assertEqual((r['current'],r['previous']),(2,1))
 def test_incremental_index_and_daily_union(self):
  self.insert(1);self.insert(2,ago=4000);self.insert(3,origin=2);self.insert(4,raw={'viaMqtt':True})
  self.index.step();a=self.index.report(7);self.index.step();b=self.index.report(7)
  self.assertEqual(a['rows'],b['rows']);self.assertEqual(sum(r['observations'] for r in a['rows']),3);self.assertEqual(max(r['unique_nodes'] for r in a['daily']),2);self.assertTrue(a['caught_up'])
 def test_readonly_source(self):
  with self.assertRaises(sqlite3.OperationalError):m.read(self.db,'DELETE FROM nodes')
 def test_telemetry_missing_zero_and_window(self):
  self.insert(1,battery_level=0);self.insert(2,battery_level=None);self.insert(3,origin=2,battery_level=80)
  d=self.client.get('/api/explorer/telemetry?nodes=!00000001&metric=battery').json
  self.assertEqual(len(d['series'][0]['points']),1);self.assertEqual(d['series'][0]['points'][0]['mean'],0)
  self.assertEqual(self.client.get('/api/explorer/telemetry?nodes=garbage').status_code,400)
 def test_etag_and_performance_no_sensitive_arguments(self):
  first=self.client.get('/api/explorer/nodes?secret=not-recorded');second=self.client.get('/api/explorer/nodes?secret=not-recorded',headers={'If-None-Match':first.headers['ETag']})
  self.assertEqual(second.status_code,304);d=self.client.get('/api/explorer/performance').json;self.assertNotIn('not-recorded',json.dumps(d));self.assertEqual(d['endpoints'][0]['unchanged'],1)
 def test_ack_sender_destination_and_failure(self):
  with connection(self.db) as c:c.execute('INSERT INTO web_sent_messages VALUES (3,90,0,1,?,?)',('test',(self.now-timedelta(seconds=60)).isoformat()))
  self.insert(1,origin=2,port='ROUTING_APP',raw={'decoded':{'requestId':90,'routing':{'errorReason':'NONE'}}})
  msg=dict(id='sent:90',sender_id='!00000003',direction='sent');self.assertEqual(enrich(self.db,[dict(msg)])[0]['delivery']['state'],'awaiting_ack')
  self.insert(2,origin=1,port='ROUTING_APP',raw={'decoded':{'requestId':90,'routing':{'errorReason':'NO_ROUTE'}}})
  self.assertEqual(enrich(self.db,[dict(msg)])[0]['delivery']['state'],'failed')
  self.insert(3,origin=1,port='ROUTING_APP',raw={'decoded':{'requestId':90,'routing':{'errorReason':'NONE'}}})
  self.assertEqual(enrich(self.db,[dict(msg)])[0]['delivery']['state'],'acknowledged')
 def test_performance_does_not_drain_a_stream(self):
  produced=[]
  def stream():
   for i in range(3):produced.append(i);yield str(i)
  self.app.add_url_rule('/api/test-stream',view_func=lambda:self.app.response_class(stream()))
  response=self.client.get('/api/test-stream',buffered=False)
  self.assertEqual(produced,[0]);response.close()
 def test_map_geometry_only(self):
  Path(self.db).with_name('offline-map.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'geometry':{'type':'Point','coordinates':[0,0]},'properties':{'html':'<script>bad</script>'}}]}))
  r=self.client.get('/api/explorer/map-pack');self.assertEqual(r.status_code,200);self.assertNotIn('<script>',r.get_data(as_text=True))
 def test_malformed_telemetry_and_mqtt_are_not_measurements(self):
  self.insert(1,port='TELEMETRY_APP',raw={'decoded':[]})
  self.insert(2,battery_level=90,transport='TRANSPORT_MQTT')
  self.insert(3,port='TELEMETRY_APP',raw={'decoded':{'telemetry':{'environmentMetrics':{'temperature':0}}}})
  self.assertEqual(self.client.get('/api/explorer/telemetry?nodes=!00000001&metric=battery').json['series'][0]['points'],[])
  self.assertEqual(self.client.get('/api/explorer/telemetry?nodes=!00000001&metric=temperature').json['series'][0]['points'][0]['mean'],0)
 def test_old_ack_and_snapshot_do_not_confirm_delivery(self):
  with connection(self.db) as c:c.execute('INSERT INTO web_sent_messages VALUES (3,90,0,1,?,?)',('test',(self.now-timedelta(seconds=60)).isoformat()))
  self.insert(1,ago=120,port='ROUTING_APP',raw={'decoded':{'requestId':90,'routing':{'errorReason':'NONE'}}})
  self.insert(2,observation_type='SNAPSHOT',port='ROUTING_APP',raw={'decoded':{'requestId':90,'routing':{'errorReason':'NONE'}}})
  msg=dict(id='sent:90',sender_id='!00000003',direction='sent')
  self.assertEqual(enrich(self.db,[msg])[0]['delivery']['state'],'awaiting_ack')
 def test_proto_defaults_and_requests_not_confused_with_responses(self):
  self.insert(1,port='TRACEROUTE_APP',raw={'hopStart':3,'decoded':{'requestId':42,'traceroute':{'snrBack':[0]}}})
  self.insert(2,port='TRACEROUTE_APP',raw={'decoded':{'wantResponse':True,'traceroute':{'route':[2]}}})
  r=self.client.get('/api/explorer/routes').json['routes'];self.assertEqual(len(r),2)
  self.assertEqual(r[0]['path'],['!00000003','!00000001'])
  with connection(self.db) as c:c.execute('INSERT INTO web_sent_messages VALUES (3,90,0,1,?,?)',('test',(self.now-timedelta(seconds=60)).isoformat()))
  self.insert(3,port='ROUTING_APP',raw={'decoded':{'requestId':90,'routing':{}}})
  self.assertEqual(enrich(self.db,[dict(id='sent:90',sender_id='!00000003',direction='sent')])[0]['delivery']['state'],'acknowledged')
 def test_no_return_proof_and_invalid_query(self):
  self.insert(1,port='TRACEROUTE_APP',raw={'decoded':{'requestId':42,'traceroute':{'routeBack':[]}}})
  self.assertEqual(len(self.client.get('/api/explorer/routes').json['routes']),1)
  self.assertEqual(self.client.get('/api/explorer/topology?hours=bad').status_code,400)
 def test_history_purge_is_backed_up_and_cannot_reintroduce_old_rows(self):
  from node_utilities import purge
  self.insert(1);self.insert(2,origin=2);self.index.step()
  result=purge(self.db,1);self.index.step()
  with connection(self.index.path) as c:self.assertFalse(c.execute('SELECT 1 FROM hourly WHERE node=?',('!00000001',)).fetchone())
  self.assertEqual(result['deleted']['explorer_history.hourly'],1)
  self.assertTrue((Path(result['backup'])/'mesh-explorer-history.sqlite3').exists())
  self.assertEqual(sum(v['observations'] for v in self.index.report(7)['rows']),1)
 def test_invalid_geometry_rejected_and_attribution_is_text(self):
  path=Path(self.db).with_name('offline-map.geojson')
  path.write_text(json.dumps({'type':'FeatureCollection','features':[{'geometry':{'type':'Point','coordinates':[0,1000]}}]}))
  self.assertEqual(self.client.get('/api/explorer/map-pack').status_code,400)
  path.write_text(json.dumps({'type':'FeatureCollection','features':[{'geometry':{'type':'Point','coordinates':[0,0]}}]}))
  path.with_name('offline-map-attribution.txt').write_text('Example data author')
  self.assertEqual(self.client.get('/api/explorer/map-pack').json['attribution'],'Example data author')

if __name__=='__main__':unittest.main()
