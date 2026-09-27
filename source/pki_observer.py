"""Read-only PKI observations using the collector's existing radio connection."""
import copy
import json
import math
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
from google.protobuf.json_format import MessageToDict
from meshtastic.protobuf import admin_pb2, mesh_pb2, portnums_pb2, telemetry_pb2
from pubsub import pub

BASE = Path('@@DATA_DIR@@')
INTERVAL = 60
RESPONSE_WAIT = 300
CONFIGS = {'lora':'LORA_CONFIG','device':'DEVICE_CONFIG','position':'POSITION_CONFIG','power':'POWER_CONFIG'}
MODULES = {'telemetry':'TELEMETRY_CONFIG','neighbor_info':'NEIGHBORINFO_CONFIG','traffic_management':'TRAFFICMANAGEMENT_CONFIG'}
KINDS = ('lora','device','local_stats','device_metrics','metadata','channel_0','channel_1',
         'position','power','telemetry','neighbor_info','traffic_management') + tuple('channel_'+str(i) for i in range(2,8))

def scrub(value):
    if isinstance(value, dict):
        return {k:scrub(v) for k,v in value.items() if k!='raw' and not any(
            s in k.lower().replace('_','') for s in ('key','password','psk','session'))}
    if isinstance(value,list):return [scrub(v) for v in value]
    return value

def interval(kind):
    return 900 if kind=='local_stats' else 3600 if kind=='device_metrics' else 86400

def backoff(failures):
    return min(21600,900*2**min(max(0,failures-1),5))

