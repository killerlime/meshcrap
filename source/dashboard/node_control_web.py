"""Authenticated, same-origin dashboard control endpoints."""
import hashlib
import hmac
import json
import os
import secrets
import socket
import time
from pathlib import Path
from flask import jsonify, request, session, render_template


def register_node_control(app, root=None):
    root = Path(root or '@@DATA_DIR@@')
    from dashboard_security import Security, COOKIE
    security=Security(app,root)
    keyfile = root / '.node-control-key'
    if not keyfile.exists():
        fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(secrets.token_urlsafe(24)+'\n')
    key = keyfile.read_text().strip()
    app.secret_key = app.secret_key or hashlib.sha256(('session:'+key).encode()).digest()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict')
    attempts = {}

    def unlocked():
        return session.get('radio_until', 0) > time.time()

    @app.get('/kmkt-control')
    def kmkt_control_page():
        return render_template('kmkt-control.html')

    @app.get('/node-control')
    def control_page():
        return render_template('node-control.html')

    @app.get('/api/kmkt-control/session')
    @app.get('/api/node-control/session')
    def control_session():
        response = jsonify(unlocked=security.routine(), admin=security.admin(), trusted=security.trusted(), secure=request.is_secure)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/api/kmkt-control/unlock')
    @app.post('/api/node-control/unlock')
    def unlock():
        if request.headers.get('Origin') != request.host_url.rstrip('/') or not request.is_json:
            return jsonify(error='Open controls from this dashboard'), 403
        if security.rate_limited():
            return jsonify(error='Too many attempts. Try again in five minutes.'),429
        supplied = (request.get_json(silent=True) or {}).get('key', '')
        if not isinstance(supplied, str) or not hmac.compare_digest(supplied, key):
            security.failure()
            return jsonify(error='Incorrect control key'), 403
        remember=(request.get_json() or {}).get('remember') is True
        if remember and not request.is_secure:
            return jsonify(error='Use the private HTTPS address to remember this device'),400
        security.success()
        response=jsonify(unlocked=True,admin=True,trusted=remember,secure=request.is_secure)
        if remember:security.remember(response,(request.get_json() or {}).get('device_name'))
        return response

    @app.post('/api/kmkt-control/action')
    @app.post('/api/node-control/action')
    def control_action():
        if request.headers.get('Origin') != request.host_url.rstrip('/') or not request.is_json:
            return jsonify(error='Open controls from this dashboard'), 403
        if request.content_length is None or request.content_length > 65536:
            return jsonify(error='Request too large'), 413
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error='Invalid request'), 400
        if body.get('action') == 'lock':
            security.forget();session.clear()
            response=jsonify(ok=True,data={});response.delete_cookie(COOKIE,secure=request.is_secure,httponly=True,samesite='Strict');return response
        if body.get('action') == 'revoke_devices':
            if not security.admin():return jsonify(error='Unlock settings to revoke devices'),401
            security.forget(all_devices=True)
            response=jsonify(ok=True,data={'message':'All remembered devices revoked.'});response.delete_cookie(COOKIE,secure=request.is_secure,httponly=True,samesite='Strict');return response
        if not security.may_act(body):
            return jsonify(error='Unlock settings for this action' if security.routine() else 'Unlock node controls first'),401
        if body.get('action') not in ('state', 'send', 'save','operation','operations'):
            return jsonify(error='Unsupported action'), 400
        if request.path.startswith('/api/kmkt-control/'):
            from kmkt_control_connection import dispatch
            try:
                result = dict(ok=True, data=dispatch(body))
            except ValueError as error:
                return jsonify(ok=False, error=str(error)), 400
            except Exception:
                return jsonify(ok=False, error='Secondary radio control connection failed. Refresh to reconnect; actions are not automatically retried.'), 503
            response = jsonify(result)
            response.headers['Cache-Control'] = 'no-store'
            return response
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(12)
                sock.connect(str(root / '.node-control.sock'))
                sock.sendall(json.dumps(body).encode()+b'\n')
                with sock.makefile('rb') as stream:
                    line = stream.readline(2_000_001)
                if len(line) > 2_000_000:
                    raise ValueError('Response too large')
                result = json.loads(line)
        except (OSError, ValueError):
            return jsonify(error='Collector controls are unavailable. It may be reconnecting or paused for mobile access.'), 503
        response = jsonify(result)
        response.headers['Cache-Control'] = 'no-store'
        return response, 200 if result.get('ok') else 400
