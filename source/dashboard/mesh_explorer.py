"""Independent observation analytics. No radio access or estimated positions."""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import threading
import time

UTC = timezone.utc
METRICS = {'snr': ('rx_snr', 'dB'), 'rssi': ('rx_rssi', 'dBm'),
           'battery': ('battery_level', '%'), 'voltage': ('voltage', 'V'),
           'temperature': ('temperature', '°C'), 'humidity': ('relativeHumidity', '%'),
           'pressure': ('barometricPressure', 'hPa')}


def node_id(n):
    return f'!{n:08x}' if type(n) is int and 0 < n < 0xffffffff else None


def stamp(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.replace(tzinfo=UTC).timestamp() if d.tzinfo is None else d.timestamp()
    except (ValueError, TypeError):
        return None


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def mapping(value):
    return value if isinstance(value, dict) else {}


def packet(row):
    try:
        p = json.loads(row.get('raw_json') or '{}')
        return p if isinstance(p, dict) else {}
    except (TypeError, ValueError):
        return {}


def rf(row, receiver):
    p = packet(row)
    return (row.get('observation_type', 'LIVE') == 'LIVE'
            and not p.get('viaMqtt') and not p.get('via_mqtt')
            and row.get('transport') not in ('TRANSPORT_MQTT', 'TRANSPORT_INTERNAL')
            and node_id(row.get('from_num')) not in (None, receiver, p.get('_collectorReceiverId'))
            and (row.get('transport') == 'TRANSPORT_LORA'
                 or finite(row.get('rx_snr')) or finite(row.get('rx_rssi'))))


def read(database, sql, args=()):
    # One bounded read connection per request; never hold the collector lock.
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True, timeout=1)) as c:
        c.row_factory = sqlite3.Row
        end = time.monotonic()+1.5
        c.set_progress_handler(lambda: int(time.monotonic() > end), 1000)
        c.execute('PRAGMA query_only=ON')
        return [dict(x) for x in c.execute(sql, args)]


def window_rows(database, hours, ports=None, limit=12000):
    cutoff = (datetime.now(UTC)-timedelta(hours=hours)).isoformat()
    clause = ' AND portnum IN ('+','.join('?' for _ in ports)+')' if ports else ''
    rows = read(database, 'SELECT * FROM packets WHERE collector_time>=?'+clause+
                ' ORDER BY row_id DESC LIMIT ?', (cutoff, *(ports or ()), limit+1))
    return rows[:limit], len(rows) > limit


def paths(row):
    """Use collector-decoded routes. Missing/opaque hops stay explicit."""
    p = packet(row)
    d = mapping(p.get('decoded'))
    route = mapping(d.get('traceroute'))
    response_id=d.get('requestId',d.get('replyId'))
    if d.get('wantResponse') or type(response_id) is not int or not 0<response_id<=0xffffffff or not isinstance(d.get('traceroute'),dict):
        return []
    outbound=route.get('route',[])
    if not isinstance(outbound,list):return []
    # A response is from destination to requester; route lists the outbound path.
    source, dest = node_id(row.get('to_num')), node_id(row.get('from_num'))
    if not source or not dest:
        return []
    def clean(v):
        if isinstance(v, str) and v.startswith('!'):
            try: v = int(v[1:], 16)
            except ValueError: return 'Unknown hop'
        return node_id(v) or 'Unknown hop'
    result = [{'source': source, 'destination': dest, 'direction': 'outbound',
               'path': [source, *[clean(v) for v in outbound[:32]], dest]}]
    back = route.get('routeBack', route.get('route_back',[]))
    back_signal=route.get('snrBack',route.get('snr_back'))
    return_available=route.get('returnRouteAvailable') is True or ('returnRouteAvailable' not in route and 'hopStart' in p and isinstance(back_signal,list) and isinstance(back,list) and len(back_signal)==len(back)+1)
    if return_available and isinstance(back, list):
        result.append({'source': dest, 'destination': source, 'direction': 'return',
                       'path': [dest, *[clean(v) for v in back[:32]], source]})
    return result


