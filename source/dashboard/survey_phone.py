"""Private Android survey uploads, isolated from HQ radio measurements."""
import hashlib,json,math,secrets,sqlite3,time,uuid,threading
from collections import OrderedDict
from pathlib import Path
from contextlib import contextmanager,closing
from datetime import datetime,timezone
from flask import request,jsonify,g,render_template,send_from_directory

class SurveyValidationError(ValueError):
    """Only application-authored validation guidance is safe to send to a phone."""
    def __init__(self, public_message):
        super().__init__(public_message)
        self.public_message=public_message

def epoch(value):
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    return (stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)).timestamp()

def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise SurveyValidationError('Invalid integer field')
    return value

def validate_position(p,now,allow_unknown_time=False):
    if not isinstance(p,dict):raise SurveyValidationError('Position required')
    lat,lon=p.get('lat'),p.get('lon')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lon)) or not -90<=lat<=90 or not -180<=lon<=180 or (lat==lon==0):raise SurveyValidationError('Invalid position')
    stamp=integer(p.get('time'),0 if allow_unknown_time else 1,int(now+120))
    source=p.get('source')
    if source not in ('phone_gps','radio_position'):raise SurveyValidationError('Invalid position source')
    out=dict(lat=lat,lon=lon,time=stamp,source=source)
    if source=='phone_gps':
        accuracy=p.get('accuracy_m')
        if type(accuracy) not in (int,float) or not math.isfinite(accuracy) or not 0<=accuracy<=804.672:raise SurveyValidationError('Invalid GPS accuracy')
        out['accuracy_m']=accuracy
    return out

def validate_destination_position(target,observed_at,now):
    """Advertised coordinates select discovery targets; they do not prove coverage."""
    position=validate_position(dict(target,source='radio_position'),now,allow_unknown_time=True)
    position['source']=integer(target.get('source'),0,3)
    position['precision_bits']=integer(target.get('precision_bits'),0,32)
    position['last_heard']=integer(target.get('last_heard',0),0,int(now+120))
    age=observed_at-position['time']
    if position['time'] and (age<0 or (position['source'] in (2,3) and age>7*86400)):
        raise SurveyValidationError('Destination GPS position is outside the discovery window')
    return position

