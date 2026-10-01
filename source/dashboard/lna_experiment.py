"""Fresh LNA experiment controls and explicitly matched observational comparisons."""
import fcntl, hashlib, json, os, sqlite3, statistics, tempfile, time
from contextlib import closing
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import jsonify, request, session

TZ=ZoneInfo('@@TIMEZONE@@')
OWN='@@RECEIVER_ID@@'

def stamp(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)

def revision(config):
    return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()

def gap_hours(times,start,end,threshold=180):
    """Hours intersecting >3 min without Receiver's regularly emitted self traffic."""
    times=sorted(set([start,end]+[t for t in times if start<=t<=end]))
    hours=set()
    for left,right in zip(times,times[1:]):
        if (right-left).total_seconds()<=threshold:continue
        cur=left.replace(minute=0,second=0,microsecond=0)
        while cur<right:
            hours.add(cur);cur+=timedelta(hours=1)
    return hours

def matched_pairs(timeline):
    states={s:[r for r in timeline if r['comparison_eligible'] and r['lna_state']==s] for s in ('OFF','ON')}
    candidates=[]
    for off in states['OFF']:
        for on in states['ON']:
            a,b=stamp(off['hour']),stamp(on['hour'])
            if a.astimezone(TZ).hour==b.astimezone(TZ).hour:
                candidates.append((abs((a-b).total_seconds()),a,b,off,on))
    used=set();pairs=[]
    for _,a,b,off,on in sorted(candidates,key=lambda x:(x[0],x[1],x[2])):
        if a in used or b in used:continue
        used.update((a,b));pairs.append((off,on))
    return pairs

def summarize(rows):
    def avg(key):
        vals=[r[key] for r in rows if r.get(key) is not None]
        return statistics.mean(vals) if vals else None
    return {'hours':len(rows),'packets_per_hour':avg('packets_per_observed_hour'),
            'direct_per_hour':avg('direct_per_observed_hour'),'rx_bad_share_pct':avg('rx_bad_share_pct')}

def compare_nodes(pairs,packets):
    """Match originating nodes only on direct receptions; SNR on relays is not origin SNR."""
    grouped=defaultdict(list)
    for p in packets:
        if p['hops_used']!=0 or p['rx_snr'] is None or not p['from_id'] or p['from_id']==OWN:continue
        hour=stamp(p['collector_time']).replace(minute=0,second=0,microsecond=0)
        grouped[(hour,p['from_id'])].append(float(p['rx_snr']))
    cells=defaultdict(list)
    for off,on in pairs:
        a,b=stamp(off['hour']),stamp(on['hour'])
        nodes_a={node for h,node in grouped if h==a}
        nodes_b={node for h,node in grouped if h==b}
        for node in nodes_a & nodes_b:
            av,bv=grouped[(a,node)],grouped[(b,node)]
            if min(len(av),len(bv))<3:continue
            cells[node].append((statistics.median(av),statistics.median(bv),len(av),len(bv)))
    result=[]
    for node,values in sorted(cells.items()):
        off=statistics.mean(v[0] for v in values);on=statistics.mean(v[1] for v in values)
        result.append({'node':node,'matched_hours':len(values),'off_snr':off,'on_snr':on,
                       'delta_snr':on-off,'off_packets':sum(v[2] for v in values),'on_packets':sum(v[3] for v in values)})
    return result

