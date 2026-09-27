"""Small-device access controls; no message bodies or credentials in audit logs."""
import hashlib,ipaddress,json,os,secrets,sqlite3,time
from datetime import timedelta
from pathlib import Path
from contextlib import contextmanager
from flask import request,session,jsonify,g,current_app
from flask.sessions import SecureCookieSessionInterface
from werkzeug.middleware.proxy_fix import ProxyFix

ROUTINE_OPERATIONS={'traceroute','position','node_info','neighbors','device_metrics','environment_metrics','power_metrics','air_quality_metrics','local_stats','health_metrics','host_metrics','traffic_management_stats'}
COOKIE='jk_trusted_device'

class SecureSessions(SecureCookieSessionInterface):
    def get_cookie_secure(self,app):return request.is_secure

class LocalHTTPSProxy:
    def __init__(self,app,hostname):self.app=app;self.hostname=hostname;self.proxy=ProxyFix(app,x_for=0,x_proto=1)
    def __call__(self,environ,start_response):
        if self.hostname and environ.get('REMOTE_ADDR') in ('127.0.0.1','::1') and environ.get('HTTP_HOST','').split(':')[0]==self.hostname and environ.get('HTTP_X_FORWARDED_PROTO')=='https':
            return self.proxy(environ,start_response)
        return self.app(environ,start_response)

class Security:
    def __init__(self,app,root):
        self.root=Path(root);self.directory=self.root/'dashboard-security';self.directory.mkdir(mode=0o700,exist_ok=True)
        self.database=self.directory/'access.db'
        secret=self.directory/'session-secret'
        if not secret.exists():
            fd=os.open(secret,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as f:f.write(secrets.token_hex(32))
        app.secret_key=secret.read_text().strip()
        config_path=self.directory/'network.json'
        config=json.loads(config_path.read_text()) if config_path.exists() else {}
        self.https_host=config.get('https_host')
        hosts=@@TRUSTED_HOSTS@@
        if self.https_host:hosts.append(self.https_host)
        self.networks=[ipaddress.ip_network(n) for n in @@ALLOWED_NETWORKS@@]
        app.config.update(TRUSTED_HOSTS=hosts,MAX_CONTENT_LENGTH=65536,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',PERMANENT_SESSION_LIFETIME=timedelta(hours=1))
        app.session_interface=SecureSessions();app.wsgi_app=LocalHTTPSProxy(app.wsgi_app,self.https_host)
        with self.db() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS devices(hash TEXT PRIMARY KEY,created REAL,expires REAL,label TEXT); CREATE TABLE IF NOT EXISTS failures(ip TEXT,at REAL); CREATE TABLE IF NOT EXISTS audit(at REAL,ip TEXT,event TEXT,status INTEGER);')
        self.database.chmod(0o600)
        app.before_request(self.guard);app.after_request(self.headers)
        app.extensions['dashboard_security']=self
    @contextmanager
    def db(self):
        connection=sqlite3.connect(self.database,timeout=3)
        try:
            with connection:yield connection
        finally:connection.close()
    def admin(self):return session.get('radio_until',0)>time.time()
    def trusted(self):
        if not request.is_secure:return False
        token=request.cookies.get(COOKIE,'')
        if not token or len(token)>128:return False
        with self.db() as db:row=db.execute('SELECT expires FROM devices WHERE hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return bool(row and row[0]>time.time())
    def routine(self):return self.admin() or self.trusted()
    def may_act(self,body):
        action=body.get('action')
        routine=action in ('state','operations','send','lock') or action=='operation' and body.get('operation') in ROUTINE_OPERATIONS
        return self.routine() if routine else self.admin()
    def rate_limited(self):
        now=time.time()
        with self.db() as db:
            db.execute('DELETE FROM failures WHERE at<?',(now-300,))
            count=db.execute('SELECT count(*) FROM failures WHERE ip=?',(request.remote_addr,)).fetchone()[0]
        return count>=5
    def failure(self):
        with self.db() as db:db.execute('INSERT INTO failures VALUES(?,?)',(request.remote_addr,time.time()))
        self.audit('unlock_failed',401)
    def success(self):
        with self.db() as db:db.execute('DELETE FROM failures WHERE ip=?',(request.remote_addr,))
        session.clear();session['radio_until']=time.time()+3600
        self.audit('unlock_success',200)
    def remember(self,response,label):
        if not request.is_secure:raise ValueError('Remembering devices requires HTTPS')
        token=secrets.token_urlsafe(32);now=time.time();expires=now+30*86400
        with self.db() as db:
            db.execute('DELETE FROM devices WHERE expires<?',(now,))
            old=request.cookies.get(COOKIE)
            if old:db.execute('DELETE FROM devices WHERE hash=?',(hashlib.sha256(old.encode()).hexdigest(),))
            db.execute('INSERT INTO devices VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),now,expires,str(label or 'Approved browser')[:80]))
        response.set_cookie(COOKIE,token,max_age=30*86400,httponly=True,secure=True,samesite='Strict')
        self.audit('device_approved',200)
    def forget(self,all_devices=False):
        with self.db() as db:
            if all_devices:db.execute('DELETE FROM devices')
            else:db.execute('DELETE FROM devices WHERE hash=?',(hashlib.sha256(request.cookies.get(COOKIE,'').encode()).hexdigest(),))
        self.audit('devices_revoked' if all_devices else 'device_forgotten',200)
    def audit(self,event,status):
        with self.db() as db:
            db.execute('INSERT INTO audit VALUES(?,?,?,?)',(time.time(),request.remote_addr,event[:120],status))
            db.execute('DELETE FROM audit WHERE rowid NOT IN (SELECT rowid FROM audit ORDER BY rowid DESC LIMIT 1000)')
    def guard(self):
        try:address=ipaddress.ip_address(request.remote_addr)
        except ValueError:return jsonify(error='Unrecognized network'),403
        if not any(address in network for network in self.networks):return jsonify(error='Use your home network or private HTTPS address'),403
        if request.path == '/api/survey-phone/sync':
            phone=current_app.extensions.get('survey_phone')
            return phone.authorize() if phone else (jsonify(error='Phone service unavailable'),503)
        if request.method in ('POST','PUT','PATCH','DELETE'):
            if request.headers.get('Origin')!=request.host_url.rstrip('/') or not request.is_json:return jsonify(error='Open this action from the dashboard'),403
            if request.content_length is None or request.content_length>65536:return jsonify(error='Invalid request size'),413
            if not isinstance(request.get_json(silent=True),dict):return jsonify(error='Expected a JSON object'),400
            if request.path.startswith(('/api/node-control/','/api/kmkt-control/')):return None
            allowed=self.routine() if request.path in ('/api/node-note','/api/events','/api/coverage-survey','/api/ask') else self.admin()
            if not allowed:return jsonify(error='Unlock radio controls to make changes'),401
        if request.path=='/api/debug-logs' and not self.admin():return jsonify(error='Unlock controls to view diagnostic logs'),401
    def headers(self,response):
        response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='SAMEORIGIN'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=(self)'
        if request.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
        if request.method in ('POST','PUT','PATCH','DELETE'):
            self.audit(request.method+' '+request.path,response.status_code)
        return response
