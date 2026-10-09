"""Nonblocking radio actions over the collector's existing connection."""
import copy,json,os,threading,time
from pathlib import Path
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import DecodeError
from meshtastic.protobuf import mesh_pb2,telemetry_pb2,admin_pb2,portnums_pb2
from pubsub import pub

REQUESTS={'traceroute':('Traceroute','TRACEROUTE_APP',mesh_pb2.RouteDiscovery),
          'position':('Request position','POSITION_APP',mesh_pb2.Position),
          'node_info':('Request node info','NODEINFO_APP',mesh_pb2.User),
          'neighbors':('Request neighbor info','NEIGHBORINFO_APP',mesh_pb2.NeighborInfo)}
METRICS={'device_metrics':'Device telemetry','environment_metrics':'Environment telemetry',
         'power_metrics':'Power telemetry','air_quality_metrics':'Air-quality telemetry',
         'local_stats':'Local statistics','health_metrics':'Health telemetry',
         'host_metrics':'Host telemetry','traffic_management_stats':'Traffic statistics'}
ADMIN={'favorite':('Add favorite','set_favorite_node'), 'unfavorite':('Remove favorite','remove_favorite_node'),
       'ignore':('Ignore node','set_ignored_node'),'unignore':('Unignore node','remove_ignored_node'),
       'remove_node':('Remove from Receiver node list','remove_by_nodenum'),
       'reboot':('Reboot Receiver','reboot_seconds'),'shutdown':('Shut down Receiver','shutdown_seconds'),
       'reset_nodes':('Reset Receiver node list','nodedb_reset'),
       'reset_config':('Reset Receiver configuration','factory_reset_config'),
       'factory_reset':('Factory-reset Receiver','factory_reset_device'),
       'metadata':('Request Receiver device info','get_device_metadata_request'),
       'connection':('Request Receiver connection status','get_device_connection_status_request')}
LOCAL={'reboot','shutdown','reset_nodes','reset_config','factory_reset','metadata','connection'}
DANGEROUS={'shutdown','reset_nodes','reset_config','factory_reset','remove_node','ignore'}

def catalog():
    return ([dict(id=k,label=v[0],local=False,confirm=False) for k,v in REQUESTS.items()]+
            [dict(id=k,label='Request '+v.lower(),local=False,confirm=False) for k,v in METRICS.items()]+
            [dict(id=k,label=v[0],local=k in LOCAL,confirm=k in DANGEROUS) for k,v in ADMIN.items()])

