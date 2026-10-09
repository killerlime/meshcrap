"""Read-only primary/secondary receiver comparison using verified overlapping collection sessions."""
import hashlib
import json
import math
import sqlite3
import statistics
import threading
import time
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from bisect import bisect_right
from collections import OrderedDict

PRIMARY_ID = '@@RECEIVER_ID@@'
SECONDARY_ID = '@@SECONDARY_RECEIVER_ID@@'
MATCH_SECONDS = 120
MAX_ROWS = 10000
LORA_FIELDS = ('use_preset', 'modem_preset', 'bandwidth', 'spread_factor', 'coding_rate',
               'region', 'channel_num', 'override_frequency', 'frequency_offset')


def timestamp(value):
    try:
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        result = float(value)
        return result if math.isfinite(result) else 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def read_status(root, now, receiver_id, secondary=False):
    """Read a local heartbeat; identity/freshness prevent stale or foreign status."""
    path = root / ('secondary/status.json' if secondary else 'receiver-status.json')
    try:
        with path.open('r', encoding='utf-8') as stream:
            text = stream.read(16385)
        if len(text) > 16384:
            raise ValueError('Oversized status')
        raw = json.loads(text)
        if not isinstance(raw, dict) or raw.get('receiver_id') != receiver_id:
            raise ValueError('Wrong receiver')
        age = now - timestamp(raw.get('heartbeat'))
        fresh = 0 <= age <= 25
        return dict(receiver_id=receiver_id, connected=raw.get('connected') is True and fresh,
                    heartbeat=raw.get('heartbeat'), heartbeat_age_seconds=round(max(0, age), 1),
                    profile=safe_profile(raw.get('profile')) if fresh else None, last_packet=raw.get('last_packet'),
                    error=raw.get('error') if fresh else 'Receiver collector heartbeat is stale')
    except (OSError, ValueError, TypeError):
        return dict(connected=False, error='Receiver collector has not started or identity is unverified', profile=None)


def safe_profile(value):
    """Allowlist even locally cached profiles before returning them to a browser."""
    if not isinstance(value, dict) or not isinstance(value.get('lora'), dict):
        return None
    from receiver_provenance import LORA_FIELDS
    channels = value.get('channels')
    return dict(lora={key: item for key, item in value['lora'].items()
                      if key in LORA_FIELDS and isinstance(item, (str, bool, int, float, type(None)))},
                channels=[dict(index=item.get('index') if type(item.get('index')) is int else None,
                               name=item.get('name') if isinstance(item.get('name'), str) else '',
                               enabled=item.get('enabled') is True)
                          for item in channels[:8] if isinstance(item, dict)] if isinstance(channels, list) else [])


def compatibility(primary, secondary):
    if not primary or not secondary:
        return dict(verified=False, mismatches=[], message='Waiting for both receiver profiles')
    fields = ['region', 'use_preset', 'override_frequency', 'frequency_offset']
    fields += ['modem_preset'] if primary['lora'].get('use_preset') else ['bandwidth', 'spread_factor', 'coding_rate']
    # With no explicit override, channel_num determines the configured frequency.
    if not primary['lora'].get('override_frequency'):
        fields.append('channel_num')
    missing = [k for k in fields if primary['lora'].get(k) is None or secondary['lora'].get(k) is None]
    differences = [k for k in fields if primary['lora'].get(k) != secondary['lora'].get(k)]
    return dict(verified=not missing and not differences, mismatches=differences, missing=missing,
                message='Radio settings align. Channel keys are not checked; packet matches require identical payloads.'
                if not missing and not differences else 'Receiver radio settings differ or are incomplete; reception counts need this context.')


