"""On-demand diagnostics over pinned SSH, never the radio API."""
import base64
import ipaddress
import json
import re
import sqlite3
import subprocess
import threading
import time
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import jsonify

def journal_command(request):
    """Validate the restricted reader protocol before constructing an SSH command."""
    if not isinstance(request,dict):raise ValueError('Invalid journal request')
    if request!={'action':'summary'}:
        if (set(request)-{'action','window','level','limit','before'} or request.get('action')!='logs'
                or request.get('window') not in ('hour','day','week')
                or request.get('level') not in ('all','warning')
                or type(request.get('limit')) is not int or request['limit'] not in (100,200,500)):
            raise ValueError('Invalid journal request')
        before=request.get('before')
        if before is not None and (not isinstance(before,str) or not re.fullmatch(r'[A-Za-z0-9_=;.-]{1,1024}',before)):
            raise ValueError('Invalid journal cursor')
    payload=base64.urlsafe_b64encode(json.dumps(request,separators=(',',':'),sort_keys=True).encode('ascii')).decode('ascii')
    # Encoding alone is not the trust boundary: assert the remote shell grammar.
    if not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}',payload) or len(payload)>4096:
        raise ValueError('Invalid journal command')
    return 'journal-read:'+payload


def ssh_connection(config):
    if not isinstance(config,dict) or set(config)!={'host','user','identity','known_hosts'}:
        raise ValueError('Invalid journal connection')
    if any(not isinstance(v,str) for v in config.values()):raise ValueError('Invalid journal connection')
    host,user=config['host'],config['user']
    if not host or len(host)>253:raise ValueError('Invalid journal host')
    if ':' in host:
        if not re.fullmatch(r'[0-9a-fA-F:]+',host):raise ValueError('Invalid journal host')
        ipaddress.IPv6Address(host)
    elif not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*',host):raise ValueError('Invalid journal host')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}',user):raise ValueError('Invalid journal user')
    paths=[]
    for field in ('identity','known_hosts'):
        value=config[field]
        if len(value)>1024 or not re.fullmatch(r'[A-Za-z0-9_./:\\-]+',value):raise ValueError('Invalid journal path')
        path=Path(value)
        if not path.is_absolute() or not path.is_file():raise ValueError('Invalid journal path')
        resolved=str(path.resolve(strict=True))
        if not re.fullmatch(r'[A-Za-z0-9_./:\\-]+',resolved):raise ValueError('Invalid journal path')
        paths.append(resolved)
    return host,user,*paths


def remote_read(root, request):
    try:
        remote_command=journal_command(request)
        settings=Path(root)/'receiver-log-access.json'
        if settings.stat().st_size>8192:raise ValueError('Invalid journal connection')
        config = json.loads(settings.read_text(encoding='utf-8'))
        host,user,identity,known_hosts=ssh_connection(config)
        command = ['ssh', '-F', '/dev/null', '-T', '-oBatchMode=yes', '-oStrictHostKeyChecking=yes',
                   '-oConnectTimeout=4', '-oServerAliveInterval=5', '-oServerAliveCountMax=1',
                   '-oIdentitiesOnly=yes', '-oPasswordAuthentication=no', '-oKbdInteractiveAuthentication=no',
                   '-oUserKnownHostsFile='+known_hosts, '-i', identity,
                   '-l', user, '--', host, remote_command]
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