class RadioActions:
    def __init__(self,get_interface,log,base_dir=None,feed_enabled=True):
        self.get_interface=get_interface;self.log=log;self.lock=threading.RLock();self.jobs={};self.last_sent=-100
        self.base=Path(base_dir) if base_dir is not None else Path('@@DATA_DIR@@')
        self.feed_enabled=feed_enabled
        pub.subscribe(self.receive,'meshtastic.receive')

    def history(self):
        with self.lock:
            for job in self.jobs.values():
                if job['status'] in ('waiting','acknowledged') and time.time()-job['started']>180:
                    job.update(status='timeout',message='No matching response within three minutes. The node may be offline or not support this request.')
            return copy.deepcopy(list(self.jobs.values())[-30:][::-1])

    def run(self,request,iface):
        operation=request.get('operation');destination=request.get('destination');channel=request.get('channel');hops=request.get('hops')
        own=f'!{iface.localNode.nodeNum:08x}'
        if operation not in REQUESTS and operation not in METRICS and operation not in ADMIN:raise ValueError('Unsupported radio action')
        known = isinstance(destination, str) and (destination in (iface.nodes or {}) or destination == own)
        # A heard node can lack NODEINFO and therefore be absent from iface.nodes.
        # Permit read-only RF requests to identities already recorded by the collector.
        if not known and (operation in REQUESTS or operation in METRICS):
            import re, sqlite3
            if isinstance(destination, str) and re.fullmatch(r'![0-9a-f]{8}', destination) and 0 < int(destination[1:], 16) < 0xffffffff:
                with sqlite3.connect((self.base / 'mesh.db').resolve().as_uri() + '?mode=ro', uri=True, timeout=2) as db:
                    known = db.execute('SELECT 1 FROM nodes WHERE node_num=? AND node_id=? LIMIT 1', (int(destination[1:], 16), destination)).fetchone() is not None
        if not known:raise ValueError('Choose a known destination node')
        if operation in LOCAL and destination!=own:raise ValueError('This maintenance action applies only to Receiver')
        if operation in ('favorite','unfavorite','ignore','unignore','remove_node','traceroute') and destination==own:raise ValueError('Choose another node for this action')
        if type(channel) is not int or not 0<=channel<len(iface.localNode.channels) or not iface.localNode.channels[channel].role:raise ValueError('Choose an enabled channel')
        if type(hops) is not int or not 0<=hops<=7:raise ValueError('Hop limit must be 0 to 7')
        if operation in DANGEROUS and request.get('confirm_node')!=destination:raise ValueError('Type the destination node ID to confirm this action')
        self.history()
        with self.lock:
            if sum(j['status'] in ('waiting','acknowledged') for j in self.jobs.values())>=8:raise ValueError('Wait for existing requests to finish')
            if time.monotonic()-self.last_sent<5:raise ValueError('Wait five seconds between radio actions')
            key=request['request_id']
            job=dict(id=key,operation=operation,source=own,destination=destination,channel=channel,started=time.time(),status='waiting',message='Submitted; waiting for a response.',packet_id=None)
            self.jobs[key]=job
            while len(self.jobs)>100:self.jobs.pop(next(iter(self.jobs)))
            try:
                if operation == 'node_info' and destination == own:
                    admin=admin_pb2.AdminMessage(get_owner_request=True)
                    job.update(response_from=iface.localNode.nodeNum, expected='ADMIN_APP', transport='direct', message='Reading identity over the direct device connection.')
                    packet=iface.localNode._sendAdmin(admin,wantResponse=True)
                elif operation in ADMIN:
                    admin=admin_pb2.AdminMessage();field=ADMIN[operation][1]
                    if operation not in LOCAL:value=int(destination[1:],16)
                    elif operation in ('reboot','shutdown'):value=10
                    elif operation in ('factory_reset','reset_config'):value=1
                    else:value=True
                    setattr(admin,field,value)
                    if operation in ('reboot','shutdown','reset_nodes','reset_config','factory_reset'):
                        if operation in ('reset_nodes','reset_config','factory_reset'):
                            backup=self.base/'backups'/'radio-control';backup.mkdir(exist_ok=True,parents=True,mode=0o700)
                            path=backup/(str(time.time_ns())+'-'+operation+'.json')
                            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                            with os.fdopen(fd,'w') as f:json.dump({'config':MessageToDict(iface.localNode.localConfig),'modules':MessageToDict(iface.localNode.moduleConfig),'channels':[MessageToDict(c) for c in iface.localNode.channels]},f)
                        if operation!='reset_nodes' and self.feed_enabled:
                            import mf_feed
                            mf_feed.pause()
                    job['response_from']=iface.localNode.nodeNum
                    job['expected']='ADMIN_APP' if operation in ('metadata','connection') else 'ROUTING_APP'
                    packet=iface.localNode._sendAdmin(admin,wantResponse=operation in ('metadata','connection'))
                else:
                    if operation in METRICS:
                        payload=telemetry_pb2.Telemetry();getattr(payload,operation).SetInParent();port='TELEMETRY_APP'
                    else:
                        _,port,cls=REQUESTS[operation];payload=cls()
                        if operation == 'node_info':
                            # Node-info requests exchange the sender's real identity.
                            user=(iface.nodesByNum or {}).get(iface.localNode.nodeNum,{}).get('user') or {}
                            allowed={f.json_name for f in mesh_pb2.User.DESCRIPTOR.fields}
                            ParseDict({k:v for k,v in user.items() if k in allowed},payload,ignore_unknown_fields=True)
                            payload.id=own
                            if not payload.long_name or not payload.short_name:
                                raise ValueError('Local identity is unavailable; refresh the radio before requesting node info')
                    job['response_from']=int(destination[1:],16);job['expected']=port
                    packet=iface.sendData(payload,destinationId=destination,portNum=getattr(portnums_pb2.PortNum,port),wantResponse=True,wantAck=True,channelIndex=channel,hopLimit=hops)
                job['packet_id']=packet.id;self.last_sent=time.monotonic()
                if operation in ('reboot','shutdown','reset_nodes','reset_config','factory_reset'):
                    job.update(status='submitted',message='Command submitted. Receiver may disconnect; verify its state after reconnection. Reset actions may require local setup.')
                self.log('WEB_RADIO_ACTION',f'{operation}; destination={destination}; packet={packet.id}')
            except Exception:
                job.update(status='failed',message='Submission failed or is uncertain. Verify radio state before retrying.');raise
            return dict(message=job['message'],operation_id=key,packet_id=job['packet_id'])

    def receive(self,packet,interface):
        if interface is not self.get_interface() or not isinstance(packet,dict):return
        decoded=packet.get('decoded') or {};request_id=decoded.get('requestId')
        if request_id is None:return
        with self.lock:
            for job in self.jobs.values():
                if job['packet_id']!=request_id or job['status'] not in ('waiting','acknowledged','timeout'):continue
                port=decoded.get('portnum')
                if port=='ROUTING_APP':
                    reason=(decoded.get('routing') or {}).get('errorReason','NONE')
                    if reason!='NONE':job.update(status='failed',message='Radio reported: '+str(reason))
                    elif job['expected']=='ROUTING_APP':job.update(status='complete',message='Receiver acknowledged the command. Refresh its node list to verify.')
                    else:job.update(status='acknowledged',message='Delivery acknowledged; waiting for requested data.')
                    continue
                if packet.get('from')!=job['response_from'] or port!=job['expected']:continue
                try:
                    cls={'TRACEROUTE_APP':mesh_pb2.RouteDiscovery,'POSITION_APP':mesh_pb2.Position,'NODEINFO_APP':mesh_pb2.User,'NEIGHBORINFO_APP':mesh_pb2.NeighborInfo,'TELEMETRY_APP':telemetry_pb2.Telemetry,'ADMIN_APP':admin_pb2.AdminMessage}[port]
                    value=cls();value.ParseFromString(decoded['payload'])
                    result=MessageToDict(value)
                    if port=='ADMIN_APP' and job['operation']=='node_info':
                        if not value.HasField('get_owner_response'):continue
                        result=MessageToDict(value.get_owner_response,always_print_fields_with_no_presence=True)
                        result={k:v for k,v in result.items() if k in ('id','longName','shortName','hwModel','role')}
                    elif port=='ADMIN_APP':result={k:v for k,v in result.items() if k in ('getDeviceMetadataResponse','getDeviceConnectionStatusResponse')}
                    if port=='NODEINFO_APP':result={k:v for k,v in result.items() if k in ('id','longName','shortName','hwModel','role')}
                    if port=='TELEMETRY_APP' and job['operation'] in METRICS and value.WhichOneof('variant')!=job['operation']:continue
                    if port=='TRACEROUTE_APP':
                        result['route']=[f'!{n:08x}' for n in value.route];result['routeBack']=[f'!{n:08x}' for n in value.route_back]
                        result['returnRouteAvailable']='hopStart' in packet and len(value.snr_back)==len(value.route_back)+1
                    job.update(status='complete',message='Identity read directly from the device; this is not an RF reception.' if job.get('transport')=='direct' else 'Response received.',result=result)
                except (ValueError,TypeError,KeyError,DecodeError):job.update(status='failed',message='The response could not be decoded.')
