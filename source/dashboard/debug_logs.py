"""On-demand, bounded journal access for this app's services only."""
import json
import re
import subprocess
import threading
from datetime import datetime,timezone
from pathlib import Path
from flask import jsonify,request

SERVICES={'collector':'mesh-collector.service','dashboard':'mesh-dashboard.service',
          'feed':'potato-mf-feed.service','gateway':'receiver-gateway.service'}
WINDOWS={'hour':'1 hour ago','day':'24 hours ago','week':'7 days ago'}
SECRET=re.compile(r'(?i)(\b(?:api[_-]?token|api[_-]?key|password|private[_-]?key|psk|authorization)\b[\s\"\x27:=]+)(?:Bearer\s+)?[^\s,;\"\x27}]+')

def scrub(message,secrets):
    text=str(message)
    for secret in secrets:
        if secret:text=text.replace(secret,'[redacted]')
    text=SECRET.sub(r'\1[redacted]',text)
    return ''.join(c for c in text if c in '\n\t' or ord(c)>=32)[:4000]

def register_debug_logs(app,root=Path('@@DATA_DIR@@')):
    slots=threading.BoundedSemaphore(2)

    @app.get('/api/debug-logs')
    def debug_logs():
        service=request.args.get('service','collector')
        window=request.args.get('window','day')
        level=request.args.get('level','all')
        try:limit=int(request.args.get('limit','200'))
        except ValueError:return jsonify(error='Invalid line limit'),400
        if service not in (*SERVICES,'all','receiver') or window not in WINDOWS or level not in ('all','warning') or limit not in (100,200,500):
            return jsonify(error='Invalid log selection'),400
        if not slots.acquire(blocking=False):
            return jsonify(error='Log viewer is busy. Retry shortly.'),503
        try:
            if service == 'receiver':
                from receiver_diagnostics import remote_read
                query = dict(action='logs', window=window, level=level, limit=limit)
                if request.args.get('before'): query['before'] = request.args['before']
                try: data = remote_read(root, query)
                except RuntimeError: return jsonify(error='Receiver logs are unavailable. Check its SSH connection.'),503
                secrets=[]
                for name in ('potato-feed/api-token','.node-control-key'):
                    try: secrets.append((root/name).read_text().strip())
                    except OSError: pass
                for entry in data.get('entries',[]):
                    message = entry.get('message','')
                    entry['truncated'] = bool(entry.get('truncated') or len(message)>4000)
                    entry['message'] = scrub(message, secrets)
                return jsonify(data)
            command=['journalctl','--no-pager','--quiet','--output=json',
                     '--output-fields=MESSAGE,__REALTIME_TIMESTAMP,PRIORITY,_SYSTEMD_UNIT',
                     '--lines='+str(limit),'--since='+WINDOWS[window]]
            for unit in (SERVICES.values() if service=='all' else [SERVICES[service]]):
                command.extend(['--unit',unit])
            if level=='warning':command.append('--priority=warning')
            result=subprocess.run(command,capture_output=True,text=True,timeout=6,check=False)
            if result.returncode:
                return jsonify(error='Logs are temporarily unavailable.'),503
            secrets=[]
            for name in ('potato-feed/api-token','.node-control-key'):
                try:secrets.append((root/name).read_text().strip())
                except OSError:pass
            entries=[]
            for line in result.stdout.splitlines():
                try:
                    item=json.loads(line)
                    stamp=datetime.fromtimestamp(int(item['__REALTIME_TIMESTAMP'])/1e6,timezone.utc).isoformat()
                    message=item.get('MESSAGE','')
                    if isinstance(message,list):message=bytes(message).decode('utf-8',errors='replace')
                    entries.append(dict(time=stamp,service=item.get('_SYSTEMD_UNIT',''),priority=str(item.get('PRIORITY','6')),message=scrub(message,secrets)))
                except (ValueError,TypeError,KeyError,OverflowError):continue
            return jsonify(entries=entries[-limit:],generated=datetime.now(timezone.utc).isoformat(),limit=limit)
        except (OSError,subprocess.TimeoutExpired):
            return jsonify(error='Log request timed out or is unavailable. Try a shorter time range.'),503
        finally:slots.release()

    @app.after_request
    def private_logs(response):
        if request.path=='/api/debug-logs':response.headers['Cache-Control']='no-store'
        return response
