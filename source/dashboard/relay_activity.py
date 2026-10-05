"""Passive last-hop relay evidence from locally received packets.

relayNode is an eight-bit identifier, not a unique node ID. See
https://github.com/meshtastic/protobufs/blob/master/meshtastic/mesh.proto
No radio requests, inferred relay identities, or HQ retransmission claims.
"""
import json
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock


def summarize(rows, nodes, receiver_id):
    names = {n['node_num']: n for n in nodes}
    candidates = defaultdict(list)
    for n in nodes:
        if isinstance(n['node_num'], int):
            candidates[n['node_num'] & 255].append(n)
    origins = {}
    seen = set()
    unknown = direct = 0
    for r in rows:
        try:
            p = json.loads(r['raw_json'])
        except (ValueError, TypeError):
            continue
        if not isinstance(p, dict):
            continue
        origin = r['from_num']
        origin_id = r['from_id'] or (f'!{origin:08x}' if isinstance(origin, int) else None)
        if not origin_id or origin_id.lower() == receiver_id.lower() or p.get('viaMqtt') or p.get('via_mqtt'):
            continue
        if p.get('_collectorReceiverId') == origin_id:
            continue
        # Count each originating packet once, even if multiple copies arrived.
        key = (origin, r['packet_id']) if r['packet_id'] else ('row', r['row_id'])
        if key in seen:
            continue
        seen.add(key)
        relay = p.get('relayNode', p.get('relay_node'))
        valid_relay = type(relay) is int and 1 <= relay <= 255
        different_relay = valid_relay and isinstance(origin, int) and relay != (origin & 255)
        hops = r['hops_used']
        if not different_relay and not (isinstance(hops, int) and hops > 0):
            if hops == 0:
                direct += 1
            else:
                unknown += 1
            continue
        n = names.get(origin, {})
        item = origins.setdefault(origin_id, dict(node_id=origin_id,
            name=n.get('long_name') or n.get('short_name') or origin_id,
            short_name=n.get('short_name'), role=n.get('role'), packets=0,
            nodeinfo=0, last_heard=None, snr=None, rssi=None, hops=None,
            relays=Counter(), unidentified_relay=0))
        item['packets'] += 1
        item['nodeinfo'] += r['portnum'] == 'NODEINFO_APP'
        if different_relay:
            item['relays'][relay] += 1
        else:
            item['unidentified_relay'] += 1
        if item['last_heard'] is None or r['collector_time'] >= item['last_heard']:
            item.update(last_heard=r['collector_time'], snr=r['rx_snr'],
                        rssi=r['rx_rssi'], hops=hops)
    result = []
    for item in origins.values():
        item['relays'] = [dict(byte=f'{b:02x}', packets=count,
            candidates=[dict(node_id=n['node_id'] or f"!{n['node_num']:08x}",
                name=n['long_name'] or n['short_name'] or n['node_id'])
                for n in candidates[b]]) for b, count in item['relays'].most_common()]
        result.append(item)
    result.sort(key=lambda n: (-n['packets'], n['name'].casefold()))
    return dict(nodes=result, relayed_packets=sum(n['packets'] for n in result),
                direct_packets=direct, unknown_packets=unknown)


def register_relay_activity(app, database, receiver_id):
    from flask import jsonify, request
    cache = {}
    lock = Lock()

    @app.get('/api/relay-activity')
    def relay_activity():
        try:
            hours = max(1, min(720, int(request.args.get('hours', 24))))
        except (TypeError, ValueError):
            hours = 24
        with lock:
            old = cache.get(hours)
            if old and time.monotonic() - old[0] < 30:
                return jsonify(old[1])
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            conn = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute("""SELECT row_id,collector_time,packet_id,from_num,
                    from_id,portnum,hops_used,rx_snr,rx_rssi,raw_json FROM packets
                    WHERE collector_time>=? AND COALESCE(observation_type,'LIVE')='LIVE'
                    AND COALESCE(transport,'') NOT IN ('TRANSPORT_MQTT','TRANSPORT_INTERNAL')
                    AND (rx_snr IS NOT NULL OR rx_rssi IS NOT NULL)
                    ORDER BY collector_time DESC,row_id DESC""", (cutoff,)).fetchall()
                nodes = [dict(n) for n in conn.execute('SELECT node_num,node_id,long_name,short_name,role FROM nodes')]
                data = summarize(rows, nodes, receiver_id)
            finally:
                conn.close()
            data.update(hours=hours, generated=datetime.now(timezone.utc).isoformat())
            cache[hours] = (time.monotonic(), data)
            if len(cache) > 24:
                oldest = min(cache, key=lambda h: cache[h][0])
                del cache[oldest]
            return jsonify(data)
