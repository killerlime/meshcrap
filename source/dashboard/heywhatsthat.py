"""Opt-in, user-triggered HeyWhatsThat PNG profiles; no background requests."""
from contextlib import contextmanager
import hashlib
import json
import math
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path
from flask import jsonify, request, Response

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def profile_query(data):
    values=[]
    for name,lo,hi in [('lat1',-54,60),('lon1',-180,180),('lat2',-54,60),('lon2',-180,180),('height1',0,1000),('height2',0,1000)]:
        value=data.get(name)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:
            raise ValueError('Check coordinates (SRTM latitude range -54 to 60) and antenna heights (0–1000 m).')
        values.append(value)
    a,b,c,d,h,j=values
    if a==c and b==d:raise ValueError('Choose two different locations.')
    return {'pt0':f'{a:.6f},{b:.6f},ff0000,{h:.2f},000000','pt1':f'{c:.6f},{d:.6f},end,{j:.2f},000000',
            'axes':'1','metric':'1','groundrelative':'1','curvature':'1','width':'1000','height':'300','src':'meshcrap-experiment'}

def register_heywhatsthat(app, main_db):
    directory=Path(main_db).parent
    config=directory/'heywhatsthat-config.json'
    ledger=directory/'heywhatsthat-usage.sqlite3'
    def enabled():
        try:return json.loads(config.read_text()).get('enabled') is True
        except (OSError,ValueError,AttributeError):return False
    @contextmanager
    def connect():
        db=sqlite3.connect(ledger,timeout=5)
        db.execute('CREATE TABLE IF NOT EXISTS daily(day INTEGER PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, successes INTEGER NOT NULL DEFAULT 0, hits INTEGER NOT NULL DEFAULT 0)')
        db.execute('CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, created REAL, png BLOB)')
        db.execute('CREATE TABLE IF NOT EXISTS throttle(id INTEGER PRIMARY KEY, last REAL)')
        db.commit()
        try:
            with db:yield db
        finally:db.close()
    @app.get('/api/heywhatsthat/usage')
    def usage():
        if not enabled():return jsonify(enabled=False)
        day=int(time.time()//86400)
        with connect() as db:
            rows=db.execute('SELECT day,attempts,successes,hits FROM daily').fetchall()
        totals={str(n):{'attempts':sum(r[1] for r in rows if r[0]>day-n),'successes':sum(r[2] for r in rows if r[0]>day-n),'cache_hits':sum(r[3] for r in rows if r[0]>day-n)} for n in (1,7,30)}
        return jsonify(enabled=True,windows=totals,local_daily_cap=20,provider_quota=None,contact_reminder='Contact HeyWhatsThat before regular production use; no numeric provider quota is published.')
    @app.post('/api/heywhatsthat/profile')
    def profile():
        # Custom header + JSON prevents cross-origin form submissions; never allow CORS.
        if request.headers.get('X-Requested-With')!='meshcrap-terrain' or request.headers.get('Sec-Fetch-Site')=='cross-site':
            return jsonify(error='Use the dashboard terrain form.'),403
        if not enabled():return jsonify(error='HeyWhatsThat is disabled in local settings.'),403
        if (request.content_length or 0)>2048:return jsonify(error='Request too large.'),413
        data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Expected terrain parameters.'),400
        try:params=profile_query(data)
        except ValueError as exc:return jsonify(error=str(exc)),400
        query=urllib.parse.urlencode(params);key=hashlib.sha256(query.encode()).hexdigest();now=time.time();day=int(now//86400)
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            cached=db.execute('SELECT png FROM cache WHERE key=? AND created>?',(key,now-30*86400)).fetchone()
            db.execute('INSERT OR IGNORE INTO daily(day) VALUES(?)',(day,))
            if cached:
                db.execute('UPDATE daily SET hits=hits+1 WHERE day=?',(day,))
                return Response(cached[0],mimetype='image/png',headers={'Cache-Control':'no-store','X-Terrain-Cache':'hit'})
            count=db.execute('SELECT attempts FROM daily WHERE day=?',(day,)).fetchone()[0]
            last=db.execute('SELECT last FROM throttle WHERE id=1').fetchone()
            if count>=20:return jsonify(error='Local experiment cap of 20 requests per UTC day reached. This is not a provider allowance; contact HeyWhatsThat before increasing usage.'),429
            if last and now-last[0]<30:return jsonify(error='Wait 30 seconds between new terrain requests.'),429
            db.execute('UPDATE daily SET attempts=attempts+1 WHERE day=?',(day,))
            db.execute('INSERT OR REPLACE INTO throttle VALUES(1,?)',(now,))
        try:
            req=urllib.request.Request('https://profile.heywhatsthat.com/bin/profile.cgi?'+query,headers={'User-Agent':'meshcrap-terrain-experiment/1.0'})
            with urllib.request.build_opener(NoRedirect).open(req,timeout=20) as response:
                png=response.read(2_000_001)
                if response.headers.get_content_type()!='image/png' or not png.startswith(b'\x89PNG\r\n\x1a\n') or len(png)>2_000_000:raise ValueError('Invalid profile')
        except Exception:
            return jsonify(error='Terrain provider unavailable or returned an invalid image. No automatic retry was made.'),502
        with connect() as db:
            db.execute('UPDATE daily SET successes=successes+1 WHERE day=?',(day,))
            db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(key,now,png))
            db.execute('DELETE FROM cache WHERE created<?',(now-30*86400,))
            db.execute('DELETE FROM cache WHERE key NOT IN (SELECT key FROM cache ORDER BY created DESC LIMIT 32)')
        return Response(png,mimetype='image/png',headers={'Cache-Control':'no-store','X-Terrain-Cache':'miss'})
