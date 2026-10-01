"""Read-only LNA context from independently measured remote receivers."""
import json,math,sqlite3,time
from contextlib import closing
from datetime import datetime,timezone
from flask import jsonify,request

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def points_for(rows,transitions):
    points=[];previous=None
    for row in rows:
        data=json.loads(row['payload_json']);ts=row['observed_at']
        if ts is None:continue
        uptime=data.get('uptime_seconds');noise=data.get('noise_floor')
        point=dict(time=datetime.fromtimestamp(ts,timezone.utc).isoformat(),timestamp=ts,
                   noise_dbm=noise if number(noise) and -160<=noise<0 else None,
                   rx_per_hour=None,relay_per_hour=None,bad_per_hour=None,
                   uptime_seconds=uptime,warmup=not number(uptime) or uptime<900,
                   state=next((x['state'] for x in reversed(transitions) if x['timestamp']<=ts),None))
        if previous and not point['warmup']:
            old,oldts=previous;du=uptime-old.get('uptime_seconds',uptime) if number(uptime) and number(old.get('uptime_seconds')) else 0
            dt=ts-oldts
            continuous=0<dt<=2700 and du>0 and abs(du-dt)<=max(120,dt*.2) and old.get('uptime_seconds',0)>=900
            if continuous:
                for key,out in [('num_packets_rx','rx_per_hour'),('num_tx_relay','relay_per_hour'),('num_packets_rx_bad','bad_per_hour')]:
                    a,b=old.get(key),data.get(key)
                    if number(a) and number(b) and b>=a:point[out]=(b-a)*3600/du
        points.append(point);previous=(data,ts)
    return points

def register_pki(app,db_path):
    @app.get('/api/lna-remote')
    def lna_remote():
        try:hours=max(1,min(720,int(request.args.get('hours',24))))
        except (ValueError,TypeError):hours=24
        now=time.time();start=now-hours*3600
        transitions=[]
        try:
            for x in json.loads((db_path.parent/'reports/lna-experiment.json').read_text())['transitions']:
                transitions.append(dict(state=x['state'],timestamp=datetime.fromisoformat(x['time_utc']).timestamp()))
            transitions.sort(key=lambda x:x['timestamp'])
        except (OSError,ValueError,KeyError):pass
        with closing(sqlite3.connect('file:'+str(db_path)+'?mode=ro',uri=True,timeout=5)) as c:
            c.row_factory=sqlite3.Row
            if not c.execute("SELECT 1 FROM sqlite_master WHERE name='pki_samples'").fetchone():
                return jsonify(hours=hours,nodes=[],enabled=False)
            targets=c.execute("SELECT node_num,node_id,long_name,short_name FROM nodes WHERE role='CLIENT' AND (lower(long_name) LIKE '@@NODE_PREFIX_LOWER@@%' OR lower(short_name) LIKE '@@NODE_PREFIX_LOWER@@%') ORDER BY long_name").fetchall()
            nodes=[]
            for n in targets:
                num=n['node_num']
                rows=c.execute("SELECT * FROM pki_samples WHERE node_num=? AND kind='local_stats' AND observed_at>=? AND observed_at<=? ORDER BY observed_at",(num,start,now)).fetchall()
                points=points_for(rows,transitions)
                latest=c.execute("SELECT * FROM pki_samples WHERE node_num=? AND kind='local_stats' ORDER BY observed_at DESC LIMIT 1",(num,)).fetchone()
                configs={}
                for kind in ('lora','device','metadata','channel_0','channel_1','device_metrics'):
                    row=c.execute('SELECT * FROM pki_samples WHERE node_num=? AND kind=? ORDER BY received_at DESC LIMIT 1',(num,kind)).fetchone()
                    if row:configs[kind]=dict(data=json.loads(row['payload_json']),received_at=row['received_at'])
                recent=c.execute('SELECT kind,status,requested_at,received_at,error FROM pki_jobs WHERE node_num=? ORDER BY requested_at DESC LIMIT 1',(num,)).fetchone()
                next_at=c.execute('SELECT MIN(next_at) FROM pki_schedule WHERE node_num=?',(num,)).fetchone()[0]
                last_success=c.execute('SELECT MAX(received_at) FROM pki_samples WHERE node_num=?',(num,)).fetchone()[0]
                sample=json.loads(latest['payload_json']) if latest else None
                age=now-latest['observed_at'] if latest and latest['observed_at'] else None
                nodes.append(dict(id=n['node_id'] or f'!{num:08x}',name=n['long_name'] or n['short_name'],points=points,
                    latest=sample,latest_at=latest['observed_at'] if latest else None,
                    latest_in_window=bool(latest and latest['observed_at'] and start<=latest['observed_at']<=now),
                    age_seconds=age,stale=age is None or age>2700,configs=configs,
                    last_success=last_success,last_request=dict(recent) if recent else None,next_attempt_at=next_at))
            requests=c.execute('SELECT COUNT(*) FROM pki_jobs WHERE requested_at>=?',(start,)).fetchone()[0]
            samples=c.execute('SELECT COUNT(*) FROM pki_samples WHERE received_at>=?',(start,)).fetchone()[0]
            pending=c.execute("SELECT COUNT(*) FROM pki_jobs WHERE status IN ('waiting','acknowledged')").fetchone()[0]
        result=jsonify(enabled=True,hours=hours,start=start,generated=now,nodes=nodes,requests=requests,responses=samples,pending=pending,
            cadence=dict(minimum_request_seconds=60,response_wait_seconds=300,local_stats_seconds=900,configuration_seconds=86400,maximum_retry_seconds=21600))
        result.headers['Cache-Control']='no-store';return result
