"""Restricted, passive meshtasticd journal reader. No radio interface or writes."""
import base64
import collections
import datetime as dt
import json
import os
import re
import subprocess

WINDOWS = {'hour': '1 hour ago', 'day': '24 hours ago', 'week': '7 days ago'}
SECRET = re.compile(r'(?i)(\b(?:api[_-]?token|api[_-]?key|password|private[_-]?key|psk|authorization|session_passkey)\b[\s\"\x27:=]+)(?:Bearer\s+)?[^\s,;\"\x27}]+')

def scrub(text):
    text = re.sub(r'\x1b\[[0-9;]*m', '', str(text))
    return SECRET.sub(r'\1[redacted]', ''.join(c for c in text if c in '\n\t' or ord(c) >= 32))

def records(args):
    command = ['journalctl', '--unit=meshtasticd.service', '--no-pager', '--quiet', '--output=json',
               '--output-fields=MESSAGE,__REALTIME_TIMESTAMP,PRIORITY,_SYSTEMD_UNIT,__CURSOR'] + args
    result = subprocess.run(command, capture_output=True, text=True, timeout=12)
    if result.returncode:
        raise RuntimeError('Receiver journal unavailable')
    rows = []
    for line in result.stdout.splitlines():
        try:
            row = json.loads(line)
            row['us'] = int(row['__REALTIME_TIMESTAMP'])
            message = row.get('MESSAGE', '')
            row['message'] = bytes(message).decode('utf-8', 'replace') if isinstance(message, list) else str(message)
            rows.append(row)
        except (ValueError, TypeError, KeyError):
            continue
    return rows

def severity(row):
    # meshtasticd embeds severity in stdout; journal PRIORITY alone misses ERROR.
    match = re.match(r'\s*(ERROR|WARN|WARNING|INFO|DEBUG|TRACE)\s*\|', scrub(row['message']))
    return {'ERROR': '3', 'WARN': '4', 'WARNING': '4', 'INFO': '6', 'DEBUG': '7', 'TRACE': '7'}.get(match[1], '6') if match else str(row.get('PRIORITY', '6'))

def summary(rows):
    counts = collections.Counter()
    hourly = collections.defaultdict(collections.Counter)
    capacity = None
    for row in rows:
        m = row['message']
        category = None
        if 'Ignore rx packet, error=-7 ' in m: category = 'crc_errors'
        elif "Can't decode protobuf" in m: category = 'decode_errors'
        elif 'Decryptable packet failed decoding, relay opaquely' in m: category = 'opaque_relays'
        elif 'Node database full:' in m:
            category = 'node_evictions'
            match = re.search(r'Node database full: (\d+) nodes', m)
            if match: capacity = int(match[1])
        elif 'Client wants config' in m: category = 'config_requests'
        elif 'Client dropped connection' in m: category = 'client_disconnects'
        if category:
            counts[category] += 1
            hour = dt.datetime.fromtimestamp(row['us']/1e6, dt.timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
            hourly[hour][category] += 1
    keys = ('crc_errors', 'decode_errors', 'opaque_relays', 'node_evictions', 'config_requests', 'client_disconnects')
    return {'counts': {key: counts[key] for key in keys} if rows else {}, 'capacity_at_last_eviction': capacity,
            'hourly': [{'hour': h, **dict(c)} for h, c in sorted(hourly.items())],
            'first_record': dt.datetime.fromtimestamp(min(r['us'] for r in rows)/1e6, dt.timezone.utc).isoformat() if rows else None,
            'records_scanned': len(rows), 'truncated': len(rows) >= 100000,
            'window_hours': 48, 'generated': dt.datetime.now(dt.timezone.utc).isoformat()}

def handle(request):
    if request == {'action': 'summary'}:
        return summary(records(['--since=48 hours ago', '--lines=100000']))
    if request.get('action') != 'logs': raise ValueError('Unsupported request')
    window, level, limit = request.get('window'), request.get('level'), request.get('limit')
    if window not in WINDOWS or level not in ('all', 'warning') or type(limit) is not int or limit not in (100, 200, 500):
        raise ValueError('Invalid log selection')
    before = request.get('before')
    if before is not None and (not isinstance(before, str) or not re.fullmatch(r'[A-Za-z0-9_=;.-]{1,1024}', before)):
        raise ValueError('Invalid cursor')
    # Scan a bounded raw page; filter embedded severity after parsing. Cursor always
    # advances across scanned records, including pages with no matching warnings.
    args = ['--reverse', '--lines='+str(limit+1)]
    if before: args.append('--cursor='+before)
    else: args.append('--since='+WINDOWS[window])
    rows = records(args)
    if before:
        cutoff = (dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours={'hour':1,'day':24,'week':168}[window])).timestamp()*1e6
        rows = [r for r in rows if r.get('__CURSOR') != before and r['us'] >= cutoff]
    more = len(rows) >= limit
    rows = rows[:limit]
    entries = []
    for row in reversed(rows):
        priority = severity(row)
        if level == 'warning' and int(priority) > 4: continue
        message = scrub(row['message'])
        entries.append({'time': dt.datetime.fromtimestamp(row['us']/1e6, dt.timezone.utc).isoformat(),
                        'service': 'meshtasticd.service', 'priority': priority, 'message': message[:16000],
                        'truncated': len(message) > 16000})
    return {'entries': entries, 'next_cursor': rows[-1].get('__CURSOR') if more and rows else None,
            'generated': dt.datetime.now(dt.timezone.utc).isoformat(), 'limit': limit,
            'scanned': len(rows), 'source': 'receiver'}

def main():
    # Intended for an authorized_keys forced command: no arbitrary SSH commands.
    command = os.environ.get('SSH_ORIGINAL_COMMAND', '')
    if not re.fullmatch(r'journal-read:[A-Za-z0-9_=-]{1,4096}', command):
        raise ValueError('Restricted journal reader')
    request = json.loads(base64.urlsafe_b64decode(command.split(':', 1)[1]))
    print(json.dumps(handle(request)))

if __name__ == '__main__':
    try: main()
    except Exception:
        print(json.dumps({'error': 'Receiver log request unavailable'}))
        raise SystemExit(1)
