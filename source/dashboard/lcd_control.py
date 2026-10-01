"""Authenticated controls for the dedicated LCD kiosk service only."""
import subprocess
import threading
from pathlib import Path
from flask import jsonify, request

UNIT = 'receiver-lcd.service'
READY = Path('/usr/local/share/mesh-lcd-control.ready')


def register_lcd_control(app):
    """Register read-only status and explicit sleep/wake actions."""
    lock = threading.Lock()

    def reply(data, code=200):
        response = jsonify(data)
        response.headers['Cache-Control'] = 'no-store'
        return response, code

    def status():
        result = subprocess.run(['/usr/bin/systemctl', 'show', UNIT,
                                 '-p', 'ActiveState', '-p', 'SubState'],
                                capture_output=True, text=True, timeout=5, check=True)
        values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        active = values.get('ActiveState', 'unknown')
        return dict(state='awake' if active == 'active' else 'asleep' if active == 'inactive' else active,
                    service_state=active, detail=values.get('SubState', ''),
                    available=READY.is_file(), unlocked=app.extensions['dashboard_security'].routine())

    @app.get('/api/lcd-control')
    def lcd_status():
        try:
            return reply(status())
        except (OSError, subprocess.SubprocessError):
            return reply(dict(error='LCD status unavailable.'), 503)

    @app.post('/api/lcd-control')
    def lcd_action():
        if request.headers.get('Origin') != request.host_url.rstrip('/') or not request.is_json:
            return reply(dict(error='Use the controls on this dashboard.'), 403)
        if not app.extensions['dashboard_security'].routine():
            return reply(dict(error='Unlock Receiver controls first, then return here.'), 401)
        if request.content_length is None or request.content_length > 1024:
            return reply(dict(error='Invalid request size.'), 413)
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or body.get('action') not in ('sleep', 'wake'):
            return reply(dict(error='Choose Sleep or Wake.'), 400)
        if not READY.is_file():
            return reply(dict(error='LCD controls need the one-time administrator setup.'), 503)
        if not lock.acquire(blocking=False):
            return reply(dict(error='An LCD action is already running. Wait and refresh.'), 409)
        try:
            action = 'stop' if body['action'] == 'sleep' else 'start'
            result = subprocess.run(['/usr/bin/sudo', '-n', '/usr/bin/systemctl', action, UNIT],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode:
                return reply(dict(error='LCD service action failed. Check the administrator setup and service log.'), 503)
            return reply(status())
        except subprocess.TimeoutExpired:
            return reply(dict(error='LCD action timed out. Check its status before retrying.'), 504)
        except (OSError, subprocess.SubprocessError):
            return reply(dict(error='LCD control unavailable. Refresh to check its status.'), 503)
        finally:
            lock.release()
