"""Passive role counterfactual. No radio API, transmissions, or config writes."""
import json
import socket
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from flask import jsonify, request

HQ = @@RECEIVER_NUM@@
HQ_ID = '@@RECEIVER_ID@@'

def read_profile(root):
    """One local IPC read of the collector's existing memory; safe while mobile owns HQ."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect(str(root / '.node-control.sock'))
        sock.sendall(b'{"action":"role_profile"}\n')
        with sock.makefile('rb') as f:
            reply = json.loads(f.readline(100001))
    if not reply.get('ok'):
        raise ValueError('Collector profile unavailable')
    d = reply['data']
    if d.get('node_id') != HQ_ID:
        raise ValueError('Receiver is not HQ')
    # Strict allowlist: never expose full configuration, keys, or location.
    return dict(node_id=HQ_ID, captured_at=d['captured_at'],
                firmware=d.get('metadata', {}).get('firmwareVersion'),
                role=d.get('device', {}).get('role'),
                rebroadcast=d.get('device', {}).get('rebroadcastMode'),
                modem=d.get('lora', {}).get('modemPreset'),
                use_preset=d.get('lora', {}).get('usePreset'),
                favorites=d.get('favorites', []))

def analyze(rows, names, profile, now, hours):
    start = now - timedelta(hours=hours)
    step = 3600 if hours <= 168 else 21600
    bins = [dict(time=(start+timedelta(seconds=i)).isoformat(), candidates=0,
                 affected=0, channel_max=None, tx_max=None, hq_samples=0)
            for i in range(0, hours*3600, step)]
    totals = Counter()
    origins = Counter()
    seen = {}
    favorites = set(profile['favorites']) if profile else None
    for r in rows:
        try:
            raw = json.loads(r['raw_json'] or '{}')
            stamp = datetime.fromisoformat(r['collector_time'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            totals['invalid'] += 1
            continue
        if not start <= stamp <= now:
            continue
        if raw.get('_collectorReceiverId') != HQ_ID:
            totals['other_receiver'] += 1
            continue
        b = bins[min(len(bins)-1, int((stamp-start).total_seconds()//step))]
        if r['from_num'] == HQ:
            totals['own'] += 1
            if r['channel_utilization'] is not None or r['air_util_tx'] is not None:
                b['hq_samples'] += 1
                for key, col in [('channel_max', 'channel_utilization'), ('tx_max', 'air_util_tx')]:
                    v = r[col]
                    if v is not None and 0 <= v <= 100:
                        b[key] = max(b[key] or 0, v)
            continue
        if raw.get('viaMqtt') or str(r['transport'] or '').lower() in ('mqtt', 'http', 'api', 'transport_mqtt', 'transport_internal'):
            totals['non_rf'] += 1
            continue
        if r['rx_snr'] is None and r['rx_rssi'] is None:
            totals['unconfirmed_rf'] += 1
            continue
        if not r['from_num'] or not r['packet_id']:
            totals['missing_identity'] += 1
            continue
        key = (r['from_num'], r['packet_id'])
        if key in seen and (stamp-seen[key]).total_seconds() < 86400:
            totals['duplicates'] += 1
            continue
        seen[key] = stamp
        totals['unique_rf'] += 1
        # Broadcast flooding only: direct messages use next-hop routing rules.
        if r['to_num'] != 0xffffffff:
            totals['non_broadcast'] += 1
            continue
        if r['hop_limit'] is None:
            totals['unknown_hops'] += 1
            continue
        if r['hop_limit'] <= 0:
            totals['exhausted'] += 1
            continue
        if r['portnum'] in ('ADMIN_APP', 'ROUTING_APP', 'TRACEROUTE_APP'):
            totals['diagnostic'] += 1
            continue
        totals['candidates'] += 1
        b['candidates'] += 1
        if favorites is not None:
            if r['from_num'] in favorites:
                totals['favorites'] += 1
            else:
                totals['affected'] += 1
                b['affected'] += 1
                origins[r['from_num']] += 1
    return dict(start=start.isoformat(), generated=now.isoformat(), hours=hours,
                bin_hours=step/3600, totals=dict(totals), bins=bins,
                profile=profile,
                origins=[dict(id=f'!{n:08x}', name=names.get(n) or f'!{n:08x}', packets=k)
                         for n,k in origins.most_common(12)])

def register_role_compare(app, db_path, startup_windows, startup_filter):
    root = Path(db_path).parent
    cache = {}
    lock = threading.Lock()
    saved = None

    @app.get('/api/role-comparison')
    def role_comparison():
        nonlocal saved
        try:
            hours = int(request.args.get('hours', 24))
            if not 1 <= hours <= 720:
                raise ValueError()
        except (TypeError, ValueError):
            return jsonify(error='Choose a window from 1 to 720 hours.'), 400
        with lock:
            entry = cache.get(hours)
            if entry and time.monotonic()-entry[0] < 60:
                return jsonify(entry[1])
            try:
                saved = read_profile(root)
                fresh = True
            except (OSError, ValueError, KeyError):
                fresh = False
            now = datetime.now(timezone.utc)
            with closing(sqlite3.connect('file:'+str(db_path)+'?mode=ro', uri=True, timeout=5)) as c:
                c.row_factory = sqlite3.Row
                filt, args = startup_filter(startup_windows(c))
                rows = [dict(r) for r in c.execute(f'''SELECT collector_time, from_num, to_num,
                    packet_id, hop_limit, portnum, rx_snr, rx_rssi, transport, raw_json,
                    channel_utilization, air_util_tx FROM packets p
                    WHERE observation_type='LIVE' AND collector_time>=? AND collector_time<=?
                    AND ({filt}) ORDER BY collector_time, row_id LIMIT 200001''',
                    [(now-timedelta(hours=hours)).isoformat(), now.isoformat(), *args])]
                if len(rows) > 200000:
                    return jsonify(error='Too many observations for this window. Choose a shorter window; no partial estimate was made.'), 422
                names = {r['node_num']:r['name'] for r in c.execute(
                    'SELECT node_num,COALESCE(long_name,short_name,node_id) name FROM nodes')}
            data = analyze(rows, names, saved, now, hours)
            data['profile_fresh'] = fresh
            # Current favorites/config are a replay assumption, not a historical record.
            data['model_ready'] = bool(saved and saved.get('role') == 'CLIENT_BASE'
                and saved.get('rebroadcast') == 'ALL'
                and str(saved.get('firmware') or '').startswith('2.8.'))
            cache[hours] = (time.monotonic(), data)
            if len(cache) > 16:
                del cache[next(iter(cache))]
            return jsonify(data)