def primary_intervals(conn, start, end):
    rows = conn.execute("""SELECT event_time,event_type FROM collector_events
                           WHERE event_type IN ('START','CONNECTING','CONNECTED','NODE_SNAPSHOT','CONNECTION_ERROR','STOP')
                           AND event_time<=? ORDER BY event_id DESC LIMIT 2000""", (iso(end),)).fetchall()
    intervals, active, pending = [], None, False
    for row in reversed(rows):
        at, kind = timestamp(row['event_time']), row['event_type']
        if kind in ('START', 'CONNECTING', 'CONNECTION_ERROR', 'STOP'):
            if active is not None and at > active:
                intervals.append((active, at))
            active, pending = None, False
        elif kind == 'CONNECTED':
            pending = True
        elif kind == 'NODE_SNAPSHOT' and pending:
            if active is None:
                active = at
            pending = False
    if active is not None:
        intervals.append((active, end))
    return [(max(a, start), min(b, end)) for a, b in intervals if b > start and a < end]


def secondary_intervals(conn, status, start, end):
    heartbeat = min(end, timestamp(status.get('heartbeat')))
    rows = conn.execute('SELECT started_at,ended_at FROM collection_sessions WHERE started_at<=? AND (ended_at IS NULL OR ended_at>=?) ORDER BY session_id DESC LIMIT 2000',
                        (iso(end), iso(start))).fetchall()
    rows = reversed(rows)
    result = []
    for row in rows:
        a = max(start, timestamp(row['started_at']))
        b = min(end, timestamp(row['ended_at']) if row['ended_at'] else heartbeat)
        if b > a:
            result.append((a, b))
    return result


def overlap(left, right):
    """Linear merge of sorted, nonoverlapping collection intervals."""
    left, right = sorted(left), sorted(right)
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = left[i]
        c, d = right[j]
        if min(b, d) > max(a, c):
            result.append((max(a, c), min(b, d)))
        if b <= d:
            i += 1
        else:
            j += 1
    return result


def interval_at(at, intervals, beginnings=None):
    beginnings = beginnings if beginnings is not None else [a for a, _ in intervals]
    index = bisect_right(beginnings, at) - 1
    return intervals[index] if index >= 0 and at <= intervals[index][1] else None


def in_intervals(at, intervals):
    return interval_at(at, intervals) is not None


def load_packets(conn, receiver_id, start, end, intervals):
    if not intervals:
        return [], False
    rows = conn.execute("""SELECT row_id,collector_time,rx_time,packet_id,from_num,from_id,to_num,channel,portnum,
                           rx_snr,rx_rssi,hops_used,transport,channel_utilization,air_util_tx,raw_json
                           FROM packets WHERE collector_time>=? AND collector_time<=?
                           AND COALESCE(observation_type,'UNDATED')='LIVE' AND rx_time>0 AND length(raw_json)<=16384
                           AND from_num!=? AND COALESCE(transport,'') NOT IN ('TRANSPORT_MQTT','TRANSPORT_INTERNAL')
                           AND (transport='TRANSPORT_LORA' OR rx_snr IS NOT NULL OR rx_rssi IS NOT NULL)
                           ORDER BY collector_time DESC LIMIT ?""",
                        (iso(start), iso(end), int(receiver_id[1:], 16), MAX_ROWS + 1))
    result = []
    truncated = False
    beginnings = [a for a, _ in intervals]
    for index, row in enumerate(rows):
        if index == MAX_ROWS:
            truncated = True
            break
        at = timestamp(row['collector_time'])
        interval = interval_at(at, intervals, beginnings)
        if interval is None:
            continue
        try:
            raw = json.loads(row['raw_json'])
        except (ValueError, TypeError):
            continue
        if not isinstance(raw, dict):
            continue
        if raw.get('_collectorObservationType', 'LIVE') != 'LIVE':
            continue
        if raw.get('viaMqtt') or raw.get('_collectorReceiverId') != receiver_id:
            continue
        # A receiver can drain packets queued before its client connected.
        rx_at = timestamp(row['rx_time'])
        interval_start = interval[0]
        if rx_at and interval_start is not None and (rx_at < interval_start - 5 or rx_at > at + 60):
            continue
        value = dict(row)
        value['at'] = at
        value['raw'] = raw
        # Keep a digest for pairing, not duplicate message/position payloads in RAM.
        value['match_key'] = packet_key(value)
        value.pop('raw')
        value.pop('raw_json')
        result.append(value)
    return list(reversed(result)), truncated


