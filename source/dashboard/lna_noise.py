"""Receiver noise-floor trend and equally weighted matched-hour comparisons."""
import json,sqlite3,statistics,math
from contextlib import closing
from datetime import datetime,timezone,timedelta
from collections import defaultdict
from flask import jsonify,request
from lna_experiment import stamp,matched_pairs

def extract(rows,transitions):
    points=[];seen=set()
    for row in rows:
        try:
            raw=json.loads(row['raw_json']);t=raw.get('decoded',{}).get('telemetry',{});s=t.get('localStats',{})
            value=s.get('noiseFloor');uptime=s.get('uptimeSeconds');ts=t.get('time')
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not -160<=value<0:continue
            received=stamp(row['collector_time'])
            # Exclude cached/replayed telemetry; no invented sample timestamps.
            if not isinstance(ts,(int,float)) or abs(received.timestamp()-ts)>120:continue
            key=(ts,uptime)
            if key in seen:continue
            seen.add(key)
            measured=datetime.fromtimestamp(ts,timezone.utc)
            state=next((x['state'] for x in reversed(transitions) if stamp(x['time_utc'])<=measured),None)
            points.append({'time':measured.isoformat(),'noise_dbm':value,'uptime_seconds':uptime,'state':state,'warmup':not isinstance(uptime,(int,float)) or uptime<900})
        except (ValueError,TypeError,KeyError,OverflowError):continue
    return sorted(points,key=lambda p:p['time'])

def comparison(points,pairs):
    byhour=defaultdict(list)
    for p in points:
        if not p['warmup']:byhour[stamp(p['time']).replace(minute=0,second=0,microsecond=0)].append(p)
    result=[]
    for off,on in pairs:
        groups=[byhour[stamp(r['hour'])] for r in (off,on)]
        if any(len(g)<3 or (stamp(g[-1]['time'])-stamp(g[0]['time'])).total_seconds()<1800 or any((stamp(b['time'])-stamp(a['time'])).total_seconds()>1200 for a,b in zip(g,g[1:])) for g in groups):continue
        a,b=[statistics.median(p['noise_dbm'] for p in g) for g in groups]
        result.append({'off_hour':off['hour'],'on_hour':on['hour'],'off_dbm':a,'on_dbm':b,'delta_db':b-a})
    return {'paired_hours':len(result),'off_dbm':statistics.mean(r['off_dbm'] for r in result) if result else None,'on_dbm':statistics.mean(r['on_dbm'] for r in result) if result else None,'delta_db':statistics.mean(r['delta_db'] for r in result) if result else None}

def register_lna_noise(app,db_path):
    @app.get('/api/lna-noise')
    def lna_noise():
        now=datetime.now(timezone.utc)
        config=json.loads((db_path.parent/'reports'/'lna-experiment.json').read_text())
        try: hours=max(1,min(720,int(request.args.get('hours',24))))
        except (ValueError,TypeError): hours=24
        start=max(now-timedelta(hours=hours),stamp(config['start_utc']))
        with closing(sqlite3.connect('file:'+str(db_path)+'?mode=ro',uri=True)) as c:
            c.row_factory=sqlite3.Row
            rows=c.execute("SELECT collector_time,raw_json FROM packets WHERE from_num=? AND portnum='TELEMETRY_APP' AND collector_time>=? AND raw_json LIKE '%localStats%' ORDER BY row_id",(@@RECEIVER_NUM@@,start.isoformat())).fetchall()
        points=[p for p in extract(rows,config['transitions']) if start<=stamp(p['time'])<=now]
        data=app.view_functions['rf_health_hourly']().get_json()
        matched=comparison(points,matched_pairs(data['timeline']))
        intervals=[(stamp(b['time'])-stamp(a['time'])).total_seconds() for a,b in zip(points[-11:],points[-10:])] if len(points)>10 else [(stamp(b['time'])-stamp(a['time'])).total_seconds() for a,b in zip(points,points[1:])]
        latest=points[-1] if points else None
        age=(now-stamp(latest['time'])).total_seconds() if latest else None
        response=jsonify(hours=hours,start=start.isoformat(),generated=now.isoformat(),points=points,latest=latest,age_seconds=age,stale=age is None or age>1200,median_interval_seconds=statistics.median(intervals) if intervals else None,matched=matched,target_interval_seconds=900)
        response.headers['Cache-Control']='no-store';return response
