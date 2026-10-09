"""Read-only broadcast message view using the existing collector database."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from flask import jsonify, render_template, request


def read_messages(database, channel, limit=100, before=None):
    cutoff=int((Path(database).resolve().parent/'potato-feed/primary-policy-start').read_text().strip())
    # Protobuf omits channel zero; the collector stores that omission as NULL.
    # Map saved slots to their channel names across the primary-channel swap.
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=3)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT p.row_id,p.collector_time,p.from_num,p.from_id,p.packet_id,
                   p.rx_snr,p.hops_used,p.raw_json,n.long_name,n.short_name
            FROM packets p LEFT JOIN nodes n ON n.node_num=p.from_num
            WHERE COALESCE(p.channel,0)=? AND p.portnum='TEXT_MESSAGE_APP'
              AND p.to_num=4294967295 AND (? IS NULL OR p.row_id < ?)
            ORDER BY p.row_id DESC LIMIT ?
        ''', (channel, before, before, limit + 1)).fetchall()
    more = len(rows) > limit
    messages = []
    for row in rows[:limit]:
        try:
            packet = json.loads(row['raw_json'])
            decoded = packet.get('decoded') or {}
            text = decoded.get('text')
            if not isinstance(text, str):
                # collector.json_default stores bytes as hexadecimal.
                payload = decoded.get('payload')
                if not isinstance(payload, str):
                    continue
                text = bytes.fromhex(payload).decode('utf-8', errors='replace')
        except (ValueError, TypeError, AttributeError):
            continue
        if not text:
            continue
        sender_id = row['from_id'] or (f"!{row['from_num']:08x}" if row['from_num'] is not None else 'Unknown')
        messages.append(dict(id=row['row_id'], received_at=row['collector_time'],
                             sender_id=sender_id, sender=row['long_name'] or row['short_name'] or sender_id,
                             packet_id=row['packet_id'], text=text, snr=row['rx_snr'], hops=row['hops_used']))
    from sent_messages import recent
    from message_evidence import enrich
    pending=recent(database, channel) if before is None else []
    enrich(database,messages+pending)
    return dict(messages=messages, sent_messages=pending,
                next_before=rows[limit-1]['row_id'] if more else None)


def register_messages(app, database):
    config_path = Path(__file__).with_name('messages_config.json')

    @app.get('/messages')
    def message_page():
        return render_template('messages.html')

    @app.get('/api/channel-messages')
    def channel_messages():
        config = json.loads(config_path.read_text())
        channels = config['channels']
        channel = request.args.get('channel', str(config['channel']))
        if channel not in channels:
            return jsonify(error='Unknown channel'), 400
        try:
            before = int(request.args['before']) if 'before' in request.args else None
            if before is not None and before < 1:
                raise ValueError()
        except ValueError:
            return jsonify(error='Invalid message cursor'), 400
        try:
            result = read_messages(database, int(channel), before=before)
        except sqlite3.Error:
            return jsonify(error='Message history is temporarily unavailable. Retry shortly.'), 503
        result.update(channel=int(channel), channel_name=channels[channel])
        response = jsonify(result)
        response.headers['Cache-Control'] = 'no-store'
        return response
