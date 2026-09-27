"""Private Android survey uploads, isolated from HQ radio measurements."""
import hashlib,json,math,secrets,sqlite3,time,uuid
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime,timezone
from flask import request,jsonify,g,render_template,send_from_directory

def epoch(value):
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    return (stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)).timestamp()

def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError('Invalid integer field')
    return value

def validate_position(p,now):
    if not isinstance(p,dict):raise ValueError('Position required')
    lat,lon=p.get('lat'),p.get('lon')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lon)) or not -90<=lat<=90 or not -180<=lon<=180 or (lat==lon==0):raise ValueError('Invalid position')
    stamp=integer(p.get('time'),1,int(now+120))
    source=p.get('source')
    if source not in ('phone_gps','radio_position'):raise ValueError('Invalid position source')
    out=dict(lat=lat,lon=lon,time=stamp,source=source)
    if source=='phone_gps':
        accuracy=p.get('accuracy_m')
        if type(accuracy) not in (int,float) or not math.isfinite(accuracy) or not 0<=accuracy<=100:raise ValueError('Invalid GPS accuracy')
        out['accuracy_m']=accuracy
    return out

class SurveyPhone:
    def __init__(self,app,root):
        self.root=Path(root);self.path=self.root/'survey-phone.sqlite3';self.mesh=self.root/'mesh.db'
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL,created REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,last_seen REAL,status TEXT);
              CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,client INTEGER NOT NULL,survey INTEGER NOT NULL,source INTEGER NOT NULL,kind TEXT NOT NULL,received REAL NOT NULL,body TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS events_survey ON events(survey,received);''')
        self.path.chmod(0o600);app.extensions['survey_phone']=self
    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=5);c.row_factory=sqlite3.Row
        try:
            with c:yield c
        finally:c.close()
    @contextmanager
    def meshdb(self):
        c=sqlite3.connect('file:'+str(self.mesh)+'?mode=ro',uri=True,timeout=5);c.row_factory=sqlite3.Row
        try:yield c
        finally:c.close()
    def authorize(self):
        if not request.is_secure:return jsonify(error='Use the private HTTPS address'),403
        if request.method!='POST' or not request.is_json or not request.content_length or request.content_length>65536:return jsonify(error='Invalid upload'),400
        token=request.headers.get('Authorization','')
        if not token.startswith('Bearer ') or not 32<=len(token[7:])<=128:return jsonify(error='Phone pairing required'),401
        digest=hashlib.sha256(token[7:].encode()).hexdigest()
        with self.db() as db:client=db.execute('SELECT * FROM clients WHERE token_hash=? AND revoked=0',(digest,)).fetchone()
        if not client:return jsonify(error='Phone pairing expired or revoked'),401
        g.survey_phone_client=dict(client)
        if client['last_seen'] and time.time()-client['last_seen']<2:return jsonify(error='Wait before syncing again'),429
        return None
    def pair(self,https_host):
        token=secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('UPDATE clients SET revoked=1 WHERE revoked=0')
            cur=db.execute('INSERT INTO clients(token_hash,created) VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),time.time()))
            client=cur.lastrowid
        return dict(client_id=client,pairing_code=json.dumps(dict(url='https://'+https_host+'/api/survey-phone/sync',token=token,node_prefix='@@NODE_PREFIX@@'),separators=(',',':')))
    def sync(self):
        data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Expected object'),400
        client=g.survey_phone_client;now=time.time()
        try:
            source=integer(data.get('source'),0,0xfffffffe)
            events=data.get('events',[])
            if not isinstance(events,list) or len(events)>10:raise ValueError('Maximum ten records per upload')
            with self.meshdb() as mesh:
                known={r[0] for r in mesh.execute("SELECT node_num FROM nodes WHERE lower(trim(coalesce(short_name,''))) LIKE '@@NODE_PREFIX_LOWER@@%' OR lower(trim(coalesce(long_name,''))) LIKE '@@NODE_PREFIX_LOWER@@ %'")}
                active=mesh.execute('SELECT * FROM coverage_surveys WHERE ended_at IS NULL ORDER BY survey_id DESC LIMIT 1').fetchone()
                normalized=[]
                for event in events:
                    if not isinstance(event,dict):raise ValueError('Invalid record')
                    event_id=str(uuid.UUID(event.get('id','')))
                    survey_id=integer(event.get('survey_id'),1,2147483647)
                    survey=mesh.execute('SELECT * FROM coverage_surveys WHERE survey_id=?',(survey_id,)).fetchone()
                    if survey is None:raise ValueError('Unknown survey')
                    node=integer(event.get('source'),1,0xfffffffe)
                    if node not in known:raise ValueError('Source is not a known local-prefix node')
                    stamp=integer(event.get('time'),1,int(now+120))
                    if stamp<epoch(survey['started_at'])-120:raise ValueError('Record predates survey')
                    kind=event.get('kind')
                    clean=dict(id=event_id,kind=kind,survey_id=survey_id,source=node,time=stamp)
                    p=event.get('position')
                    if p is not None:
                        clean['position']=validate_position(p,now)
                        reference=event.get('requested_at',stamp)
                        if type(reference) is not int or not -120<=reference-clean['position']['time']<=300:raise ValueError('Position was not fresh at observation')
                    if kind=='position':
                        if p is None:raise ValueError('Missing position')
                        if survey['ended_at'] and stamp>epoch(survey['ended_at'])+30:raise ValueError('Position outside survey')
                    elif kind=='trace':
                        dest=integer(event.get('destination'),1,0xfffffffe)
                        if dest==node:raise ValueError('Destination equals source')
                        at=integer(event.get('requested_at'),1,int(now+120))
                        if at<epoch(survey['started_at'])-120 or stamp<at-120 or (survey['ended_at'] and at>epoch(survey['ended_at'])+30):raise ValueError('Request outside survey')
                        status=event.get('status')
                        if status not in ('requested','success','late_success','timeout','routing_error','transport_error','stopped'):raise ValueError('Unknown result status')
                        clean.update(destination=dest,requested_at=at,packet_id=integer(event.get('packet_id'),1,0xffffffff),channel=integer(event.get('channel'),0,7),status=status,test=event.get('test') is True)
                        details=event.get('details',{})
                        if not isinstance(details,dict):raise ValueError('Invalid response details')
                        if status in ('success','late_success'):
                            if details.get('response_from')!=dest or details.get('response_to')!=node:raise ValueError('Response identity mismatch')
                            parsed={}
                            for key in ('route','route_back','snr_towards_quarter_db','snr_back_quarter_db'):
                                values=details.get(key,[])
                                if not isinstance(values,list) or len(values)>16:raise ValueError('Invalid route')
                                parsed[key]=[integer(v,0,0xffffffff) if key.startswith('route') else integer(v,-1000,1000) for v in values]
                            parsed.update(response_from=dest,response_to=node,response_packet_id=integer(details.get('response_packet_id'),0,0xffffffff))
                            clean['details']=parsed
                        elif status=='routing_error':clean['details']={'routing_error':str(details.get('routing_error','Unknown'))[:64]}
                    else:raise ValueError('Unknown record kind')
                    normalized.append(clean)
            if source and source not in known:raise ValueError('Connected source is not a known local-prefix node')
            status=dict(source=source,ready=data.get('ready') is True,armed=data.get('armed') is True,channel=integer(data.get('channel',0),0,7),nearby=integer(data.get('nearby',0),0,10000))
            with self.db() as db:
                for event in normalized:
                    encoded=json.dumps(event,sort_keys=True,separators=(',',':'))
                    old=db.execute('SELECT client,body FROM events WHERE id=?',(event['id'],)).fetchone()
                    # Re-pairing rotates credentials but retains this phone's idempotent outbox.
                    if old and old['body']!=encoded:raise ValueError('Conflicting record identifier')
                    db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?)',(event['id'],client['id'],event['survey_id'],event['source'],event['kind'],now,encoded))
                db.execute('UPDATE clients SET last_seen=?,status=? WHERE id=?',(now,json.dumps(status),client['id']))
            from coverage_areas import AREAS
            return jsonify(ok=True,accepted=[e['id'] for e in normalized],survey_id=active['survey_id'] if active else 0,
                           area_name=AREAS[active['area_id']]['name'] if active else '',lease_seconds=30 if source in known and status['ready'] else 0)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as e:return jsonify(error=str(e)),400
    def report(self,survey_id):
        with self.db() as db:
            # Bound the response; all original records remain in the separate phone database.
            rows=db.execute('SELECT body FROM events WHERE survey=? ORDER BY received DESC,rowid DESC LIMIT 5000',(survey_id,)).fetchall()
            client=db.execute('SELECT last_seen,status FROM clients WHERE revoked=0 ORDER BY id DESC LIMIT 1').fetchone()
        traces={};positions={}
        for r in rows:
            e=json.loads(r['body'])
            if e['kind']=='trace':
                key=(e['source'],e['packet_id'])
                priority={'requested':0,'stopped':1,'transport_error':1,'routing_error':1,'timeout':1,'success':2,'late_success':2}
                if key not in traces or priority[e['status']]>priority[traces[key]['status']]:traces[key]=e
            elif e['kind']=='position':positions.setdefault(e['source'],[]).append(e['position'])
        paths=[]
        import math
        def distance(a,b):
            p1,p2=math.radians(a['lat']),math.radians(b['lat'])
            x=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(b['lon']-a['lon'])/2)**2
            return 3958.7613*2*math.asin(math.sqrt(min(1,max(0,x))))
        for node,points in positions.items():
            points.sort(key=lambda p:p['time']);segments=[];segment=[];previous=None
            for p in points:
                if previous and (p['time']-previous['time']>300 or distance(previous,p)>5):
                    if segment:segments.append(segment)
                    segment=[]
                segment.append([p['lat'],p['lon']]);previous=p
            if segment:segments.append(segment)
            paths.append(dict(node_num=node,node=f'Phone survey !{node:08x}',segments=segments,samples=len(points),simplified=False))
        with self.meshdb() as mesh:
            names={r['node_num']:r['name'] for r in mesh.execute("SELECT node_num,coalesce(nullif(long_name,''),nullif(short_name,''),node_id) AS name FROM nodes") if r['name']}
        return dict(names=names,status='Phone connected' if client and client['last_seen'] and time.time()-client['last_seen']<45 else 'Phone not connected',
                    traces=list(traces.values())[:100],trace_count=len(traces),successes=sum(e['status'] in ('success','late_success') for e in traces.values()),routes=paths)

def register_survey_phone(app,root='@@DATA_DIR@@'):
    phone=SurveyPhone(app,root)
    @app.get('/survey-companion')
    def setup():return render_template('survey-companion.html',https_host=app.extensions['dashboard_security'].https_host,
        apk_available=(Path(root)/'dashboard/survey-downloads/jk-survey-test.apk').is_file())
    @app.get('/survey-companion/<name>')
    def artifact(name):
        if name not in ('jk-survey-test.apk','jk-survey-source.zip'):return jsonify(error='Unknown file'),404
        return send_from_directory(Path(root)/'dashboard/survey-downloads',name,as_attachment=True)
    @app.post('/api/survey-phone/pair')
    def pair():
        security=app.extensions['dashboard_security']
        if not security.admin():return jsonify(error='Unlock admin controls first'),401
        if not request.is_secure or request.host!=security.https_host:return jsonify(error='Open the private HTTPS setup page'),403
        return jsonify(phone.pair(security.https_host))
    @app.post('/api/survey-phone/revoke')
    def revoke():
        if not app.extensions['dashboard_security'].admin():return jsonify(error='Unlock admin controls first'),401
        with phone.db() as db:db.execute('UPDATE clients SET revoked=1')
        return jsonify(ok=True)
    @app.post('/api/survey-phone/sync')
    def sync():
        if not hasattr(g,'survey_phone_client'):return jsonify(error='Phone authentication required'),401
        return phone.sync()
    return phone