def packet_key(row):
    if 'match_key' in row:
        return row['match_key']
    raw, port = row['raw'], row['portnum']
    payload = None
    decoded = raw.get('decoded') or {}
    if isinstance(decoded, dict):
        if 'payload' in decoded:
            payload = ('decoded', decoded['payload'])
        elif any(k in decoded for k in ('user', 'position', 'telemetry', 'neighborinfo', 'routing', 'traceroute', 'text')):
            payload = ('decoded-fields', decoded)
    if payload is None and 'encrypted' in raw:
        payload = ('encrypted', raw['encrypted'])
    if payload is None or type(row['packet_id']) is not int or not 0 < row['packet_id'] <= 0xffffffff:
        return None
    if type(row['from_num']) is not int or not 0 < row['from_num'] < 0xffffffff or type(row['to_num']) is not int:
        return None
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return row['from_num'], row['packet_id'], row['to_num'], port, digest


def summary(rows):
    hops = Counter('direct' if r['hops_used'] == 0 else 'relayed' if isinstance(r['hops_used'], int) and 1 <= r['hops_used'] <= 7 else 'unknown' for r in rows)
    return dict(observations=len(rows), nodes=len({r['from_num'] for r in rows}), hops=dict(hops),
                ports=dict(Counter(r['portnum'] or 'Opaque' for r in rows)), last_rf=rows[-1]['collector_time'] if rows else None)


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def paired_metrics(pairs):
    result = dict(packets=len(pairs))
    for field, label in [('rx_snr', 'snr'), ('rx_rssi', 'rssi')]:
        values = [k[field] - h[field] for h, k in pairs if numeric(h[field]) and numeric(k[field])]
        result[label + '_samples'] = len(values)
        result[label + '_median_secondary_minus_primary'] = round(statistics.median(values), 2) if values else None
    return result


def local_telemetry(conn, receiver_id, start, end):
    rows = conn.execute('''SELECT collector_time,battery_level,voltage,channel_utilization,air_util_tx,uptime_seconds
                           FROM packets WHERE from_num=? AND portnum='TELEMETRY_APP'
                           AND collector_time>=? AND collector_time<=?
                           AND COALESCE(observation_type,'LIVE')='LIVE'
                           ORDER BY collector_time DESC LIMIT 500''',
                        (int(receiver_id[1:], 16), iso(start), iso(end))).fetchall()
    return [dict(row) for row in reversed(rows)]


def group_packets(primary, secondary):
    groups = defaultdict(list)
    unmatchable = 0
    for label, rows in [('primary', primary), ('secondary', secondary)]:
        for row in rows:
            key = packet_key(row)
            if key is None:
                unmatchable += 1
                continue
            groups[key].append((label, row))
    episodes = []
    for values in groups.values():
        values.sort(key=lambda x: x[1]['at'])
        batch, beginning = [], None
        for value in values:
            if beginning is not None and value[1]['at'] - beginning > MATCH_SECONDS:
                episodes.append(batch)
                batch, beginning = [], None
            if beginning is None:
                beginning = value[1]['at']
            batch.append(value)
        if batch:
            episodes.append(batch)
    return episodes, unmatchable


