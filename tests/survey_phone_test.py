"""Synthetic phone integration: no radio, external connections or personal data."""
import ast, gc, importlib.util, json, sqlite3, sys, tempfile, time, unittest, uuid
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask,request,jsonify,g

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packaging_cli',ROOT/'meshcrap.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)

class PhoneSurveyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();base=Path(self.tmp.name)
        config=json.loads((ROOT/'config.example.json').read_text());config['data_dir']=str(base/'data');config['https_host']='collector.example';config['trusted_hosts'].append('collector.example')
        path=base/'config.json';path.write_text(json.dumps(config));settings,self.data=cli.load_config(path)
        runtime=cli.initialize(settings,self.data);self.runtime=runtime;sys.path.insert(0,str(runtime/'dashboard'))
        import survey_phone
        self.app=Flask(__name__);self.app.testing=True
        self.phone=survey_phone.register_survey_phone(self.app,self.data)
        from dashboard_security import Security
        self.security=Security(self.app,self.data)
        self.client=self.app.test_client();self.token=json.loads(self.phone.pair('collector.example')['pairing_code'])['token']
        with sqlite3.connect(self.data/'mesh.db') as db:
            db.execute("INSERT INTO nodes(node_num,node_id,short_name,long_name) VALUES(305419896,'!12345678','MY1','MY Test')")
        self.now=int(time.time())
    def tearDown(self):gc.collect();self.tmp.cleanup()
    def post(self,path,body,token=None,https=True):
        return self.client.post('/api/survey-phone/'+path,json=body,headers={'Authorization':'Bearer '+(token or self.token)},base_url=('https' if https else 'http')+'://collector.example')
    def command(self,action='start',survey_id=0):return dict(id=str(uuid.uuid4()),action=action,survey_id=survey_id)
    def start(self):
        r=self.post('control',self.command());self.assertEqual(r.status_code,200);return r.json['survey_id']
    def event(self,survey):
        return dict(id=str(uuid.uuid4()),kind='position',survey_id=survey,source=305419896,time=self.now,
                    position=dict(lat=1.5,lon=2.5,time=self.now,source='phone_gps',accuracy_m=10))
    def sync(self,events):
        # Rate limiting is independently checked; simulate a later network retry.
        with self.phone.db() as db:db.execute('UPDATE clients SET last_seen=NULL')
        return self.post('sync',dict(source=305419896,ready=True,events=events))
    def test_passive_receptions_allowlist_and_cache_invalidation(self):
        survey=self.start();event=self.event(survey)
        event.update(kind='reception',sender=42,packet_id=7,channel=0,rx_time=self.now,rssi=-110,snr=-5.5,via_mqtt=False,text='never retain message contents')
        self.assertEqual(self.phone.report(survey)['metrics']['received_packets'],0)
        result=self.sync([event]);self.assertEqual(result.status_code,200);self.assertTrue(result.json['reception_records'])
        self.assertEqual(self.phone.report(survey)['metrics']['received_packets'],1)
        with self.phone.db() as db:
            self.assertNotIn('text',json.loads(db.execute('SELECT body FROM events').fetchone()[0]))
        for fields in [dict(via_mqtt=True),dict(sender=305419896),dict(rx_time=self.now-121),dict(snr=float('inf'))]:
            bad=dict(event,id=str(uuid.uuid4()),**fields)
            self.assertEqual(self.sync([bad]).status_code,400)

    def test_start_replay_and_no_area_requirement(self):
        command=self.command();first=self.post('control',command);second=self.post('control',command)
        self.assertEqual(first.json,second.json)
        with sqlite3.connect(self.data/'mesh.db') as db:
            self.assertEqual(db.execute('SELECT area_id FROM coverage_surveys').fetchall(),[('roaming',)])
        self.assertEqual(self.post('control',self.command()).status_code,409)
        command['action']='stop';self.assertEqual(self.post('control',command).status_code,400)
    def test_stop_cannot_end_replacement_session(self):
        first=self.start();stop=self.command('stop',first)
        self.assertEqual(self.post('control',stop).status_code,200);second=self.start()
        self.assertEqual(self.post('control',stop).status_code,200)
        self.assertEqual(self.post('control',self.command('stop',first)).status_code,409)
        with sqlite3.connect(self.data/'mesh.db') as db:
            self.assertEqual(db.execute('SELECT survey_id FROM coverage_surveys WHERE ended_at IS NULL').fetchone()[0],second)
    def test_credentials_https_revocation_and_no_admin_actions(self):
        self.assertEqual(self.post('control',self.command(),https=False).status_code,403)
        self.assertEqual(self.post('control',self.command(),token='x'*40).status_code,401)
        self.assertEqual(self.post('control',dict(id=str(uuid.uuid4()),action='reboot')).status_code,400)
        self.assertEqual(self.client.post('/api/coverage-survey',json={'action':'start'},headers={'Authorization':'Bearer '+self.token,'Origin':'https://collector.example'},base_url='https://collector.example').status_code,401)
        with self.phone.db() as db:db.execute('UPDATE clients SET revoked=1')
        self.assertEqual(self.post('control',self.command()).status_code,401)
    def test_replay_retains_coordinates_outside_configured_region(self):
        survey=self.start();event=self.event(survey)
        first=self.sync([event]);self.assertEqual(first.status_code,200);self.assertTrue(first.json['phone_controls'])
        self.assertEqual(first.json['area_name'],'Roaming survey');self.assertEqual(self.sync([event]).status_code,200)
        report=self.phone.report(survey);self.assertEqual(report['routes'][0]['segments'],[[[1.5,2.5]]])
        with self.phone.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],1)
        event['position']['lat']=3;self.assertEqual(self.sync([event]).status_code,400)
    def test_interrupted_batch_rolls_back_and_recovers(self):
        survey=self.start();event=self.event(survey);bad=self.event(survey);bad['time']=self.now+500
        self.assertEqual(self.sync([event,bad]).status_code,400)
        with self.phone.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],0)
        self.assertEqual(self.sync([event]).status_code,200)
    def test_ended_session_offline_replay_and_stale_position(self):
        survey=self.start();event=self.event(survey);self.post('control',self.command('stop',survey))
        self.assertEqual(self.sync([event]).status_code,200)
        event=self.event(survey);event['position']['time']=self.now-86401
        self.assertEqual(self.sync([event]).status_code,400)
        event=self.event(survey);event['time']=self.now+40;event['position']['time']=self.now+40
        self.assertEqual(self.sync([event]).status_code,400)
    def test_twenty_four_hour_half_mile_position_boundary(self):
        survey=self.start();event=self.event(survey)
        event['position'].update(time=self.now-86400,accuracy_m=804.672)
        self.assertEqual(self.sync([event]).status_code,200)
        event=self.event(survey);event['position']['accuracy_m']=804.673
        self.assertEqual(self.sync([event]).status_code,400)
        event=self.event(survey);event['position']['time']=self.now-86401
        self.assertEqual(self.sync([event]).status_code,400)
    def test_roaming_report_avoids_area_grid(self):
        survey=self.start();self.sync([self.event(survey)])
        # Exercise the actual reporting function without importing Linux-only service controls.
        tree=ast.parse((self.runtime/'dashboard/app.py').read_text(encoding='utf-8'))
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_survey_metrics','_survey_haversine')]
        namespace={'app':self.app};exec(compile(ast.Module(body=functions,type_ignores=[]),'app-report','exec'),namespace)
        with sqlite3.connect(self.data/'mesh.db') as db:
            db.row_factory=sqlite3.Row;row=db.execute('SELECT * FROM coverage_surveys').fetchone()
            report=namespace['_survey_metrics'](db,row)
        self.assertEqual(report['area_id'],'roaming');self.assertEqual(report['gps_samples'],1)
        self.assertEqual(report['routes'][0]['segments'][0][0],[1.5,2.5]);self.assertNotIn('cells_proven_this_survey',report)
    def test_twelve_hour_destination_and_no_last_heard_requirement(self):
        survey=self.start();event=self.event(survey)
        event.update(kind='trace',destination=591751049,packet_id=42,requested_at=self.now,channel=0,status='requested',destination_position=dict(lat=3.5,lon=4.5,time=self.now-43200,last_heard=0,source=2,precision_bits=24))
        self.assertEqual(self.sync([event]).status_code,200)
        event['id']=str(uuid.uuid4());event['destination_position']['time']-=1
        self.assertEqual(self.sync([event]).status_code,400)

    def test_trace_destination_snapshot_survives_late_reply(self):
        survey=self.start();event=self.event(survey)
        event.update(kind='trace',destination=591751049,packet_id=42,requested_at=self.now,channel=0,status='timeout',destination_position=dict(lat=3.5,lon=4.5,time=self.now-60,last_heard=self.now-10,source=2,precision_bits=24))
        self.assertEqual(self.sync([event]).status_code,200)
        late=dict(event,id=str(uuid.uuid4()),status='late_success',details=dict(response_from=591751049,response_to=305419896,response_packet_id=43,route=[],route_back=[]))
        self.assertEqual(self.sync([late]).status_code,200)
        trace=self.phone.report(survey)['traces'][0]
        self.assertEqual(trace['status'],'late_success');self.assertEqual(trace['position'],event['position']);self.assertEqual(trace['destination_position'],event['destination_position'])
    def test_dashboard_start_also_defaults_to_roaming(self):
        tree=ast.parse((self.runtime/'dashboard/app.py').read_text(encoding='utf-8'))
        names=('_survey_metrics','_survey_haversine','_survey_init','_survey_active','coverage_survey')
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        def database():
            if 'test_db' not in g:
                g.test_db=sqlite3.connect(self.data/'mesh.db');g.test_db.row_factory=sqlite3.Row
            return g.test_db
        @self.app.teardown_appcontext
        def close_database(error):
            db=g.pop('test_db',None)
            if db is not None:db.close()
        from coverage_areas import AREAS
        namespace=dict(app=self.app,request=request,jsonify=jsonify,db=database,AREAS=AREAS)
        exec(compile(ast.Module(body=functions,type_ignores=[]),'dashboard-survey','exec'),namespace)
        with self.client.session_transaction(base_url='https://collector.example') as session:session['radio_until']=time.time()+3600
        response=self.client.post('/api/coverage-survey',json={'action':'start'},base_url='https://collector.example',headers={'Origin':'https://collector.example'})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json['active']['area_id'],'roaming')

if __name__=='__main__':unittest.main()