def topology(rows, nodes, receiver):
    edges = {}
    ambiguous = Counter()
    seen = set()
    def add(a, b, evidence, row, signal=False):
        if not a or not b or a == b or 'Unknown hop' in (a, b): return
        key = (a, b, evidence)
        item = edges.setdefault(key, dict(source=a, target=b, evidence=evidence,
                           observations=0, first_seen=row['collector_time'], last_seen=row['collector_time'],
                           snr_sum=0, snr_samples=0))
        item['observations'] += 1
        item['first_seen'] = min(item['first_seen'], row['collector_time'])
        item['last_seen'] = max(item['last_seen'], row['collector_time'])
        if signal and finite(row.get('rx_snr')):
            item['snr_sum'] += row['rx_snr']; item['snr_samples'] += 1
    for row in rows:
        if not rf(row, receiver): continue
        key = (row.get('from_num'), row.get('packet_id'), row.get('to_num'), row.get('portnum')) if row.get('packet_id') else ('row', row['row_id'])
        if key in seen: continue
        seen.add(key)
        origin = node_id(row.get('from_num'))
        if row.get('hops_used') == 0: add(origin, receiver, 'direct reception', row, True)
        elif type(packet(row).get('relayNode')) is int:
            # A one-byte relay tag is not a globally unique node identity.
            ambiguous[packet(row)['relayNode']] += 1
        if row.get('portnum') == 'TRACEROUTE_APP':
            for path in paths(row):
                for a, b in zip(path['path'], path['path'][1:]): add(a, b, 'recorded traceroute', row)
    result = []
    for e in edges.values():
        e['snr'] = e.pop('snr_sum')/e['snr_samples'] if e['snr_samples'] else None
        result.append(e)
    result.sort(key=lambda e: -e['observations'])
    used = {x for e in result for x in (e['source'], e['target'])}
    names = {node_id(n['node_num']): n for n in nodes}
    return {'edges': result[:600], 'edge_limit': len(result)>600,
            'nodes': [{'id': n, 'name': names.get(n, {}).get('long_name') or n} for n in sorted(used)],
            'ambiguous': [{'relay_byte': f'{b:02x}', 'observations': count,
                'candidates': [i for i in names if i and int(i[1:],16)&255 == b]} for b,count in ambiguous.most_common(30)]}