def correlations(primary, secondary, intervals, start, end, bin_seconds):
    # Only whole bins continuously covered by both collectors support count correlation.
    first = math.ceil(start / bin_seconds) * bin_seconds
    bins = []
    while first + bin_seconds <= end:
        if any(a <= first and first + bin_seconds <= b for a, b in intervals):
            bins.append(dict(at=iso(first), start=first, primary=0, secondary=0))
        first += bin_seconds
    by_time = {b['start']: b for b in bins}
    for label, rows in [('primary', primary), ('secondary', secondary)]:
        for row in rows:
            b = by_time.get(math.floor(row['at'] / bin_seconds) * bin_seconds)
            if b is not None:
                b[label] += 1
    coefficient = None
    if len(bins) >= 12:
        x, y = [b['primary'] for b in bins], [b['secondary'] for b in bins]
        mx, my = statistics.mean(x), statistics.mean(y)
        xx, yy = sum((v - mx) ** 2 for v in x), sum((v - my) ** 2 for v in y)
        if xx > 0 and yy > 0:
            coefficient = round(sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(xx * yy), 3)
    for b in bins:
        b.pop('start')
    return dict(bin_minutes=bin_seconds // 60, complete_bins=len(bins), packet_count_pearson=coefficient, timeline=bins)


def closest_pair(left, right):
    """Nearest timestamps in linear time; inputs are sorted within each episode."""
    i = j = 0
    best, distance = (left[0], right[0]), abs(left[0]['at'] - right[0]['at'])
    while i < len(left) and j < len(right):
        difference = abs(left[i]['at'] - right[j]['at'])
        if difference < distance:
            best, distance = (left[i], right[j]), difference
        if left[i]['at'] <= right[j]['at']:
            i += 1
        else:
            j += 1
    return best


def compare(primary, secondary, intervals, start, end, names=None):
    names = names or {}
    episodes, unmatchable = group_packets(primary, secondary)
    counts, node_counts, pairs = Counter(), defaultdict(Counter), []
    classes = defaultdict(list)
    pairs_by_node = defaultdict(list)
    for episode in episodes:
        h, k = [r for label, r in episode if label == 'primary'], [r for label, r in episode if label == 'secondary']
        category = 'both' if h and k else 'primary_only' if h else 'secondary_only'
        counts[category] += 1
        node_counts[episode[0][1]['from_num']][category] += 1
        if h and k:
            pair = closest_pair(h, k)
            pairs.append(pair)
            pairs_by_node[pair[0]['from_num']].append(pair)
            ha, ka = pair[0]['hops_used'], pair[1]['hops_used']
            known_hops = type(ha) is int and type(ka) is int and 0 <= ha <= 7 and 0 <= ka <= 7
            kind = 'direct_both' if known_hops and ha == ka == 0 else 'relayed_both' if known_hops and ha > 0 and ka > 0 else 'mixed' if known_hops else 'unknown'
            classes[kind].append(pair)
    nodes = []
    for number, counts_for_node in node_counts.items():
        node_pairs = pairs_by_node[number]
        direct = [p for p in node_pairs if p[0]['hops_used'] == p[1]['hops_used'] == 0]
        nodes.append(dict(node_id=f'!{number:08x}', name=names.get(number) or f'!{number:08x}',
                          **{key: counts_for_node[key] for key in ('both', 'primary_only', 'secondary_only')},
                          direct=paired_metrics(direct)))
    nodes.sort(key=lambda n: -(n['both'] + n['primary_only'] + n['secondary_only']))
    hop_pairs = Counter(f"{h['hops_used'] if h['hops_used'] is not None else '?'} → {k['hops_used'] if k['hops_used'] is not None else '?'}" for h, k in pairs)
    bins = 300 if end - start <= 3600 else 900 if end - start <= 86400 else 3600
    return dict(primary=summary(primary), secondary=summary(secondary), packets={k: counts[k] for k in ('both', 'primary_only', 'secondary_only')},
                unmatchable_observations=unmatchable,
                signal={key: paired_metrics(classes[key]) for key in ('direct_both', 'relayed_both', 'mixed', 'unknown')},
                hop_pairs=dict(hop_pairs), nodes=nodes[:200], timing=correlations(primary, secondary, intervals, start, end, bins))


class Comparison:
    def __init__(self, root, primary_database, primary_id, secondary_id, label='Secondary', enabled=False):
        self.root = Path(root)
        self.primary_database = Path(primary_database)
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.primary_id, self.secondary_id = primary_id, secondary_id
        self.label, self.enabled = label, enabled

    def build(self, hours):
        now = time.time()
        with self.lock:
            cached = self.cache.get(hours)
            if cached and now - cached[0] < 15:
                return cached[1]
            primary_status = read_status(self.root, now, self.primary_id) if self.enabled else {}
            status = read_status(self.root, now, self.secondary_id, True) if self.enabled else {}
            result = dict(enabled=self.enabled, labels=dict(primary='Primary', secondary=self.label), generated_at=iso(now), hours=hours, status=status, primary_status=primary_status, primary_profile=primary_status.get('profile'),
                          compatibility=compatibility(primary_status.get('profile'), status.get('profile')),
                          coverage=dict(overlap_seconds=0, intervals=[], first_collection=None), comparison=None,
                          limits=['Only simultaneous collection periods are compared.',
                                  'Not observed at one receiver does not prove reception failure.',
                                  'Direct paired packets support signal comparisons; relayed values describe the last hop.',
                                  'Payload identity is required; local channel slot numbers are not treated as shared identities.',
                                  'Signal calibration and antenna differences can affect the measured offset.',
                                  'Packet-count correlation needs at least 12 complete bins and does not establish a cause.'])
            secondary_file = self.root / 'secondary/mesh.db'
            if self.enabled and secondary_file.exists() and self.primary_database.exists():
                with closing(sqlite3.connect(self.primary_database.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as hconn, closing(sqlite3.connect(secondary_file.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as kconn:
                    hconn.row_factory = kconn.row_factory = sqlite3.Row
                    first = kconn.execute('SELECT MIN(started_at) FROM collection_sessions').fetchone()[0]
                    requested = now - hours * 3600
                    start = max(requested, timestamp(first)) if first else now
                    hi = primary_intervals(hconn, start, min(now, timestamp(primary_status.get('heartbeat'))))
                    ki = secondary_intervals(kconn, status, start, now)
                    common = overlap(hi, ki)
                    result['coverage'] = dict(overlap_seconds=round(sum(b - a for a, b in common)),
                                              intervals=[dict(start=iso(a), end=iso(b)) for a, b in common],
                                              first_collection=first, requested_start=iso(requested), actual_start=iso(start))
                    if common:
                        begin, finish = common[0][0], common[-1][1]
                        hrows, ht = load_packets(hconn, self.primary_id, begin, finish, common)
                        krows, kt = load_packets(kconn, self.secondary_id, begin, finish, common)
                        names = {r['node_num']: r['long_name'] or r['short_name'] for r in hconn.execute('SELECT node_num,long_name,short_name FROM nodes ORDER BY node_num LIMIT 4000')}
                        for r in kconn.execute('SELECT node_num,long_name,short_name FROM nodes ORDER BY node_num LIMIT 4000'):
                            names.setdefault(r['node_num'], r['long_name'] or r['short_name'])
                        result['comparison'] = compare(hrows, krows, common, begin, finish, names)
                        result['truncated'] = ht or kt
                        if result['truncated']:
                            result['comparison']['timing']['packet_count_pearson'] = None
                    result['local_telemetry'] = dict(primary=local_telemetry(hconn, self.primary_id, start, now),
                                                    secondary=local_telemetry(kconn, self.secondary_id, start, now))
            self.cache[hours] = now, result
            self.cache.move_to_end(hours)
            while len(self.cache) > 4:
                self.cache.popitem(last=False)
            return result


def register_receiver_comparison(app, primary_database, enabled=False, secondary_id='!00000000', label='Secondary', controls=False):
    from flask import jsonify, render_template, request
    root = Path(primary_database).parent
    comparison = Comparison(root, primary_database, PRIMARY_ID, secondary_id, label, enabled)
    app.extensions['receiver_comparison'] = comparison

    @app.get('/receiver-comparison')
    def receiver_comparison_page():
        return render_template('receiver-comparison.html')

    @app.get('/api/receiver-comparison/integration')
    def receiver_comparison_integration():
        response = jsonify(enabled=enabled, secondary_label=label, controls_enabled=enabled and controls)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/receiver-comparison')
    def receiver_comparison_api():
        try:
            hours = int(request.args.get('hours', '24'))
            if not 1 <= hours <= 720:
                raise ValueError()
        except ValueError:
            return jsonify(error='Choose a window from 1 to 720 hours'), 400
        try:
            result = comparison.build(hours)
        except (sqlite3.Error, OSError):
            return jsonify(error='Receiver databases are temporarily unavailable. Retry shortly.'), 503
        response = jsonify(result)
        response.headers['Cache-Control'] = 'no-store'
        return response
