from contextlib import closing
"""Weather Underground observations associated with HQ; never mesh packets."""
import json, math, sqlite3, time, threading, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path('@@DATA_DIR@@')
DATABASE=ROOT/'weather.sqlite3'
KEY=ROOT/'weather-api-key'
STATION='@@WEATHER_STATION@@'
NODE='@@RECEIVER_ID@@'
INTERVAL=300
STALE=900

def iso(epoch):
    return datetime.fromtimestamp(epoch,timezone.utc).isoformat()

def initialize():
    with closing(sqlite3.connect(DATABASE,timeout=5)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS observations(station TEXT NOT NULL, observed INTEGER NOT NULL, fetched INTEGER NOT NULL, temperature REAL, humidity REAL, pressure REAL, quality INTEGER, PRIMARY KEY(station,observed))')
        db.execute('CREATE TABLE IF NOT EXISTS fetch_status(id INTEGER PRIMARY KEY CHECK(id=1), attempted INTEGER, success INTEGER, error TEXT)')
    DATABASE.chmod(0o600)

def normalize(data, now):
    rows=data.get('observations',[])
    if len(rows)!=1 or rows[0].get('stationID')!=STATION:raise ValueError('Station identity mismatch')
    o=rows[0];stamp=o.get('epoch');metric=o.get('metric') or {}
    if type(stamp) not in (int,float) or not math.isfinite(stamp) or stamp<=0 or stamp>now+120:raise ValueError('Invalid observation time')
    if o.get('qcStatus')==-1:raise ValueError('Station observation failed quality control')
    def number(value,low,high):
        if value is None:return None
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError('Invalid weather measurement')
        return float(value)
    values=(number(metric.get('temp'),-100,70),number(o.get('humidity'),0,100),number(metric.get('pressure'),300,1200))
    if all(x is None for x in values):raise ValueError('No weather measurements available')
    return (STATION,int(stamp),int(now),*values,o.get('qcStatus'))

def collect_once():
    now=int(time.time());error=None
    try:
        key=KEY.read_text().strip()
        query=urllib.parse.urlencode(dict(stationId=STATION,format='json',units='m',numericPrecision='decimal',apiKey=key))
        req=urllib.request.Request('https://api.weather.com/v2/pws/observations/current?'+query,headers={'Accept':'application/json'})
        # Disable redirects so the key cannot be forwarded to another destination.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as r:
            row=normalize(json.loads(r.read(65536)),now)
        with closing(sqlite3.connect(DATABASE,timeout=5)) as db, db:
            db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?)',row)
            db.execute('INSERT INTO fetch_status VALUES(1,?,?,NULL) ON CONFLICT(id) DO UPDATE SET attempted=excluded.attempted,success=excluded.success,error=NULL',(now,now))
    except urllib.error.HTTPError as exc:error='Weather service HTTP '+str(exc.code)
    except Exception as exc:error=type(exc).__name__ # Never log credential-bearing URLs.
    if error:
        with closing(sqlite3.connect(DATABASE,timeout=5)) as db, db:
            db.execute('INSERT INTO fetch_status(id,attempted,error) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET attempted=excluded.attempted,error=excluded.error',(now,error))

def latest():
    try:
        with closing(sqlite3.connect('file:'+str(DATABASE)+'?mode=ro',uri=True,timeout=2)) as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT * FROM observations WHERE station=? ORDER BY observed DESC LIMIT 1',(STATION,)).fetchone()
            status=db.execute('SELECT * FROM fetch_status WHERE id=1').fetchone()
    except sqlite3.Error:return dict(available=False,source='Weather Underground',station_id=STATION,error='Weather storage unavailable')
    result=dict(available=bool(row),source='AcuRite Atlas via Weather Underground',station_id=STATION,node_id=NODE,
                poll_seconds=INTERVAL,error=status['error'] if status else None)
    if row:
        age=max(0,int(time.time())-row['observed'])
        result.update(observed_at=iso(row['observed']),received_at=iso(row['fetched']),age_seconds=age,stale=age>STALE,
          values=dict(temperature=row['temperature'],relativeHumidity=row['humidity'],barometricPressure=row['pressure']),
          pressure_basis='As reported by Weather Underground; not converted to station pressure')
    return result

def register_weather(app):
    from flask import jsonify, request
    @app.get('/api/hq-weather')
    def weather():return jsonify(latest())
    @app.after_request
    def attach_weather(response):
        if request.path!='/api/telemetry' or response.status_code!=200:return response
        data=response.get_json(silent=True)
        if not data or (data.get('node') or {}).get('node_id')!=NODE:return response
        weather=latest()
        if weather.get('available'):
            details=data.setdefault('details',{})
            if details.get('environment'):details['environment_radio']=details['environment']
            details['environment']=weather
            response.set_data(app.json.dumps(data))
        return response

def start_weather():
    def run():
        import fcntl
        with (ROOT/'weather-poll.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return
            initialize()
            while True:
                try:collect_once()
                except Exception:pass # Keep the dashboard and RF collection independent.
                time.sleep(INTERVAL)
    threading.Thread(target=run,name='hq-weather',daemon=True).start()
