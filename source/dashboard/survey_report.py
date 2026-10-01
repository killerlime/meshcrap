"""Survey contribution reports; no radio actions or changes to packet history."""
from datetime import datetime, timedelta, timezone
import math
from collections import OrderedDict
from coverage_age import accumulate

_baselines = OrderedDict()

def proven(c):
    return bool(c and c['samples'] >= 3 and c['snr'] and
                sum(c['snr']) / len(c['snr']) >= -12 and
                (not c['hops'] or sum(c['hops']) / len(c['hops']) <= 4))

def stamp(value):
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t

def enrich(conn, survey, rows, buckets, bounds, steps, distance, area=None):
    min_lat, max_lat, min_lon, max_lon = bounds
    lat_step, lon_step = steps
    cache_key = (survey['start_row_id'], survey['started_at'], bounds, steps, tuple(area.get('parts',())) if area else ())
    baseline = _baselines.get(cache_key)
    if baseline is None:
        previous = conn.execute('''SELECT collector_time, latitude, longitude,
            rx_snr, rx_rssi, hops_used, from_id AS node FROM packets
            WHERE row_id <= ? AND latitude BETWEEN ? AND ?
            AND longitude BETWEEN ? AND ?''',
            (survey['start_row_id'], min_lat, max_lat, min_lon, max_lon)).fetchall()
        if area:
            from coverage_areas import contains
            previous=[r for r in previous if contains(area,r['latitude'],r['longitude'])]
        current, old = accumulate(previous, min_lat, min_lon, lat_step, lon_step,
                                  stamp(survey['started_at']) - timedelta(days=30))
        baseline = {key: ('PROVEN' if proven(current[key]) else 'MARGINAL')
                    if key in current else 'STALE' for key in current.keys() | old.keys()}
        _baselines[cache_key] = baseline
        while len(_baselines) > 16:
            _baselines.popitem(last=False)
    gained = [key for key, bucket in buckets.items()
              if proven(bucket) and baseline.get(key, 'UNTESTED') != 'PROVEN']
    refreshed = [key for key in buckets if baseline.get(key) == 'STALE']
    by_node = {}
    for r in rows:
        lat, lon = float(r['latitude']), float(r['longitude'])
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            by_node.setdefault(r['from_num'], []).append(r)
    routes = []
    for node_num, points in by_node.items():
        segments, segment, previous = [], [], None
        for r in points:
            point = [float(r['latitude']), float(r['longitude'])]
            if previous:
                gap = (stamp(r['collector_time']) - stamp(previous['collector_time'])).total_seconds()
                jump = distance(previous['latitude'], previous['longitude'], *point)
                if gap < 0 or gap > 1800 or jump > 5:
                    if segment: segments.append(segment)
                    segment = []
            if not segment or segment[-1] != point:
                segment.append(point)
            previous = r
        if segment: segments.append(segment)
        total = sum(len(s) for s in segments)
        stride = max(1, math.ceil(total / 2000))
        displayed = [s[::stride] + ([s[-1]] if s[-1] != s[::stride][-1] else []) for s in segments]
        routes.append(dict(node_num=node_num, node=points[-1]['node'], segments=displayed,
                           samples=len(points), simplified=stride > 1))
    return dict(new_coverage_cells=len(gained), stale_cells_refreshed=len(refreshed),
                gained_cell_ids=[f'{x}:{y}' for x,y in gained],
                refreshed_cell_ids=[f'{x}:{y}' for x,y in refreshed], routes=routes,
                traceroute_status='Phone companion required',
                contribution_note='Newly proven = cells not proven at the start that this outing independently proves. Refreshed = previously stale cells heard during this outing. Route gaps over 30 minutes or 5 miles are not joined.')