class RemoteObserver:
    def __init__(self,get_interface,log,db_path=None,start=True):
        self.get_interface,self.log=get_interface,log
        self.db_path=Path(db_path or BASE/'mesh.db')
        self.lock=threading.RLock()
        self.last_send=time.time() # Give the radio a minute to finish its startup sync.
        self.last_busy=0
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS pki_jobs (
              id TEXT PRIMARY KEY,node_num INTEGER NOT NULL,kind TEXT NOT NULL,
              requested_at REAL NOT NULL,packet_id INTEGER,status TEXT NOT NULL,
              received_at REAL,error TEXT);
            CREATE INDEX IF NOT EXISTS pki_jobs_request ON pki_jobs(packet_id);
            CREATE INDEX IF NOT EXISTS pki_jobs_node ON pki_jobs(node_num,kind,requested_at);
            CREATE TABLE IF NOT EXISTS pki_samples (
              job_id TEXT PRIMARY KEY,node_num INTEGER NOT NULL,kind TEXT NOT NULL,
              observed_at REAL,received_at REAL NOT NULL,payload_json TEXT NOT NULL,
              rx_rssi REAL,rx_snr REAL,hops INTEGER,transport TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS pki_samples_time ON pki_samples(node_num,kind,observed_at);
            CREATE TABLE IF NOT EXISTS pki_schedule (
              node_num INTEGER NOT NULL,kind TEXT NOT NULL,next_at REAL NOT NULL,
              failures INTEGER NOT NULL DEFAULT 0,last_status TEXT,last_success REAL,
              PRIMARY KEY(node_num,kind));
            ''')
            # Preserve in-flight requests across reloads; do not retransmit on startup.
            latest=c.execute('SELECT MAX(requested_at) FROM pki_jobs').fetchone()[0]
            if latest:self.last_send=max(self.last_send,latest)
        pub.subscribe(self.receive,'meshtastic.receive')
        if start:threading.Thread(target=self.loop,daemon=True,name='pki-observer').start()

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.db_path,timeout=3)
        c.row_factory=sqlite3.Row
        try:
            with c:yield c
        finally:c.close()

    def targets(self,c):
        return c.execute("SELECT node_num,COALESCE(NULLIF(node_id,''),printf('!%08x',node_num)) node_id,long_name,short_name,last_heard FROM nodes WHERE role='CLIENT' AND (lower(long_name) LIKE '@@NODE_PREFIX_LOWER@@%' OR lower(short_name) LIKE '@@NODE_PREFIX_LOWER@@%') AND node_num!=@@RECEIVER_NUM@@ ORDER BY last_heard DESC").fetchall()

    def finish(self,c,job,status,now,error=None):
        c.execute('UPDATE pki_jobs SET status=?,received_at=?,error=? WHERE id=?',(status,now,error,job['id']))
        previous=c.execute('SELECT failures FROM pki_schedule WHERE node_num=? AND kind=?',(job['node_num'],job['kind'])).fetchone()
        failures=0 if status=='response' else (previous['failures'] if previous else 0)+1
        delay=interval(job['kind']) if status=='response' else 86400 if status=='empty_response' else backoff(failures)
        c.execute('''INSERT INTO pki_schedule(node_num,kind,next_at,failures,last_status,last_success) VALUES(?,?,?,?,?,?)
            ON CONFLICT(node_num,kind) DO UPDATE SET next_at=excluded.next_at,failures=excluded.failures,
            last_status=excluded.last_status,last_success=COALESCE(excluded.last_success,pki_schedule.last_success)''',
            (job['node_num'],job['kind'],now+delay,failures,status,now if status=='response' else None))

    def expire(self,c,now):
        for job in c.execute("SELECT * FROM pki_jobs WHERE status IN ('waiting','acknowledged') AND requested_at<?",(now-RESPONSE_WAIT,)).fetchall():
            self.finish(c,job,'timeout',now,'No data reply within five minutes')

    def history(self):
        with self.lock,self.db() as c:
            self.expire(c,time.time())
            return [dict(id=j['id'],destination=f"!{j['node_num']:08x}",read=j['kind'],started=j['requested_at'],
                         status=j['status'],packet_id=j['packet_id'],error=j['error'])
                    for j in c.execute('SELECT * FROM pki_jobs ORDER BY requested_at DESC LIMIT 120')]

    def run(self,request,iface):
        destination=request.get('destination','')
        if not isinstance(destination,str) or len(destination)!=9 or not destination.startswith('!'):raise ValueError('Choose a known local CLIENT node')
        target=int(destination[1:],16);kind=request.get('read');rid=request['request_id']
        if kind not in KINDS:raise ValueError('Unsupported read-only diagnostic')
        with self.lock,self.db() as c:
            if not any(n['node_num']==target for n in self.targets(c)):raise ValueError('Only known local CLIENT nodes are authorized')
            self.expire(c,time.time())
            existing=c.execute('SELECT id FROM pki_jobs WHERE id=?',(rid,)).fetchone()
            if existing:return dict(message='Already attempted',id=rid)
            pending=c.execute("SELECT node_num FROM pki_jobs WHERE status IN ('waiting','acknowledged')").fetchall()
            if len(pending)>=2 or any(j['node_num']==target for j in pending):raise ValueError('Waiting for existing remote requests')
            if time.time()-self.last_send<INTERVAL:raise ValueError('Waiting for the one-minute radio spacing')
            message=admin_pb2.AdminMessage();port=portnums_pb2.ADMIN_APP
            if kind in CONFIGS:message.get_config_request=getattr(admin_pb2.AdminMessage,CONFIGS[kind])
            elif kind in MODULES:message.get_module_config_request=getattr(admin_pb2.AdminMessage,MODULES[kind])
            elif kind.startswith('channel_'):message.get_channel_request=int(kind[8:])+1
            elif kind=='metadata':message.get_device_metadata_request=True
            else:
                message=telemetry_pb2.Telemetry();getattr(message,kind).SetInParent();port=portnums_pb2.TELEMETRY_APP
            now=time.time();self.last_send=now
            c.execute('INSERT INTO pki_jobs(id,node_num,kind,requested_at,status) VALUES(?,?,?,?,?)',(rid,target,kind,now,'waiting'))
            c.commit() # Durable reservation before transmitting; never silently repeat on a lost return.
            try:
                packet=iface.sendData(message,destinationId=target,portNum=port,wantAck=True,
                    wantResponse=True,channelIndex=0,hopLimit=7,pkiEncrypted=True)
                c.execute('UPDATE pki_jobs SET packet_id=? WHERE id=?',(packet.id,rid))
                c.commit()
                self.log('PKI_READ_SENT',f'{destination}; {kind}; packet={packet.id}')
                return dict(id=rid,packet_id=packet.id,status='waiting')
            except Exception as e:
                job=c.execute('SELECT * FROM pki_jobs WHERE id=?',(rid,)).fetchone()
                self.finish(c,job,'send_error',time.time(),type(e).__name__)
                c.commit()
                self.log('PKI_READ_FAILED',f'{destination}; {kind}; {type(e).__name__}')
                return dict(id=rid,status='send_error')

    def receive(self,packet,interface=None):
        try:self._receive(packet,interface)
        except Exception as e:self.log('PKI_OBSERVATION_ERROR',type(e).__name__)

    def _receive(self,packet,interface):
        d=packet.get('decoded') or {};req=d.get('requestId')
        if not req:return
        with self.lock,self.db() as c:
            job=c.execute('SELECT * FROM pki_jobs WHERE packet_id=? ORDER BY requested_at DESC LIMIT 1',(req,)).fetchone()
            if not job or job['status'] in ('response','empty_response'):return
            if time.time()-job['requested_at']>3600:return
            now=time.time();port=d.get('portnum')
            if port=='ROUTING_APP':
                r=mesh_pb2.Routing();r.ParseFromString(d.get('payload',b''));error=mesh_pb2.Routing.Error.Name(r.error_reason)
                if error!='NONE' and job['status'] in ('waiting','acknowledged'):self.finish(c,job,'rejected',now,error)
                elif error=='NONE' and job['status']=='waiting':c.execute("UPDATE pki_jobs SET status='acknowledged' WHERE id=?",(job['id'],))
                return
            if packet.get('from')!=job['node_num']:return
            kind=job['kind'];observed=now
            if kind in ('local_stats','device_metrics'):
                if port!='TELEMETRY_APP':return
                message=telemetry_pb2.Telemetry();message.ParseFromString(d.get('payload',b''))
                if not message.HasField(kind):return
                data=MessageToDict(getattr(message,kind),preserving_proto_field_name=True,always_print_fields_with_no_presence=True)
                ts=message.time
                observed=ts if job['requested_at']-120<=ts<=now+120 else None
                data['remote_time']=ts;data['clock_valid']=observed is not None
            else:
                if port!='ADMIN_APP':return
                message=admin_pb2.AdminMessage();message.ParseFromString(d.get('payload',b''))
                expected='get_config_response' if kind in CONFIGS else 'get_module_config_response' if kind in MODULES else 'get_channel_response' if kind.startswith('channel_') else 'get_device_metadata_response'
                if message.WhichOneof('payload_variant')!=expected:return
                response=getattr(message,expected)
                if kind in CONFIGS or kind in MODULES:
                    if not response.HasField(kind):self.finish(c,job,'empty_response',now,'Node returned an empty settings group');return
                    response=getattr(response,kind)
                if kind.startswith('channel_') and response.index!=int(kind[8:]):return
                data=MessageToDict(response,preserving_proto_field_name=True,always_print_fields_with_no_presence=True)
                if kind.startswith('channel_') and interface is not None:
                    from meshtastic.protobuf import config_pb2
                    preset=config_pb2.Config.LoRaConfig.ModemPreset.Name(interface.localNode.localConfig.lora.modem_preset).replace('_','').lower()
                    name=(response.settings.name or preset).replace('_','').lower()
                    remote_key=bytes(response.settings.psk)
                    matches=[]
                    for ch in interface.localNode.channels or []:
                        local_name=(ch.settings.name or preset).replace('_','').lower()
                        if local_name==name:
                            from mf_feed import DEFAULT_KEY
                            normalize=lambda k:DEFAULT_KEY if k==b'\x01' else k
                            matches.append(normalize(bytes(ch.settings.psk))==normalize(remote_key))
                    data['key_matches_gunit_named_channel']=any(matches) if matches else None
            data=scrub(data)
            hops=None
            if 'hopStart' in packet and 'hopLimit' in packet and packet['hopStart']>=packet['hopLimit']:hops=packet['hopStart']-packet['hopLimit']
            c.execute('INSERT OR IGNORE INTO pki_samples VALUES(?,?,?,?,?,?,?,?,?,?)',
                (job['id'],job['node_num'],kind,observed,now,json.dumps(data),packet.get('rxRssi'),packet.get('rxSnr'),hops,'PKI_REQUEST'))
            self.finish(c,job,'response',now)
            c.commit()
            self.log('PKI_READ_RECEIVED',f"!{job['node_num']:08x}; {kind}")

    def tick(self):
        iface=self.get_interface()
        if iface is None or not iface.isConnected.is_set():return
        now=time.time()
        if now-self.last_send<INTERVAL:return
        # Let normal traffic take precedence when Receiver reports a busy channel.
        metrics=((iface.nodesByNum or {}).get(iface.localNode.nodeNum,{}) or {}).get('deviceMetrics',{})
        if metrics.get('channelUtilization',0)>20 or metrics.get('airUtilTx',0)>5:return
        choice=None
        with self.lock,self.db() as c:
            self.expire(c,now)
            pending=c.execute("SELECT node_num FROM pki_jobs WHERE status IN ('waiting','acknowledged')").fetchall()
            if len(pending)>=2:return
            blocked={r['node_num'] for r in pending}
            options=[]
            for n in self.targets(c):
                num=n['node_num']
                if num in blocked:continue
                schedule={r['kind']:dict(r) for r in c.execute('SELECT * FROM pki_schedule WHERE node_num=?',(num,))}
                proven=any(r['last_success'] and now-r['last_success']<86400 for r in schedule.values())
                kinds=KINDS if proven else ('lora',)
                # Telemetry first on reachable nodes; stagger the initial configuration inventory.
                for kind in kinds:
                    row=schedule.get(kind)
                    if row and row['next_at']>now:continue
                    priority=0 if proven and kind=='local_stats' else 1 if proven and kind=='device' else 2 if proven and kind=='device_metrics' else 3 if kind=='lora' else 4
                    options.append((priority,row['next_at'] if row else 0,-(n['last_heard'] or 0),num,kind))
            if options:
                _,_,_,num,kind=min(options);choice=(num,kind)
        if choice:
            num,kind=choice
            self.run(dict(destination=f'!{num:08x}',read=kind,request_id='pki-'+uuid.uuid4().hex),iface)

    def loop(self):
        while True:
            try:self.tick()
            except Exception as e:self.log('PKI_SCHEDULER_ERROR',type(e).__name__)
            time.sleep(10)
