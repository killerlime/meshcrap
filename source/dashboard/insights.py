"""Read-only, deterministic mesh observations for the Insights tab."""
import json,sqlite3,statistics,threading,time
from collections import Counter,defaultdict
from contextlib import closing
from datetime import datetime,timezone,timedelta
from pathlib import Path
from flask import jsonify,request
OWN=@@RECEIVER_NUM@@
EXCLUDE={'ROUTING_APP','ADMIN_APP','TRACEROUTE_APP'}
def dt(v):return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc)
def receiver_num(row):return @@RECEIVER_NUM@@ if row.get('receiver_id')=='@@RECEIVER_ID@@' else @@RECEIVER_NUM@@

def summarize(rows):
 traffic=[r for r in rows if r['from_num'] not in (None,receiver_num(r)) and r['portnum'] and r['portnum'] not in EXCLUDE]
 direct=[r for r in traffic if r['hops_used']==0]
 snrs=[r['rx_snr'] for r in direct if r['rx_snr'] is not None]
 return {'packets':len(traffic),'nodes':len({r['from_num'] for r in traffic}),'direct':len(direct),'relayed':sum(r['hops_used'] is not None and r['hops_used']>0 for r in traffic),'unknown_hops':sum(r['hops_used'] is None for r in traffic),'direct_median_snr':statistics.median(snrs) if snrs else None,'mix':dict(Counter(r['portnum'] for r in traffic))}