class HistoryIndex:
    """Incremental derived summaries in a separate database; source is read-only."""
    def __init__(self, database, receiver):
        self.database, self.receiver = database, receiver
        self.path = Path(database).with_name('mesh-explorer-history.sqlite3')
        self.lock = threading.Lock()
        self.error = None
    def connect(self):
        c = sqlite3.connect(self.path, timeout=2)
        self.path.chmod(0o600)
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('CREATE TABLE IF NOT EXISTS progress (id INTEGER PRIMARY KEY, cursor INTEGER NOT NULL)')
        c.execute('INSERT OR IGNORE INTO progress VALUES (1,0)')
        c.execute('CREATE TABLE IF NOT EXISTS hourly (hour INTEGER,node TEXT,observations INTEGER,direct INTEGER,snr_sum REAL,snr_count INTEGER,PRIMARY KEY(hour,node))')
        return c
    def step(self):
        with self.lock, closing(self.connect()) as c:
            # Serialize the read/write batch with utilities' attached-database purge.
            c.commit()
            c.execute('BEGIN IMMEDIATE')
            cursor = c.execute('SELECT cursor FROM progress WHERE id=1').fetchone()[0]
            rows = read(self.database, 'SELECT * FROM packets WHERE row_id>? ORDER BY row_id LIMIT 2000', (cursor,))
            with c:
                for row in rows:
                    t = stamp(row['collector_time'])
                    if t is None or not rf(row,self.receiver): continue
                    snr = row.get('rx_snr'); has = finite(snr)
                    c.execute('INSERT INTO hourly VALUES (?,?,?,?,?,?) ON CONFLICT(hour,node) DO UPDATE SET observations=observations+excluded.observations,direct=direct+excluded.direct,snr_sum=snr_sum+excluded.snr_sum,snr_count=snr_count+excluded.snr_count',
                         (int(t//3600)*3600,node_id(row['from_num']),1,int(row.get('hops_used')==0),snr if has else 0,int(has)))
                if rows:c.execute('UPDATE progress SET cursor=? WHERE id=1',(rows[-1]['row_id'],))
            self.error = None
    def report(self, days):
        if not self.path.exists(): return {'rows': [], 'indexed_through': 0, 'index_status': 'Starting'}
        with self.lock, closing(sqlite3.connect(self.path,timeout=1)) as c:
            c.row_factory = sqlite3.Row
            end=time.monotonic()+1.5
            c.set_progress_handler(lambda:int(time.monotonic()>end),1000)
            values = c.execute('SELECT hour,SUM(observations) observations,SUM(direct) direct,COUNT(*) unique_nodes,SUM(snr_sum) snr_sum,SUM(snr_count) snr_count FROM hourly WHERE hour>=? GROUP BY hour ORDER BY hour', (time.time()-min(days,30)*86400,)).fetchall()
            cursor = c.execute('SELECT cursor FROM progress WHERE id=1').fetchone()[0]
        # Daily unique nodes count the union across hours, not the sum.
        with closing(sqlite3.connect(self.path,timeout=1)) as c:
            end=time.monotonic()+1.5
            c.set_progress_handler(lambda:int(time.monotonic()>end),1000)
            daily = c.execute('SELECT CAST(hour/86400 AS INTEGER)*86400,COUNT(DISTINCT node),SUM(observations),SUM(direct) FROM hourly WHERE hour>=? GROUP BY CAST(hour/86400 AS INTEGER) ORDER BY 1',(time.time()-days*86400,)).fetchall()
        maximum = read(self.database,'SELECT MAX(row_id) maximum FROM packets')[0]['maximum'] or 0
        return {'rows':[dict(v) for v in values], 'daily':[dict(ts=r[0],unique_nodes=r[1],observations=r[2],direct=r[3]) for r in daily],
                'indexed_through':cursor,'source_latest':maximum,'caught_up':cursor>=maximum,
                'index_status':'Temporarily unavailable' if self.error else 'Ready' if cursor>=maximum else 'Backfilling',
                'retention':'Summaries retained until explicitly removed; raw history is unchanged.'}
    def worker(self):
        while True:
            try:self.step()
            except (sqlite3.Error,OSError,ValueError):self.error=True
            time.sleep(30)


def register_explorer(app, database, receiver, start_worker=True):
    from flask import jsonify, request
    index = HistoryIndex(database, receiver)
    app.extensions['mesh_explorer'] = index
    cache = {}; lock = threading.Lock()
    @app.after_request
    def explorer_invalidate_after_purge(response):
        if request.endpoint == 'remove' and response.status_code < 400:
            with lock:cache.clear()
        return response
    def hours():return max(1,min(720,int(request.args.get('hours',24))))
    def respond(name, fn):
        # Normalize only the meaningful arguments; arbitrary query strings cannot
        # retain multiple parsed copies of a large local geography pack.
        keys={'nodes':(), 'map-pack':(), 'delivery':(), 'topology':('hours',),
              'routes':('hours',), 'telemetry':('hours','nodes','metric'), 'history':('days',)}[name]
        try:
            key=(name,tuple((k,str(hours()) if k=='hours' else str(max(1,min(3650,int(request.args.get('days',90))))) if k=='days' else request.args.get(k,'')) for k in keys))
            with lock:
                cached=cache.get(key)
                if cached and time.monotonic()-cached[0]<30:body,etag=cached[1:]
                else:
                    body=fn();etag='"'+hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()+'"'
                    if len(cache)>=32:cache.pop(next(iter(cache)))
                    cache[key]=(time.monotonic(),body,etag)
            response=app.response_class(status=304) if request.headers.get('If-None-Match')==etag else jsonify(body)
            response.headers.update({'ETag':etag,'Cache-Control':'private, no-cache'})
            return response
        except (ValueError,TypeError):return jsonify(error='Invalid selection'),400
        except (sqlite3.Error,OSError):return jsonify(error='History is busy. Retry shortly.'),503
    @app.get('/api/explorer/nodes')
    def explorer_nodes():
        return respond('nodes',lambda:read(database,'SELECT node_num,node_id,long_name,short_name,role FROM nodes ORDER BY long_name LIMIT 2000'))
    @app.get('/api/explorer/topology')
    def explorer_topology():
        def build():
            rows,truncated=window_rows(database,hours())
            out=topology(rows,read(database,'SELECT node_num,long_name FROM nodes LIMIT 5000'),receiver)
            out.update(truncated=truncated,hours=hours(),receiver=receiver)
            return out
        return respond('topology',build)
    @app.get('/api/explorer/routes')
    def explorer_routes():
        def build():
            h=hours();rows,truncated=window_rows(database,h*2,('TRACEROUTE_APP',),1000)
            boundary=time.time()-h*3600;groups={}
            for row in rows:
                if not rf(row,receiver):continue
                for route in paths(row):
                    key=(route['source'],route['destination'],route['direction'],tuple(route['path']))
                    item=groups.setdefault(key,{**route,'current':0,'previous':0,'last_seen':row['collector_time']})
                    t=stamp(row['collector_time'])
                    if t is not None:item['current' if t>=boundary else 'previous']+=1
            return {'routes':list(groups.values()),'hours':h,'truncated':truncated}
        return respond('routes',build)
    @app.get('/api/explorer/telemetry')
    def explorer_telemetry():
        def build():
            metric=request.args.get('metric','snr');field,unit=METRICS[metric] if metric in METRICS else (None,None)
            ids=request.args.get('nodes','').split(',')
            if not field or not 1<=len(ids)<=6 or any(not node_id(int(n[1:],16)) or len(n)!=9 or not n.startswith('!') for n in ids):raise ValueError()
            h=hours();start=time.time()-h*3600;step=max(60,int(h*3600/360));result=[]
            for ident in ids:
                rows=read(database,'SELECT * FROM packets WHERE from_num=? AND collector_time>=? ORDER BY row_id DESC LIMIT 6001',(int(ident[1:],16),datetime.fromtimestamp(start,UTC).isoformat()))
                buckets=defaultdict(list)
                for row in rows[:6000]:
                    p=packet(row)
                    if row.get('observation_type','LIVE')!='LIVE' or p.get('viaMqtt') or p.get('via_mqtt') or row.get('transport') in ('TRANSPORT_MQTT','TRANSPORT_INTERNAL'):continue
                    if metric in ('snr','rssi') and not rf(row,receiver):continue
                    value=row.get(field)
                    if metric in ('temperature','humidity','pressure'):
                        value=mapping(mapping(mapping(p.get('decoded')).get('telemetry')).get('environmentMetrics')).get(field)
                    t=stamp(row['collector_time'])
                    if finite(value) and t is not None:buckets[int(t//step)*step].append(value)
                result.append({'id':ident,'truncated':len(rows)>6000,'points':[{'ts':t,'mean':sum(v)/len(v),'min':min(v),'max':max(v),'samples':len(v)} for t,v in sorted(buckets.items())]})
            return {'series':result,'unit':unit,'metric':metric,'bucket_seconds':step,'start':start,'end':start+h*3600}
        return respond('telemetry',build)
    @app.get('/api/explorer/history')
    def explorer_history():return respond('history',lambda:index.report(max(1,min(3650,int(request.args.get('days',90))))))
    @app.get('/api/explorer/delivery')
    def explorer_delivery():
        def build():
            from message_evidence import enrich
            tables=read(database,"SELECT name FROM sqlite_master WHERE name='web_sent_messages'")
            rows=read(database,'SELECT * FROM web_sent_messages ORDER BY submitted_at DESC LIMIT 100') if tables else []
            messages=[dict(id='sent:'+str(r['packet_id']),sender_id=node_id(r['sender_num']),
                          destination_id=node_id(r['destination_num']) or 'Broadcast',
                          direction='sent',received_at=r['submitted_at']) for r in rows]
            return {'messages':enrich(database,messages)}
        return respond('delivery',build)
    @app.get('/api/explorer/map-pack')
    def map_pack():
        def build():
            custom=Path(database).with_name('offline-map.geojson')
            path=custom if custom.exists() else Path(__file__).parent/'static/offline-geography.json'
            if path.stat().st_size>5*1024*1024:raise ValueError('Map pack too large')
            geo=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(geo,dict) or geo.get('type')!='FeatureCollection' or len(geo.get('features',[]))>10000:raise ValueError()
            # Return geometry only; no HTML, remote icons or arbitrary properties.
            features=[]
            for feature in geo['features']:
                geometry=mapping(mapping(feature).get('geometry'))
                if geometry.get('type') not in ('Polygon','MultiPolygon','LineString','MultiLineString','Point','MultiPoint'):continue
                def valid_coords(value,depth=0):
                    if not isinstance(value,list) or not value or depth>5:return False
                    if all(finite(v) for v in value):return 2<=len(value)<=3 and -180<=value[0]<=180 and -90<=value[1]<=90
                    return all(valid_coords(v,depth+1) for v in value)
                if not valid_coords(geometry.get('coordinates')):raise ValueError('Invalid map coordinates')
                features.append(dict(type='Feature',properties={},geometry=geometry))
            attribution_file=custom.with_name('offline-map-attribution.txt')
            attribution=(attribution_file.read_text(encoding='utf-8')[:1000].strip() if custom.exists() and attribution_file.exists() else '')
            return {'geometry':dict(type='FeatureCollection',features=features),
                'attribution':attribution or ('Local map pack' if custom.exists() else 'Natural Earth · public domain'),
                'detail':'User-supplied local geography' if custom.exists() else 'Coarse country boundaries · not street detail'}
        return respond('map-pack',build)
    if start_worker:threading.Thread(target=index.worker,daemon=True,name='history-summary').start()
    return index
