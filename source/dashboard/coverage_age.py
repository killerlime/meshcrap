"""Separate current coverage observations from retained historical evidence."""
from datetime import datetime,timezone

def expired(timestamp,cutoff):
    try:
        stamp=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
        return stamp<cutoff
    except (ValueError,TypeError,AttributeError):return True

def accumulate(rows,min_lat,min_lon,lat_step,lon_step,cutoff):
    current,old={},{}
    for rr in rows:
        r=dict(rr);lat=float(r['latitude']);lon=float(r['longitude'])
        key=(int((lon-min_lon)//lon_step),int((lat-min_lat)//lat_step))
        bucket=old if expired(r['collector_time'],cutoff) else current
        c=bucket.setdefault(key,dict(samples=0,nodes=set(),snr=[],rssi=[],hops=[],direct=0,last=None))
        c['samples']+=1
        if r['node']:c['nodes'].add(r['node'])
        for field,target in [('rx_snr','snr'),('rx_rssi','rssi')]:
            if r[field] is not None:c[target].append(float(r[field]))
        if r['hops_used'] is not None:
            hops=int(r['hops_used']);c['hops'].append(hops);c['direct']+=int(hops==0)
        if r['collector_time'] and (c['last'] is None or r['collector_time']>c['last']):c['last']=r['collector_time']
    return current,old