def analyze(rows,now,hours,names):
 start=now-timedelta(hours=hours);previous_start=start-timedelta(hours=hours)
 parsed=[(r,dt(r['collector_time'])) for r in rows]
 current=[r for r,t in parsed if start<=t<=now];previous=[r for r,t in parsed if previous_start<=t<start]
 a,b=summarize(current),summarize(previous)
 def quality(rr,left,right):
  minutes={dt(r['collector_time']).replace(second=0,microsecond=0) for r in rr if r['from_num']==receiver_num(r)}
  expected=max(1,(right-left).total_seconds()/60)
  return min(100,100*len(minutes)/expected)
 step=300 if hours<=1 else 900 if hours<=6 else 3600 if hours<=24 else 21600 if hours<=168 else 86400
 buckets=defaultdict(list)
 for r,t in parsed:
  if start<=t<=now:buckets[min(int((t-start).total_seconds()//step),int((now-start).total_seconds()-1)//step)].append(r)
 bins=[];cursor=start
 while cursor<now:
  end=min(now,cursor+timedelta(seconds=step));rr=buckets[len(bins)];summary=summarize(rr)
  bins.append({'time':cursor.isoformat(),'end':end.isoformat(),'packets':summary['packets'],'nodes':summary['nodes'],'direct':summary['direct'],'observed_pct':round(quality(rr,cursor,end),1)});cursor=end
 groups=[defaultdict(list),defaultdict(list)]
 for group,rr in zip(groups,(current,previous)):
  for r in rr:
   if r['from_num'] not in (None,receiver_num(r)) and r['portnum'] and r['portnum'] not in EXCLUDE:group[r['from_num']].append(r)
 def identity(num):
  n=names.get(num,{})
  return {'id':f'!{num:08x}','name':n.get('long_name') or n.get('short_name') or f'!{num:08x}'}
 leaders=[];signals=[];quiet=[];new=[]
 for num,rr in groups[0].items():
  direct=[r['rx_snr'] for r in rr if r['hops_used']==0 and r['rx_snr'] is not None];before=[r['rx_snr'] for r in groups[1].get(num,[]) if r['hops_used']==0 and r['rx_snr'] is not None]
  leaders.append(dict(identity(num),packets=len(rr),direct_samples=len(direct),median_snr=statistics.median(direct) if direct else None,last_seen=max(r['collector_time'] for r in rr)))
  if len(direct)>=3 and len(before)>=3:signals.append(dict(identity(num),current=statistics.median(direct),previous=statistics.median(before),delta=statistics.median(direct)-statistics.median(before),samples=len(direct),previous_samples=len(before)))
  if num not in groups[1]:new.append(dict(identity(num),packets=len(rr)))
 for num,rr in groups[1].items():
  if len(rr)>=3 and num not in groups[0]:quiet.append(dict(identity(num),previous_packets=len(rr),last_seen=max(r['collector_time'] for r in rr)))
 a['observed_pct']=round(quality(current,start,now),1);b['observed_pct']=round(quality(previous,previous_start,start),1)
 return {'generated':now.isoformat(),'hours':hours,'start':start.isoformat(),'previous_start':previous_start.isoformat(),'current':a,'previous':b,'bins':bins,'leaders':sorted(leaders,key=lambda r:-r['packets'])[:12],'signals':sorted(signals,key=lambda r:-abs(r['delta']))[:12],'quiet':sorted(quiet,key=lambda r:-r['previous_packets'])[:12],'newly_heard':sorted(new,key=lambda r:-r['packets'])[:12],'newly_heard_count':len(new),'quiet_count':len(quiet)}
def register_insights(app,db_path,startup_windows,startup_filter):
 cache={};lock=threading.Lock()
 @app.get('/api/insights/channels')
 def insights_channels():
  config=json.loads(Path(__file__).with_name('messages_config.json').read_text())
  response=jsonify(channels=config['channels'],channel=config['channel'])
  response.headers['Cache-Control']='no-store';return response
 @app.get('/api/insights')
 def insights():
  try:hours=max(1,min(720,int(request.args.get('hours',24))))
  except (ValueError,TypeError):hours=24
  with lock:
   cached=cache.get(hours)
   if cached and time.monotonic()-cached[0]<55:data=cached[1]
   else:
    now=datetime.now(timezone.utc);start=now-timedelta(hours=hours*2)
    with closing(sqlite3.connect('file:'+str(db_path)+'?mode=ro',uri=True,timeout=5)) as c:
     c.row_factory=sqlite3.Row
     filt,params=startup_filter(startup_windows(c))
     rows=[dict(r) for r in c.execute(f"""SELECT collector_time,from_num,portnum,hops_used,rx_snr, COALESCE(json_extract(CASE WHEN json_valid(raw_json) THEN raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@') receiver_id FROM packets p
      WHERE observation_type='LIVE' AND collector_time>=? AND collector_time<=? AND ({filt})
      AND (from_num=CASE WHEN json_extract(CASE WHEN json_valid(raw_json) THEN raw_json ELSE NULL END,'$._collectorReceiverId')='@@RECEIVER_ID@@' THEN {OWN} ELSE @@RECEIVER_NUM@@ END OR (COALESCE(transport,'') NOT IN ('TRANSPORT_MQTT','TRANSPORT_INTERNAL')
       AND CASE WHEN json_valid(raw_json) THEN COALESCE(json_extract(raw_json,'$.viaMqtt'),0) ELSE 0 END=0
       AND (transport='TRANSPORT_LORA' OR rx_snr IS NOT NULL OR rx_rssi IS NOT NULL)))
      ORDER BY collector_time""",[start.isoformat(),now.isoformat()]+params)]
     names={r['node_num']:dict(r) for r in c.execute('SELECT node_num,long_name,short_name FROM nodes')}
     events=[dict(r) for r in c.execute("SELECT event_time,event_type,message FROM collector_events WHERE event_time>=? AND event_type IN ('START','STOP','CONNECTED','CONNECTION_ERROR','WEB_CONFIG_SUBMITTED','CHANNEL_ORDER_CHANGED') ORDER BY event_id DESC LIMIT 10",((now-timedelta(hours=hours)).isoformat(),))]
    data=analyze(rows,now,hours,names);data['events']=events
    if len(cache)>8:cache.clear()
    cache[hours]=(time.monotonic(),data)
  response=jsonify(data);response.headers['Cache-Control']='no-store';return response
