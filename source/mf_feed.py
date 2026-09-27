"""Opt-in public broadcast export; no private-channel or per-node exceptions."""
from contextlib import closing
import hashlib,json,math,re,sqlite3,time
from pathlib import Path
from google.protobuf.json_format import ParseDict
from meshtastic.protobuf import mesh_pb2,telemetry_pb2

ROOT=Path('@@DATA_DIR@@')
OUTBOX=ROOT/'potato-feed/outbox.db'
PAUSED=OUTBOX.with_name('capture-paused')
UPLOAD_HOLD=OUTBOX.with_name('upload-hold')
ENABLED=@@ENABLE_POTATO@@
BASE_URL='@@POTATO_URL@@'
SLOT=@@POTATO_CHANNEL_SLOT@@
ALLOWED=@@POTATO_TYPES@@
GUNIT_ID='@@RECEIVER_ID@@'
GUNIT_NUM=@@RECEIVER_NUM@@
DEFAULT_KEY=bytes.fromhex('d4f1bb3a20290759f0bcffabcf4e6901') # Standard public Meshtastic key, not an operator secret.
META={'snr':(-100,100),'rssi':(-200,0),'hop_limit':(0,7),'hop_start':(0,7),'lora_freq':(100,3000)}
SECTIONS={'TEXT_MESSAGE_APP':'text','NODEINFO_APP':'user','POSITION_APP':'position','TELEMETRY_APP':'telemetry','NEIGHBORINFO_APP':'neighborinfo'}
USER_FIELDS={'id','longName','shortName','hwModel','role','isLicensed','isUnmessagable'}
POLICY=hashlib.sha256(json.dumps([BASE_URL,SLOT,sorted(ALLOWED),GUNIT_ID,'public-broadcast-v1']).encode()).hexdigest()
POLICY_STARTED=0

def clean_fields(data, descriptor):
    if not isinstance(data, dict):
        raise ValueError('Invalid section')
    result = {}
    for field in descriptor.fields:
        key = field.json_name if field.json_name in data else field.name
        if key not in data:
            continue
        value = data[key]
        def scalar(value):
            if field.message_type:
                return clean_fields(value, field.message_type)
            if field.type == field.TYPE_BOOL:
                if type(value) is not bool: raise ValueError('Invalid boolean')
            elif field.type in (field.TYPE_STRING, field.TYPE_BYTES):
                if not isinstance(value,str) or len(value)>2048: raise ValueError('Invalid string')
            elif field.enum_type:
                if not isinstance(value,(str,int)) or isinstance(value,bool): raise ValueError('Invalid enum')
            elif type(value) not in (int,float) or not math.isfinite(value):
                raise ValueError('Invalid number')
            return value
        if field.is_repeated:
            if not isinstance(value,list) or len(value)>64: raise ValueError('Invalid list')
            result[field.json_name]=[scalar(v) for v in value]
        else:
            result[field.json_name]=scalar(value)
    return result


def clean_section(port, value, sender_id):
    if port == 'TEXT_MESSAGE_APP':
        if not isinstance(value,str) or not value.strip() or len(value.encode('utf-8'))>228:
            raise ValueError('Invalid text')
        return value
    cls={'NODEINFO_APP':mesh_pb2.User,'POSITION_APP':mesh_pb2.Position,'TELEMETRY_APP':telemetry_pb2.Telemetry,'NEIGHBORINFO_APP':mesh_pb2.NeighborInfo}[port]
    cleaned=clean_fields(value,cls.DESCRIPTOR)
    if port=='NODEINFO_APP':
        cleaned={k:v for k,v in cleaned.items() if k in USER_FIELDS}
        if cleaned.get('id',sender_id)!=sender_id: raise ValueError('Sender mismatch')
        cleaned['id']=sender_id
        if not any(k in cleaned for k in ('longName','shortName','hwModel','role')): raise ValueError('Empty node info')
    elif port=='POSITION_APP':
        for source,target,maximum in [('latitude','latitudeI',90),('longitude','longitudeI',180)]:
            if target not in cleaned and source in value:
                number=value[source]
                if type(number) not in (int,float) or not math.isfinite(number) or abs(number)>maximum: raise ValueError('Invalid coordinate')
                cleaned[target]=round(number*1e7)
        lat,lon=cleaned.get('latitudeI'),cleaned.get('longitudeI')
        if lat is None or lon is None or abs(lat)>900000000 or abs(lon)>1800000000 or (lat==0 and lon==0): raise ValueError('No valid position')
    elif port=='NEIGHBORINFO_APP':
        if cleaned.get('nodeId') != int(sender_id[1:],16): raise ValueError('Neighbor sender mismatch')
        for neighbor in cleaned.get('neighbors',[]):
            if type(neighbor.get('nodeId')) is not int or not 0 < neighbor['nodeId'] < 0xffffffff:
                raise ValueError('Invalid neighbor node')
    elif not any(isinstance(v,dict) and v for v in cleaned.values()):
        raise ValueError('No telemetry metrics')
    try:
        ParseDict(cleaned,cls())  # Validate enum names, ranges and protobuf oneof rules.
    except Exception:
        raise ValueError('Invalid decoded data') from None
    return cleaned


