"""On-demand diagnostics over pinned SSH, never the radio API."""
import base64
import json
import sqlite3
import subprocess
import threading
import time
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import jsonify

def remote_read(root, request):
    try:
        config = json.loads((Path(root)/'receiver-log-access.json').read_text())
        command = ['ssh', '-T', '-oBatchMode=yes', '-oStrictHostKeyChecking=yes',
                   '-oConnectTimeout=4', '-oServerAliveInterval=5', '-oServerAliveCountMax=1',
                   '-oIdentitiesOnly=yes', '-oPasswordAuthentication=no', '-oKbdInteractiveAuthentication=no',
                   '-oUserKnownHostsFile='+config['known_hosts'], '-i', config['identity'],
                   '-l', config['user'], config['host'],
                   'journal-read:'+base64.urlsafe_b64encode(json.dumps(request).encode()).decode()]
        result = subprocess.run(command, capture_output=True, text=True, timeout=18)
        if result.returncode: raise RuntimeError('Receiver journal unavailable')
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or data.get('error'): raise ValueError('Invalid receiver response')
        return data
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Receiver logs are unavailable; check the saved SSH connection.') from exc

def connection_summary(db, now):
    start = (now-timedelta(hours=48)).isoformat()
    with closing(sqlite3.connect('file:'+str(db)+'?mode=ro', uri=True, timeout=2)) as conn:
        conn.execute('PRAGMA query_only=ON')
        rows = conn.execute("SELECT event_time,event_type,message FROM collector_events WHERE event_time>=? AND event_type IN ('CONNECTED','CONNECTION_ERROR') ORDER BY event_time", (start,)).fetchall()
        latest = conn.execute("SELECT event_time,event_type FROM collector_events WHERE event_type IN ('CONNECTED','CONNECTION_ERROR') ORDER BY event_id DESC LIMIT 1").fetchone()
    errors = [r for r in rows if r[1]=='CONNECTION_ERROR']
    return {'errors_48h': len(errors), 'no_route_48h': sum('No route to host' in (r[2] or '') for r in errors),
            'last_error': errors[-1][0] if errors else None,
            'last_event': {'time': latest[0], 'type': latest[1]} if latest else None}

def register_receiver_diagnostics(app, db):
    lock = threading.Lock()
    cache = {'attempted': 0, 'data': None, 'error': None}
    @app.get('/api/receiver-diagnostics')
    def receiver_diagnostics():
        now = datetime.now(timezone.utc)
        # Single bounded request per five minutes, even if several tabs ask.
        with lock:
            if time.monotonic()-cache['attempted'] > 300 or not cache['attempted']:
                cache['attempted'] = time.monotonic()
                try:
                    cache['data'] = remote_read(db.parent, {'action': 'summary'})
                    cache['error'] = None
                except RuntimeError:
                    cache['error'] = 'Receiver journal unavailable. Earlier readings, if shown, are stale.'
            radio, error = cache['data'], cache['error']
        try: connection = connection_summary(db, now)
        except sqlite3.Error: connection = None
        response = jsonify(radio=radio, radio_error=error, stale=bool(error), connection=connection, generated=now.isoformat())
        response.headers['Cache-Control'] = 'no-store'
        return response
