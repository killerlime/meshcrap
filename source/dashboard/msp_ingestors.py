"""On-demand, read-only public MSP Mesh ingestor directory."""
import json,re,urllib.request
from datetime import datetime,timezone
from flask import jsonify

ORIGIN='' # External directory integration is unavailable in this distribution.
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def fetch_public(path):
    if not ORIGIN:raise ValueError('External directory not configured')
    request=urllib.request.Request(ORIGIN+path,headers={'Accept':'application/json','User-Agent':'Meshcrap/1'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=5) as response:
        data=response.read(8*1024*1024+1)
    if len(data)>8*1024*1024:raise ValueError('Response too large')
    result=json.loads(data)
    if not isinstance(result,list):raise ValueError('Unexpected response')
    return result

def combine(ingestors,nodes,now):
    directory={n['node_id'].lower():n for n in nodes if isinstance(n,dict) and isinstance(n.get('node_id'),str)}
    result=[];seen=set()
    for item in ingestors:
        if not isinstance(item,dict):continue
        ident=item.get('node_id')
        if not isinstance(ident,str) or not re.fullmatch(r'![0-9a-fA-F]{8}',ident):continue
        ident=ident.lower()
        if ident in seen:continue
        seen.add(ident);node=directory.get(ident,{})
        stamp=item.get('last_seen_time')
        if type(stamp) not in (int,float) or not 0<stamp<=now.timestamp()+300:stamp=None
        age=max(0,now.timestamp()-stamp) if stamp is not None else None
        def label(value):return value.strip()[:120] if isinstance(value,str) else ''
        result.append(dict(node_id=ident,name=label(node.get('long_name')) or label(node.get('short_name')) or ident,
          short_name=label(node.get('short_name')),version=label(item.get('version')) or 'Not reported',
          preset=label(item.get('modem_preset')) or 'Not reported',
          last_seen=datetime.fromtimestamp(stamp,timezone.utc).isoformat() if stamp is not None else None,
          age_seconds=age,recent=age is not None and age<=3600,is_gunit=ident.lower()=='@@RECEIVER_ID@@'))
    result.sort(key=lambda r:r['age_seconds'] if r['age_seconds'] is not None else float('inf'))
    return result

def register_msp_ingestors(app):
    register_heard_by(app)
    @app.get('/api/msp-ingestors')
    def msp_ingestors():
        try:
            ingestors=fetch_public('/api/ingestors');nodes=fetch_public('/api/nodes?limit=1000')
            now=datetime.now(timezone.utc)
            result=combine(ingestors,nodes,now)
            return jsonify(checked_at=now.isoformat(),ingestors=result,source=ORIGIN+'/api/ingestors'),200,{'Cache-Control':'no-store'}
        except (OSError,ValueError,TypeError,OverflowError):
            return jsonify(error='MSP Mesh could not be reached. Try Refresh again shortly.'),502,{'Cache-Control':'no-store'}


def heard_by_summary(collections,nodes,now):
    directory={n['node_id'].lower():n for n in nodes if isinstance(n,dict) and isinstance(n.get('node_id'),str)}
    def ident(value):
        return value.lower() if isinstance(value,str) and re.fullmatch(r'![0-9a-fA-F]{8}',value) else None
    def name(node_id):
        node=directory.get(node_id,{})
        for key in ('long_name','short_name'):
            value=node.get(key)
            if isinstance(value,str) and value.strip():return value.strip()[:120]
        return node_id
    groups={};seen=set();omitted=0
    for kind,records in collections.items():
        for record in records:
            if not isinstance(record,dict):omitted+=1;continue
            node=ident(record.get('from_id')) or ident(record.get('node_id'))
            reporter=ident(record.get('ingestor'));stamp=record.get('rx_time')
            if not node or not reporter or type(stamp) not in (int,float) or not 0<stamp<=now.timestamp()+300:
                omitted+=1;continue
            packet_id=record.get('id')
            fingerprint=(kind,node,reporter,stamp,str(packet_id))
            if fingerprint in seen:continue
            seen.add(fingerprint)
            key=(node,reporter)
            if key not in groups:
                groups[key]=dict(node_id=node,node_name=name(node),ingestor_id=reporter,ingestor_name=name(reporter),reports=0,kinds=set(),latest=stamp,self_report=node==reporter)
            group=groups[key];group['reports']+=1;group['kinds'].add(kind);group['latest']=max(group['latest'],stamp)
    result=sorted(groups.values(),key=lambda row:row['latest'],reverse=True)
    for row in result:
        row['kinds']=sorted(row['kinds']);row['last_report']=datetime.fromtimestamp(row.pop('latest'),timezone.utc).isoformat()
    return result,omitted


def register_heard_by(app):
    @app.get('/api/msp-heard-by')
    def heard_by():
        from concurrent.futures import ThreadPoolExecutor,as_completed
        paths={'nodes':'/api/nodes?limit=1000','Messages':'/api/messages?limit=200','Positions':'/api/positions?limit=200','Telemetry':'/api/telemetry?limit=200'}
        collections={};nodes=[];unavailable=[]
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending={pool.submit(fetch_public,path):kind for kind,path in paths.items()}
            for future in as_completed(pending):
                kind=pending[future]
                try:
                    data=future.result()
                    if kind=='nodes':nodes=data
                    else:collections[kind]=data[:200]
                except (OSError,ValueError,TypeError):unavailable.append(kind)
        if not collections:
            return jsonify(error='Public packet reports are unavailable. Try Refresh again.'),502,{'Cache-Control':'no-store'}
        now=datetime.now(timezone.utc);rows,omitted=heard_by_summary(collections,nodes,now)
        return jsonify(checked_at=now.isoformat(),rows=rows,unavailable=sorted(unavailable),omitted=omitted,
                       source_counts={k:len(v) for k,v in collections.items()},limit_per_type=200),200,{'Cache-Control':'no-store'}