def register_lna_experiment(app,db_path):
    root=Path(db_path).parent
    config_path=root/'reports'/'lna-experiment.json'
    def config():return json.loads(config_path.read_text())
    def reply(data,status=200):
        r=jsonify(data);r.headers['Cache-Control']='no-store';return r,status

    @app.get('/api/lna-experiment')
    def lna_state():
        c=config()
        return reply(dict(c,revision=revision(c),unlocked=session.get('radio_until',0)>time.time()))

    @app.post('/api/lna-experiment/state')
    def lna_transition():
        if session.get('radio_until',0)<=time.time():return reply({'error':'Unlock controls first.'},401)
        if request.headers.get('Origin')!=request.host_url.rstrip('/') or not request.is_json:
            return reply({'error':'Use the controls on this dashboard.'},403)
        if request.content_length is None or request.content_length>4096:return reply({'error':'Invalid request size.'},413)
        body=request.get_json(silent=True)
        if not isinstance(body,dict) or body.get('state') not in ('ON','OFF') or body.get('physical_change_confirmed') is not True:
            return reply({'error':'Confirm the physical LNA state before recording it.'},400)
        with (config_path.with_suffix('.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            c=config()
            if body.get('revision')!=revision(c):return reply({'error':'The state changed in another session. Refresh and check it.'},409)
            if c['transitions'][-1]['state']==body['state']:
                return reply({'changed':False,'experiment':c,'revision':revision(c)})
            now=datetime.now(timezone.utc)
            if now<=stamp(c['transitions'][-1]['time_utc']):return reply({'error':'Clock moved backwards; check Pi time.'},409)
            backup=root/'backups'/'lna-transitions';backup.mkdir(parents=True,exist_ok=True)
            (backup/(now.strftime('%Y%m%dT%H%M%S.%fZ')+'.json')).write_text(json.dumps(c,indent=2))
            c['transitions'].append({'time_utc':now.isoformat(),'state':body['state'],'basis':'Physical state confirmed in dashboard'})
            fd,temp=tempfile.mkstemp(prefix='.lna-',dir=config_path.parent)
            try:
                with os.fdopen(fd,'w') as f:
                    json.dump(c,f,indent=2);f.flush();os.fsync(f.fileno())
                os.chmod(temp,config_path.stat().st_mode & 0o777)
                os.replace(temp,config_path)
            finally:
                if os.path.exists(temp):os.unlink(temp)
        return reply({'changed':True,'experiment':c,'revision':revision(c)})

    @app.get('/api/lna-analysis')
    def lna_analysis():
        # Use the exact eligibility rules used by the hourly chart.
        data=app.view_functions['rf_health_hourly']().get_json()
        pairs=matched_pairs(data['timeline'])
        packets=[]
        if pairs:
            wanted={stamp(r['hour']) for pair in pairs for r in pair}
            with closing(sqlite3.connect('file:'+str(db_path)+'?mode=ro',uri=True)) as conn:
                conn.row_factory=sqlite3.Row
                diagnostic_ids=set()
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='pki_jobs'").fetchone():
                    diagnostic_ids={r[0] for r in conn.execute('SELECT packet_id FROM pki_jobs WHERE requested_at>=? AND packet_id IS NOT NULL',(min(wanted).timestamp()-3600,))}
                rows=conn.execute("SELECT collector_time,from_id,rx_snr,hops_used,raw_json FROM packets WHERE observation_type='LIVE' AND collector_time>=? AND collector_time<? AND hops_used=0 AND rx_snr IS NOT NULL AND from_id!=?",(min(wanted).isoformat(),(max(wanted)+timedelta(hours=1)).isoformat(),OWN))
                for r in rows:
                    if stamp(r['collector_time']).replace(minute=0,second=0,microsecond=0) not in wanted:continue
                    try:polled=json.loads(r['raw_json'] or '{}').get('decoded',{}).get('requestId') in diagnostic_ids
                    except (ValueError,TypeError):polled=False
                    if not polled:packets.append(dict(r))
        nodes=compare_nodes(pairs,packets)
        return reply({'generated':datetime.now(timezone.utc).isoformat(),'paired_hours':len(pairs),
                      'off':summarize([a for a,b in pairs]),'on':summarize([b for a,b in pairs]),
                      'nodes':nodes,'node_balanced_delta_snr':statistics.mean(r['delta_snr'] for r in nodes) if nodes else None,
                      'method':'Nearest-date one-to-one hours at the same @@TIMEZONE@@ clock hour. Signal comparison requires the same direct node and at least 3 SNR packets in each matched hour; nodes have equal weight.',
                      'limitations':'Observational comparison: weather, traffic, node movement and unobserved packets can still bias results. No significance claim.',
                      'pairs':[{'off':a['hour'],'on':b['hour']} for a,b in pairs]})
