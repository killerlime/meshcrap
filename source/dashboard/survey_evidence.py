"""Summarize all companion records; map limits never limit statistical totals."""
import json, math
from collections import Counter, defaultdict

def miles(a,b):
    x,y=map(math.radians,(a['lat'],b['lat']))
    h=math.sin((y-x)/2)**2+math.cos(x)*math.cos(y)*math.sin(math.radians(b['lon']-a['lon'])/2)**2
    return 3958.7613*2*math.asin(math.sqrt(min(1,max(0,h))))

def precise(p,observed):
    return bool(p and 0<=observed-p['time']<=120 and p.get('source')=='phone_gps'
                and 0<=p.get('accuracy_m',float('inf'))<=100)

def summarize(rows,total):
    counts=Counter(); outcomes=Counter(); traces={}; previous={}; fixes=set()
    routes=defaultdict(list); segments={}; distance=0.; gaps=0; rejected=0
    heard=set(); channels=Counter(); evidence=[]; rx_seen=set()
    # A uniform display stride covers the entire trip, not only the tail.
    stride=max(1,math.ceil(total/2000)); displayed=0
    for row in rows:
        e=json.loads(row['body']);kind=e['kind'];counts[kind]+=1
        p=e.get('position');source=e['source'];at=e.get('requested_at',e['time'])
        if kind=='trace':
            key=(source,e['channel'],e['packet_id'],e['requested_at'])
            rank={'requested':0,'stopped':1,'transport_error':1,'routing_error':1,'timeout':1,'success':2,'late_success':2}
            if key not in traces or rank[e['status']]>rank[traces[key]['status']]:traces[key]=e
        elif kind=='reception':
            key=(source,e['sender'],e['packet_id'],e['channel'],e.get('rx_time',e['time']))
            if key in rx_seen:continue
            rx_seen.add(key);heard.add(e['sender']);channels[e['channel']]+=1
            if precise(p,e.get('rx_time',e['time'])) and abs(p['time']-e.get('rx_time',e['time']))<=15 and len(evidence)<500:
                evidence.append(dict(lat=p['lat'],lon=p['lon'],kind='heard',time=e['time'],channel=e['channel']))
        elif kind=='position':
            key=(source,p['time'],p['lat'],p['lon'])
            if key in fixes:counts['repeated_fix']+=1;continue
            fixes.add(key)
            if not precise(p,e['time']):
                counts['approximate_fix']+=1;previous.pop(source,None);segments.pop(source,None);continue
            counts['precise_fix']+=1;old=previous.get(source);join=False
            if old:
                seconds=p['time']-old['time'];d=miles(old,p)
                join=0<seconds<=120 and d*3600/seconds<=120
                if join:
                    # Ignore movement smaller than the combined reported uncertainty.
                    if d*1609.344>old.get('accuracy_m',0)+p.get('accuracy_m',0):distance+=d
                else:gaps+=1;rejected+=int(seconds>0 and d*3600/seconds>120)
            if not join or source not in segments:
                segments[source]=[];routes[source].append(segments[source])
            displayed+=1
            if not segments[source] or displayed%stride==0:segments[source].append([p['lat'],p['lon']])
            previous[source]=p
    ordered=sorted(traces.values(),key=lambda e:e['requested_at'],reverse=True)
    destinations=set();located=0;tested=set();by_channel=defaultdict(Counter)
    for e in ordered:
        status=e['status'];outcomes[status]+=1;destinations.add(e['destination']);by_channel[e['channel']][status]+=1
        p=e.get('position')
        if precise(p,e['requested_at']):
            located+=1;tested.add((math.floor(p['lat']*69),math.floor(p['lon']*69*math.cos(math.radians(p['lat'])))))
            if len(evidence)<1000:evidence.append(dict(lat=p['lat'],lon=p['lon'],kind='reply' if status in ('success','late_success') else 'no_reply' if status=='timeout' else 'other',time=e['requested_at'],channel=e['channel']))
    replies=outcomes['success']+outcomes['late_success']
    concluded=replies+outcomes['timeout']+outcomes['routing_error']
    return dict(traces=ordered[:100],trace_count=len(ordered),successes=replies,
        routes=[dict(node_num=n,node=f'Phone survey !{n:08x}',segments=s,samples=sum(len(a) for a in s),simplified=stride>1) for n,s in routes.items()],
        evidence=evidence,metrics=dict(records=total,position_records=counts['position'],unique_fixes=len(fixes),
          precise_fixes=counts['precise_fix'],approximate_fixes=counts['approximate_fix'],repeated_fixes=counts['repeated_fix'],
          reliable_distance_miles=distance,recording_gaps=gaps,rejected_jumps=rejected,
          requests=len(ordered),replies=replies,late_replies=outcomes['late_success'],no_reply=outcomes['timeout'],
          incomplete=outcomes['requested'],local_failures=outcomes['transport_error']+outcomes['stopped'],routing_errors=outcomes['routing_error'],
          reply_fraction=replies/concluded if concluded else None,small_sample=concluded<20,
          destinations=len(destinations),located_requests=located,approximate_test_cells=len(tested),
          received_packets=len(rx_seen),heard_nodes=len(heard),receptions_by_channel=dict(channels),
          outcomes_by_channel={c:dict(v) for c,v in by_channel.items()},all_records_included=True,
          note='Replies demonstrate reachability, possibly through relays. No reply is not proof of no coverage. Only GPS fixes ≤2 minutes old and ≤100 m reported accuracy locate evidence. Radio GPS with unknown accuracy stays approximate. Distance excludes gaps, implausible jumps and movement within reported GPS uncertainty. Map points and request table are limited; totals include all retained records.'))
