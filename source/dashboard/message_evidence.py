"""Derive delivery evidence from recorded submissions and routing replies."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
import time


def timestamp(value):
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (TypeError,ValueError):return None


def enrich(database, messages):
    if not messages:return messages
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as c:
        c.row_factory=sqlite3.Row
        end=time.monotonic()+1.5
        c.set_progress_handler(lambda:int(time.monotonic()>end),1000)
        c.execute('PRAGMA query_only=ON')
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='web_sent_messages'").fetchone():return messages
        submitted=[dict(r) for r in c.execute('SELECT * FROM web_sent_messages ORDER BY submitted_at DESC LIMIT 300')]
        earliest=min((r['submitted_at'] for r in submitted),default=None)
        if not earliest:return messages
        replies=c.execute("SELECT raw_json,collector_time,from_num,to_num,channel,observation_type,transport FROM packets WHERE portnum='ROUTING_APP' AND collector_time>=? ORDER BY row_id DESC LIMIT 3000",(earliest,)).fetchall()
    by_key={(f"!{s['sender_num']:08x}",s['packet_id']):s for s in submitted}
    evidence={}
    for r in replies:
        try:
            p=json.loads(r['raw_json']);d=p.get('decoded') or {};request=d.get('requestId');route=d.get('routing')
            if not isinstance(route,dict) or type(request) is not int:continue
            key=(f"!{r['to_num']:08x}",request);s=by_key.get(key)
            observed=timestamp(r['collector_time']);started=timestamp(s['submitted_at']) if s else None
            if not s or observed is None or started is None or observed<started:continue
            # Direct-message ACK must originate at the intended destination.
            if s['destination_num']!=0xffffffff and r['from_num']!=s['destination_num']:continue
            if r['from_num'] in (None,s['sender_num'],0xffffffff) or p.get('viaMqtt') or p.get('via_mqtt'):continue
            if r['observation_type']!='LIVE' or r['transport'] in ('TRANSPORT_MQTT','TRANSPORT_INTERNAL'):continue
            if r['channel'] is not None and r['channel']!=s['channel']:continue
            if 'routeRequest' in route or 'routeReply' in route:continue
            # Proto3 omits the default NONE enum in an otherwise valid ACK.
            reason=route.get('errorReason','NONE')
            if key not in evidence:
                evidence[key]={'state':'acknowledged' if reason in ('NONE',0) else 'failed',
                     'detail':'Acknowledged by one peer; this is not proof every recipient received it.' if s['destination_num']==0xffffffff and reason in ('NONE',0) else 'Destination acknowledged receipt.' if reason in ('NONE',0) else 'Routing reply: '+str(reason)[:80],
                     'at':r['collector_time']}
        except (ValueError,TypeError,AttributeError):continue
    for m in messages:
        try:pid=int(str(m['id']).split(':')[-1]) if m.get('direction')=='sent' else m.get('packet_id')
        except (ValueError,TypeError):continue
        key=(m.get('sender_id'),pid);s=by_key.get(key)
        if not s:continue
        m['direction']='sent'
        value=evidence.get(key)
        if value is None:
            t=timestamp(s['submitted_at'])
            elapsed=time.time()-t if t is not None else 9999
            value={'state':'awaiting_ack' if s['destination_num']!=0xffffffff and elapsed<120 else 'submitted' if s['destination_num']==0xffffffff else 'unknown',
                   'detail':'Submitted to radio; broadcast delivery is unconfirmed.' if s['destination_num']==0xffffffff else 'Awaiting destination acknowledgement.' if elapsed<120 else 'No matching acknowledgement in retained history; delivery is unknown.'}
        m['delivery']=value
    return messages