class SurveyPhone:
    def __init__(self,app,root):
        self.report_cache=OrderedDict();self.report_lock=threading.Lock()
        self.root=Path(root);self.path=self.root/'survey-phone.sqlite3';self.mesh=self.root/'mesh.db'
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL,created REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,last_seen REAL,status TEXT);
              CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,client INTEGER NOT NULL,survey INTEGER NOT NULL,source INTEGER NOT NULL,kind TEXT NOT NULL,received REAL NOT NULL,body TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS events_survey ON events(survey,received);
              CREATE TABLE IF NOT EXISTS offline_permits(token TEXT PRIMARY KEY,client INTEGER NOT NULL,survey INTEGER NOT NULL,source INTEGER NOT NULL,issued INTEGER NOT NULL,expires INTEGER NOT NULL);
              CREATE INDEX IF NOT EXISTS offline_permits_scope ON offline_permits(client,survey,source,expires);''')
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
        if request.path.endswith('/sync') and client['last_seen'] and time.time()-client['last_seen']<2:return jsonify(error='Wait before syncing again'),429
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
            if not isinstance(events,list) or len(events)>10:raise SurveyValidationError('Maximum ten records per upload')
            with self.meshdb() as mesh, self.db() as permits:
                known={r[0] for r in mesh.execute("SELECT node_num FROM nodes WHERE lower(trim(coalesce(short_name,''))) LIKE '@@NODE_PREFIX_LOWER@@%' OR lower(trim(coalesce(long_name,''))) LIKE '@@NODE_PREFIX_LOWER@@ %'")}
                active=mesh.execute('SELECT * FROM coverage_surveys WHERE ended_at IS NULL ORDER BY survey_id DESC LIMIT 1').fetchone()
                normalized=[];local_outings={}
                for event in events:
                    if not isinstance(event,dict):raise SurveyValidationError('Invalid record')
                    event_id=str(uuid.UUID(event.get('id','')))
                    outing=event.get('outing')
                    if outing is not None:
                        if not isinstance(outing,dict):raise SurveyValidationError('Invalid phone outing')
                        outing_id=str(uuid.UUID(outing.get('id','')))
                        started=integer(outing.get('started_at'),1,int(now+120))
                        local_outings[event_id]=(outing_id,started)
                        survey_id=0
                        survey=dict(started_at=datetime.fromtimestamp(started,timezone.utc).isoformat(),ended_at=None)
                    else:
                        survey_id=integer(event.get('survey_id'),1,2147483647)
                        survey=mesh.execute('SELECT * FROM coverage_surveys WHERE survey_id=?',(survey_id,)).fetchone()
                    if survey is None:raise SurveyValidationError('Unknown survey')
                    node=integer(event.get('source'),1,0xfffffffe)
                    if node not in known:raise SurveyValidationError('Source is not a known local-prefix node')
                    stamp=integer(event.get('time'),1,int(now+120))
                    if stamp<epoch(survey['started_at'])-120:raise SurveyValidationError('Record predates survey')
                    kind=event.get('kind')
                    clean=dict(id=event_id,kind=kind,survey_id=survey_id,source=node,time=stamp)
                    if outing is not None:clean['outing']=dict(id=outing_id,started_at=started)
                    # Upload may occur days later. Validate observation time, not delivery time.
                    # An offline phone cannot learn that someone ended its outing remotely.
                    # Keep its granted observations on the original outing, never a replacement.
                    offline=False
                    permit=event.get('offline_permit')
                    if permit is not None:
                        if not isinstance(permit,str) or len(permit)>128:raise SurveyValidationError('Invalid offline permit')
                        grant=permits.execute('SELECT * FROM offline_permits WHERE token=?',(permit,)).fetchone()
                        reference=event.get('requested_at',stamp)
                        if not grant or grant['survey']!=survey_id or grant['source']!=node or type(reference) is not int or not grant['issued']-120<=reference<=grant['expires']:raise SurveyValidationError('Offline observation outside authorization')
                        offline=True
                        clean['offline_authorized']=True
                    p=event.get('position')
                    if p is not None:
                        clean['position']=validate_position(p,now)
                        reference=event.get('requested_at',stamp)
                        if type(reference) is not int or not -120<=reference-clean['position']['time']<=86400:raise SurveyValidationError('Position was not fresh at observation')
                    if kind in ('outing_start','outing_end'):
                        if outing is None:raise SurveyValidationError('Phone outing required')
                    elif kind=='position':
                        if p is None:raise SurveyValidationError('Missing position')
                        if not offline and survey['ended_at'] and stamp>epoch(survey['ended_at'])+30:raise SurveyValidationError('Position outside survey')
                    elif kind=='reception':
                        if not offline and survey['ended_at'] and stamp>epoch(survey['ended_at'])+30:raise SurveyValidationError('Reception outside survey')
                        sender=integer(event.get('sender'),1,0xfffffffe)
                        if sender==node:raise SurveyValidationError('Local transmission is not received RF')
                        rx=integer(event.get('rx_time'),1,stamp)
                        if stamp-rx>120 or event.get('via_mqtt') is not False:raise SurveyValidationError('Not a current radio reception')
                        rssi=integer(event.get('rssi'),-200,-1)
                        snr=event.get('snr')
                        if type(snr) not in (int,float) or not math.isfinite(snr) or not -100<=snr<=100:raise SurveyValidationError('Invalid SNR')
                        clean.update(sender=sender,packet_id=integer(event.get('packet_id'),1,0xffffffff),channel=integer(event.get('channel'),0,7),rx_time=rx,rssi=rssi,snr=snr,via_mqtt=False)
                    elif kind=='trace':
                        dest=integer(event.get('destination'),1,0xfffffffe)
                        if dest==node:raise SurveyValidationError('Destination equals source')
                        at=integer(event.get('requested_at'),1,int(now+120))
                        if at<epoch(survey['started_at'])-120 or stamp<at-120 or (not offline and survey['ended_at'] and at>epoch(survey['ended_at'])+30):raise SurveyValidationError('Request outside survey')
                        status=event.get('status')
                        if status not in ('requested','success','late_success','timeout','routing_error','transport_error','stopped'):raise SurveyValidationError('Unknown result status')
                        clean.update(destination=dest,requested_at=at,packet_id=integer(event.get('packet_id'),1,0xffffffff),channel=integer(event.get('channel'),0,7),status=status,test=event.get('test') is True)
                        target=event.get('destination_position')
                        if target is not None:
                            if not isinstance(target,dict):raise SurveyValidationError('Invalid destination position')
                            position=validate_destination_position(target,at,now)
                            clean['destination_position']=position
                        details=event.get('details',{})
                        if not isinstance(details,dict):raise SurveyValidationError('Invalid response details')
                        if status in ('success','late_success'):
                            if details.get('response_from')!=dest or details.get('response_to')!=node:raise SurveyValidationError('Response identity mismatch')
                            parsed={}
                            for key in ('route','route_back','snr_towards_quarter_db','snr_back_quarter_db'):
                                values=details.get(key,[])
                                if not isinstance(values,list) or len(values)>16:raise SurveyValidationError('Invalid route')
                                parsed[key]=[integer(v,0,0xffffffff) if key.startswith('route') else integer(v,-1000,1000) for v in values]
                            parsed.update(response_from=dest,response_to=node,response_packet_id=integer(details.get('response_packet_id'),0,0xffffffff))
                            clean['details']=parsed
                        elif status=='routing_error':clean['details']={'routing_error':str(details.get('routing_error','Unknown'))[:64]}
                    else:raise SurveyValidationError('Unknown record kind')
                    normalized.append(clean)
            if source and source not in known:raise SurveyValidationError('Connected source is not a known local-prefix node')
            status=dict(source=source,ready=data.get('ready') is True,armed=data.get('armed') is True,channel=integer(data.get('channel',0),0,7),nearby=integer(data.get('nearby',0),0,10000))
            offline_permit='';offline_until=0
            with self.db() as db:
                # Attach for one atomic commit of trip IDs and event acknowledgments.
                # Imported phone outings never occupy or end the collector's active survey.
                db.execute('ATTACH DATABASE ? AS meshdata',(str(self.mesh),))
                db.execute('BEGIN IMMEDIATE')
                db.execute('CREATE TABLE IF NOT EXISTS meshdata.phone_outings(id TEXT PRIMARY KEY,survey INTEGER NOT NULL,source INTEGER NOT NULL,started INTEGER NOT NULL,ended INTEGER)')
                for event in normalized:
                    if event['id'] in local_outings:
                        outing_id,started=local_outings[event['id']]
                        old_outing=db.execute('SELECT * FROM meshdata.phone_outings WHERE id=?',(outing_id,)).fetchone()
                        if old_outing:
                            if old_outing['source']!=event['source'] or old_outing['started']!=started:raise SurveyValidationError('Conflicting phone outing')
                            event['survey_id']=old_outing['survey']
                            if old_outing['ended'] and event.get('requested_at',event['time'])>old_outing['ended']:raise SurveyValidationError('Observation after phone outing ended')
                        else:
                            start_iso=datetime.fromtimestamp(started,timezone.utc).isoformat()
                            event['survey_id']=db.execute("INSERT INTO meshdata.coverage_surveys(started_at,ended_at,start_row_id,end_row_id,area_id,notes) VALUES(?,?,0,0,'roaming','Phone outing — upload in progress')",(start_iso,start_iso)).lastrowid
                            db.execute('INSERT INTO meshdata.phone_outings VALUES(?,?,?,?,NULL)',(outing_id,event['survey_id'],event['source'],started))
                        end_iso=datetime.fromtimestamp(event['time'],timezone.utc).isoformat()
                        if event['kind']=='outing_end':
                            db.execute('UPDATE meshdata.phone_outings SET ended=? WHERE id=?',(event['time'],outing_id))
                            db.execute("UPDATE meshdata.coverage_surveys SET ended_at=?,notes='Phone outing — ended on phone' WHERE survey_id=?",(end_iso,event['survey_id']))
                        elif not old_outing or not old_outing['ended']:
                            db.execute('UPDATE meshdata.coverage_surveys SET ended_at=max(ended_at,?) WHERE survey_id=?',(end_iso,event['survey_id']))
                    encoded=json.dumps(event,sort_keys=True,separators=(',',':'))
                    old=db.execute('SELECT client,body FROM events WHERE id=?',(event['id'],)).fetchone()
                    # Re-pairing rotates credentials but retains this phone's idempotent outbox.
                    if old and old['body']!=encoded:raise SurveyValidationError('Conflicting record identifier')
                    db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?)',(event['id'],client['id'],event['survey_id'],event['source'],event['kind'],now,encoded))
                db.execute('UPDATE clients SET last_seen=?,status=? WHERE id=?',(now,json.dumps(status),client['id']))
                if active and source in known and status['ready']:
                    grant=db.execute('SELECT * FROM offline_permits WHERE client=? AND survey=? AND source=? AND expires>? ORDER BY expires DESC LIMIT 1',(client['id'],active['survey_id'],source,int(now)+43200)).fetchone()
                    if grant:offline_permit=grant['token'];offline_until=grant['expires']
                    else:
                        offline_permit=secrets.token_urlsafe(32);offline_until=int(now)+86400
                        db.execute('INSERT INTO offline_permits VALUES(?,?,?,?,?,?)',(offline_permit,client['id'],active['survey_id'],source,int(now),offline_until))
            from coverage_areas import AREAS
            return jsonify(ok=True,accepted=[e['id'] for e in normalized],survey_id=active['survey_id'] if active else 0,
                           phone_controls=True, reception_records=True,local_outings=True,offline_permit=offline_permit,offline_until=offline_until,
                           area_name=('Roaming survey' if active['area_id']=='roaming' else AREAS[active['area_id']]['name']) if active else '',lease_seconds=30 if source in known and status['ready'] else 0)
        except SurveyValidationError as error:return jsonify(error=error.public_message),400
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):return jsonify(error='Invalid survey record. Check its identifiers and fields.'),400
    def control(self):
        """Survey-only controls; replay protection is committed with the survey change."""
        from coverage_areas import AREAS
        data=request.get_json(silent=True)
        try:
            if not isinstance(data,dict):raise SurveyValidationError('Expected object')
            command=str(uuid.UUID(data.get('id','')))
            action=data.get('action')
            if action not in ('start','stop'):raise SurveyValidationError('Choose start or stop')
            area='roaming'
            wanted=integer(data.get('survey_id',0),0,2147483647)
            payload=json.dumps(dict(action=action,area_id=area,survey_id=wanted),sort_keys=True)
            with closing(sqlite3.connect(self.mesh,timeout=5)) as db, db:
                db.row_factory=sqlite3.Row
                db.execute('BEGIN IMMEDIATE')
                db.execute('CREATE TABLE IF NOT EXISTS survey_phone_commands(id TEXT PRIMARY KEY,client INTEGER NOT NULL,payload TEXT NOT NULL,result TEXT NOT NULL)')
                old=db.execute('SELECT * FROM survey_phone_commands WHERE id=?',(command,)).fetchone()
                if old:
                    if old['client']!=g.survey_phone_client['id'] or old['payload']!=payload:raise SurveyValidationError('Conflicting command identifier')
                    return jsonify(json.loads(old['result']))
                active=db.execute('SELECT * FROM coverage_surveys WHERE ended_at IS NULL ORDER BY survey_id DESC LIMIT 1').fetchone()
                now=datetime.now(timezone.utc).isoformat()
                row=db.execute('SELECT coalesce(max(row_id),0) FROM packets').fetchone()[0]
                if action=='start':
                    if active:return jsonify(error='A survey is already active. Refresh before starting another.'),409
                    survey=db.execute('INSERT INTO coverage_surveys(started_at,start_row_id,area_id) VALUES(?,?,?)',(now,row,area)).lastrowid
                else:
                    if not active or active['survey_id']!=wanted:return jsonify(error='The active survey changed. Refresh before ending it.'),409
                    survey=wanted
                    db.execute('UPDATE coverage_surveys SET ended_at=?,end_row_id=? WHERE survey_id=?',(now,row,survey))
                result=dict(ok=True,action=action,survey_id=survey)
                db.execute('INSERT INTO survey_phone_commands VALUES(?,?,?,?)',(command,g.survey_phone_client['id'],payload,json.dumps(result)))
            return jsonify(result)
        except (ValueError,TypeError,AttributeError):return jsonify(error='Invalid survey command'),400
    def report(self,survey_id):
        from survey_evidence import summarize
        with self.db() as db:
            db.execute('BEGIN')
            total,last=db.execute('SELECT count(*),max(rowid) FROM events WHERE survey=?',(survey_id,)).fetchone()
            key=(survey_id,total,last)
            with self.report_lock:
                report=self.report_cache.get(key)
                if report is None:
                    rows=db.execute("SELECT body FROM events WHERE survey=? ORDER BY json_extract(body,'$.time'),rowid",(survey_id,))
                    report=summarize(rows,total)
                    self.report_cache[key]=report
                    while len(self.report_cache)>12:self.report_cache.popitem(last=False)
                else:self.report_cache.move_to_end(key)
            client=db.execute('SELECT last_seen FROM clients WHERE revoked=0 ORDER BY id DESC LIMIT 1').fetchone()
        with self.meshdb() as mesh:
            names={r['node_num']:r['name'] for r in mesh.execute("SELECT node_num,coalesce(nullif(long_name,''),nullif(short_name,''),node_id) AS name FROM nodes") if r['name']}
            survey=mesh.execute('SELECT notes FROM coverage_surveys WHERE survey_id=?',(survey_id,)).fetchone()
        status='Phone connected' if client and client['last_seen'] and time.time()-client['last_seen']<45 else 'Phone not connected'
        if survey and survey['notes']=='Phone outing — upload in progress':status+=' · Phone outing still open; displayed end is the latest uploaded observation'
        elif survey and survey['notes']=='Phone outing — ended on phone':status+=' · Outing ended on phone'
        return dict(report,names=names,status=status)


def register_survey_phone(app,root='@@DATA_DIR@@'):
    phone=SurveyPhone(app,root)
    @app.get('/survey-companion')
    def setup():return render_template('survey-companion.html',https_host=app.extensions['dashboard_security'].https_host,
        apk_available=(Path(root)/'dashboard/survey-downloads/meshcrap-survey-test.apk').is_file()),200,{'Cache-Control':'no-store'}
    @app.get('/survey-companion/<name>')
    def artifact(name):
        if name not in ('meshcrap-survey-test.apk','meshcrap-survey-source.zip'):return jsonify(error='Unknown file'),404
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
    @app.post('/api/survey-phone/control')
    def control():
        if not hasattr(g,'survey_phone_client'):return jsonify(error='Phone authentication required'),401
        return phone.control()
    return phone