def initialize():
    global POLICY_STARTED
    OUTBOX.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    policy_file=OUTBOX.with_name('policy.json')
    try:old=json.loads(policy_file.read_text())
    except (OSError,ValueError):old={}
    if ENABLED and old.get('policy')!=POLICY:
        old={'policy':POLICY,'started':int(time.time())};policy_file.write_text(json.dumps(old))
    POLICY_STARTED=old.get('started',0) if ENABLED else 0
    with closing(sqlite3.connect(OUTBOX,timeout=2)) as db,db:
        db.execute('CREATE TABLE IF NOT EXISTS queue(sequence INTEGER PRIMARY KEY,policy TEXT NOT NULL,payload TEXT NOT NULL,packet_id INTEGER NOT NULL,sender TEXT NOT NULL,captured_at INTEGER NOT NULL,sent_at INTEGER,UNIQUE(packet_id,sender))')
    OUTBOX.chmod(0o600)

def pause():
    PAUSED.parent.mkdir(parents=True,exist_ok=True);PAUSED.write_text('Public feed capture paused')

def public_mf(iface):
    if not ENABLED or UPLOAD_HOLD.exists() or not POLICY_STARTED or iface is None or not iface.isConnected.is_set():return False
    try:
        node=iface.localNode;channel=node.channels[SLOT];lora=node.localConfig.lora
        preset=lora.DESCRIPTOR.fields_by_name['modem_preset'].enum_type.values_by_number[lora.modem_preset].name
        return (node.nodeNum==GUNIT_NUM and channel.index==SLOT and channel.role!=0
          and channel.settings.name in ('','MediumFast') and bytes(channel.settings.psk) in (b'\x01',DEFAULT_KEY)
          and lora.use_preset and preset=='MEDIUM_FAST')
    except (AttributeError,IndexError,KeyError,TypeError):return False

def connected(iface):
    if public_mf(iface):PAUSED.unlink(missing_ok=True);return True
    pause();return False

def valid_meta(name,value):
    low,high=META[name]
    return type(value) in (int,float) and math.isfinite(value) and low<=value<=high and (name not in ('rssi','hop_limit','hop_start') or type(value) is int)

def eligible_payload(packet,iface):
    if not isinstance(packet,dict) or not public_mf(iface):return None
    decoded=packet.get('decoded')
    if not isinstance(decoded,dict) or decoded.get('portnum') not in ALLOWED:return None
    if type(packet.get('channel',0)) is not int or packet.get('channel',0)!=SLOT:return None
    if type(packet.get('to')) is not int or packet['to']!=0xffffffff or packet.get('toId') not in (None,'^all','!ffffffff'):return None
    if packet.get('pkiEncrypted') or packet.get('encrypted') or packet.get('viaMqtt') or packet.get('transportMechanism') in ('TRANSPORT_INTERNAL','TRANSPORT_MQTT'):return None
    sender,number,received=packet.get('from'),packet.get('id'),packet.get('rxTime')
    if any(type(v) is not int for v in (sender,number,received)):return None
    if not 0<sender<0xffffffff or sender==GUNIT_NUM or not 0<number<=0xffffffff or not POLICY_STARTED<=received<=time.time()+60:return None
    ident=f'!{sender:08x}'
    if packet.get('fromId') not in (None,ident):return None
    port=decoded['portnum'];section=SECTIONS[port]
    try:value=clean_section(port,decoded.get(section),ident)
    except (ValueError,TypeError,KeyError,OverflowError):return None
    result=dict(id=number,rx_time=received,from_id=ident,to_id='^all',channel=SLOT,channel_name='MediumFast',portnum=port,protocol='meshtastic',ingestor=GUNIT_ID)
    result[section]=value
    for src,target in [('rxSnr','snr'),('rxRssi','rssi'),('hopLimit','hop_limit'),('hopStart','hop_start')]:
        if valid_meta(target,packet.get(src)):result[target]=packet[src]
    from radio_frequency import from_iface
    frequency=from_iface(iface)
    if valid_meta('lora_freq',frequency):result['lora_freq']=frequency
    return result

def validate_payload(p):
    if not ENABLED or not isinstance(p,dict) or p.get('portnum') not in ALLOWED:return False
    section=SECTIONS[p['portnum']]
    required={'id','rx_time','from_id','to_id','channel','channel_name','portnum','protocol','ingestor',section}
    if not required<=p.keys() or p.keys()-required-META.keys():return False
    if (p['ingestor'],p['channel'],p['channel_name'],p['protocol'],p['to_id'])!=(GUNIT_ID,SLOT,'MediumFast','meshtastic','^all'):return False
    if not isinstance(p['from_id'],str) or not re.fullmatch('![0-9a-f]{8}',p['from_id']) or not 0<int(p['from_id'][1:],16)<0xffffffff or p['from_id']==GUNIT_ID:return False
    if type(p['id']) is not int or not 0<p['id']<=0xffffffff or type(p['rx_time']) is not int or not POLICY_STARTED<=p['rx_time']<=time.time()+60:return False
    if any(not valid_meta(k,p[k]) for k in META if k in p):return False
    try:return clean_section(p['portnum'],p[section],p['from_id'])==p[section]
    except (ValueError,KeyError,TypeError,OverflowError):return False

def capture(packet,iface):
    if not ENABLED or PAUSED.exists():return False
    payload=eligible_payload(packet,iface)
    if payload is None:return False
    with closing(sqlite3.connect(OUTBOX,timeout=.2)) as db,db:
        # Bound pending storage if no uploader is running.
        if db.execute('SELECT count(*) FROM queue WHERE sent_at IS NULL').fetchone()[0]>=10000:return False
        db.execute('INSERT OR IGNORE INTO queue(policy,payload,packet_id,sender,captured_at) VALUES(?,?,?,?,?)',(POLICY,json.dumps(payload),payload['id'],payload['from_id'],int(time.time())))
    return True

def capture_sent_text(packet,iface):
    # Local UI submissions are not independently confirmed over RF.
    return False
