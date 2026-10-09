"""Local control socket hosted by the existing radio-owning collector."""
import copy
import hashlib
import json
import os
import socketserver
import threading
import time
from pathlib import Path
from google.protobuf.json_format import MessageToDict, ParseDict
from meshtastic.protobuf import admin_pb2, mesh_pb2

BASE = Path('@@DATA_DIR@@')
SOCKET = BASE / '.node-control.sock'
SECRET_WORDS = ('password', 'psk', 'private_key', 'session', 'admin_key')


def secret(name):
    return any(word in name for word in SECRET_WORDS)


def revision(message):
    return hashlib.sha256(message.SerializeToString(deterministic=True)).hexdigest()


def fields(message):
    result = []
    values = MessageToDict(message, preserving_proto_field_name=True, always_print_fields_with_no_presence=True)
    for f in message.DESCRIPTOR.fields:
        value = values.get(f.name)
        entry = dict(name=f.name, label=f.name.replace('_', ' ').capitalize(), repeated=f.is_repeated,
                     secret=secret(f.name), value=None if secret(f.name) else value)
        if f.message_type:
            entry.pop('value', None)
            entry['type'] = 'message'
            if f.is_repeated:
                entry['items'] = [fields(x) for x in getattr(message, f.name)]
                entry['prototype'] = fields(getattr(message, f.name).add())
                del getattr(message, f.name)[-1]
            else:
                entry['fields'] = fields(getattr(message, f.name))
        elif f.enum_type:
            entry.update(type='enum', options=[v.name for v in f.enum_type.values])
        elif f.type == f.TYPE_BOOL:
            entry['type'] = 'boolean'
        elif f.type in (f.TYPE_STRING, f.TYPE_BYTES):
            entry['type'] = 'bytes' if f.type == f.TYPE_BYTES else 'string'
        else:
            entry['type'] = 'number'
        if entry['secret']:
            entry['configured'] = bool(getattr(message, f.name))
        result.append(entry)
    return result


def merge(original, changes):
    if not isinstance(changes, dict):
        raise ValueError('Settings must be a group of fields')
    result = copy.deepcopy(original)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result



def reply_target(row_id, channel, destination, base=BASE):
    import sqlite3
    if type(row_id) is not int or row_id < 1 or destination != '^all':
        raise ValueError('Select a channel message to reply to')
    with sqlite3.connect((Path(base)/'mesh.db').resolve().as_uri()+'?mode=ro', uri=True) as db:
        row=db.execute("SELECT packet_id,channel,to_num,portnum FROM packets WHERE row_id=?",(row_id,)).fetchone()
    if not row:
        raise ValueError('The original message is no longer available')
    packet_id,original_channel,to_num,port=row
    # Protobuf omits channel zero. Channel slots belong to this receiver.
    original_channel = 0 if original_channel is None else original_channel

    if original_channel != channel or to_num != 0xffffffff or port != 'TEXT_MESSAGE_APP' or type(packet_id) is not int or not 0 < packet_id <= 0xffffffff:
        raise ValueError('Choose a broadcast message on the selected channel')
    return packet_id

class Control:
    def __init__(self, get_interface, log, base_dir=None, feed_enabled=True, expected_receiver_id=None):
        self.get_interface = get_interface
        self.log = log
        self.lock = threading.Lock()
        self.results = {}
        self.base = Path(base_dir) if base_dir is not None else BASE
        self.feed_enabled = feed_enabled
        self.expected_receiver_id = expected_receiver_id
        from radio_actions import RadioActions
        self.actions = RadioActions(get_interface,log,base_dir=self.base,feed_enabled=feed_enabled)

    def iface(self):
        iface = self.get_interface()
        if iface is None or not iface.isConnected.is_set():
            raise ValueError('Receiver is unavailable. The collector may be reconnecting or the mobile gateway may own the radio.')
        if self.expected_receiver_id is not None and iface.localNode.nodeNum != self.expected_receiver_id:
            raise ValueError('Receiver identity does not match configuration')
        return iface

    def section(self, iface, kind, name):
        if kind == 'owner':
            if name != 'identity':
                raise ValueError('Unknown identity settings group')
            owner = mesh_pb2.User()
            data = (iface.nodesByNum or {}).get(iface.localNode.nodeNum, {}).get('user', {})
            ParseDict(data, owner, ignore_unknown_fields=True)
            return owner
        if kind == 'channel':
            try:
                index = int(name)
            except (TypeError, ValueError):
                raise ValueError('Unknown channel') from None
            if not 0 <= index < len(iface.localNode.channels or []):
                raise ValueError('Unknown channel')
            return iface.localNode.channels[index]
        if kind not in ('config', 'module'):
            raise ValueError('Unknown settings group')
        parent = iface.localNode.localConfig if kind == 'config' else iface.localNode.moduleConfig
        container = admin_pb2.AdminMessage().set_config if kind == 'config' else admin_pb2.AdminMessage().set_module_config
        if name not in container.DESCRIPTOR.fields_by_name or name not in parent.DESCRIPTOR.fields_by_name:
            raise ValueError('Unsupported settings group')
        return getattr(parent, name)

    def snapshot(self, iface):
        node = iface.localNode
        groups = []
        owner = self.section(iface, 'owner', 'identity')
        editable = {'long_name', 'short_name', 'is_licensed', 'is_unmessagable'}
        groups.append(dict(kind='owner', name='identity', revision=revision(owner),
                           fields=[f for f in fields(owner) if f['name'] in editable]))
        for kind, parent, container in [('config', node.localConfig, admin_pb2.AdminMessage().set_config),
                                         ('module', node.moduleConfig, admin_pb2.AdminMessage().set_module_config)]:
            for f in container.DESCRIPTOR.fields:
                if f.name not in parent.DESCRIPTOR.fields_by_name or not f.message_type:
                    continue
                message = getattr(parent, f.name)
                groups.append(dict(kind=kind, name=f.name, revision=revision(message), fields=fields(copy.deepcopy(message))))
        channels = []
        for channel in node.channels or []:
            channels.append(dict(index=channel.index, name=channel.settings.name or ('Primary' if channel.index == 0 else 'Channel '+str(channel.index)),
                                 enabled=channel.role != 0, revision=revision(channel), fields=fields(copy.deepcopy(channel))))
        nodes = []
        for value in list((iface.nodes or {}).values()):
            user = value.get('user') or {}
            if user.get('id'):
                nodes.append(dict(id=user['id'], name=user.get('longName') or user.get('shortName') or user['id'],
                                  last_heard=value.get('lastHeard'), battery=(value.get('deviceMetrics') or {}).get('batteryLevel')))
        return dict(connected=True, feed_allowed=self.feed_enabled and __import__('mf_feed').public_mf(iface), node_id=f'!{node.nodeNum:08x}', groups=groups, channels=channels,
                    nodes=sorted(nodes, key=lambda n:n['name'].lower()),
                    metadata=MessageToDict(iface.metadata) if iface.metadata else {}, actions=__import__('radio_actions').catalog())

    def dispatch(self, request):
        with self.lock:
            action = request.get('action')
            if action in ('remote_read', 'remote_read_history'):
                raise ValueError('PKI probing has been removed; historical measurements are retained')
            if action == 'operations':
                return dict(operations=self.actions.history())
            iface = self.iface()
            if action == 'role_profile':
                # Read only already-cached configuration; never request radio data.
                return dict(node_id=f'!{iface.localNode.nodeNum:08x}',
                    captured_at=time.time(),
                    metadata=MessageToDict(iface.metadata) if iface.metadata else {},
                    device=MessageToDict(iface.localNode.localConfig.device, always_print_fields_with_no_presence=True),
                    lora=MessageToDict(iface.localNode.localConfig.lora, always_print_fields_with_no_presence=True),
                    favorites=[int(num) for num, n in (iface.nodesByNum or {}).items() if n.get('isFavorite')])
            if action == 'state':
                return self.snapshot(iface)
            request_id = request.get('request_id')
            if not isinstance(request_id, str) or not 16 <= len(request_id) <= 80:
                raise ValueError('Missing action identifier')
            if request_id in self.results:
                return self.results[request_id]
            # Reserve before sending so a timeout cannot cause a duplicate transmission.
            self.results[request_id] = dict(message='This action was already attempted. Check the radio before trying again.')
            if len(self.results) > 300:
                self.results.pop(next(iter(self.results)))
            if action == 'send':
                text = request.get('text', '')
                if not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > 228:
                    raise ValueError('Enter a message of 1–228 UTF-8 bytes')
                channel = int(request.get('channel', -1))
                self.section(iface, 'channel', channel)
                if not iface.localNode.channels[channel].role:
                    raise ValueError('That channel is disabled')
                destination = request.get('destination', '^all')
                if destination != '^all' and destination not in (iface.nodes or {}):
                    raise ValueError('Choose a known destination node')
                reply_id = reply_target(request['reply_row_id'], channel, destination, self.base) if request.get('reply_row_id') is not None else None
                packet = iface.sendText(text, destinationId=destination, channelIndex=channel, wantAck=destination != '^all', replyId=reply_id)
                # Save local submissions separately from received RF packets.
                try:
                    import sent_messages
                    sent_messages.record(packet, iface.localNode.nodeNum, text, database=self.base/'mesh.db')
                except Exception as error:
                    self.log('WEB_SENT_HISTORY_ERROR', type(error).__name__)
                # sendText does not emit a receive event for the local submission.
                # A queue failure must not turn a successful send into a resend prompt.
                try:
                    if self.feed_enabled:
                        import mf_feed
                        if mf_feed.capture_sent_text(packet, iface):
                            self.log('POTATO_SENT_TEXT_QUEUED', f'packet={packet.id}; public MediumFast')
                except Exception as error:
                    self.log('POTATO_QUEUE_ERROR', type(error).__name__)
                self.log('WEB_MESSAGE_SENT', f'channel={channel}; destination={destination}; packet={packet.id}')
                result = dict(message='Message submitted to Receiver. Delivery is not yet confirmed.', packet_id=packet.id)
            elif action == 'operation':
                result = self.actions.run(request,iface)
            elif action == 'swap_mediumfast_primary':
                raise ValueError('Use the channel editor; deployment-specific slot swapping is not supported')
            elif action == 'save':
                kind, name = request.get('kind'), request.get('name')
                current = self.section(iface, kind, name)
                if revision(current) != request.get('revision'):
                    raise ValueError('Settings changed since this form loaded. Refresh before applying changes.')
                changes = request.get('changes')
                if not changes:
                    raise ValueError('No changes to apply')
                if kind == 'owner' and (not isinstance(changes, dict) or set(changes)-{'long_name','short_name','is_licensed','is_unmessagable'}):
                    raise ValueError('Unsupported identity field')
                candidate = type(current)()
                try:
                    ParseDict(merge(MessageToDict(current, preserving_proto_field_name=True), changes), candidate)
                except Exception:
                    raise ValueError('One or more settings have an invalid value or unsupported field') from None
                if kind == 'channel':
                    if candidate.index != current.index:
                        raise ValueError('Channel slots cannot be moved here')
                    if len(candidate.settings.name.encode('utf-8')) > 11:
                        raise ValueError('Channel names must be at most 11 UTF-8 bytes')
                    if len(candidate.settings.psk) not in (0, 1, 16, 32):
                        raise ValueError('Channel key must decode to 0, 1, 16, or 32 bytes')
                    roles = [candidate.role if c.index == candidate.index else c.role for c in iface.localNode.channels]
                    if roles.count(1) != 1:
                        raise ValueError('Keep exactly one primary channel')
                if kind == 'owner':
                    if not candidate.long_name.strip() or len(candidate.long_name.encode('utf-8')) > 39:
                        raise ValueError('Long name must contain 1–39 UTF-8 bytes')
                    if not candidate.short_name.strip() or len(candidate.short_name.encode('utf-8')) > 4:
                        raise ValueError('Short name must contain 1–4 UTF-8 bytes')
                backup = self.base / 'backups' / 'radio-control'
                backup.mkdir(parents=True, exist_ok=True, mode=0o700)
                path = backup / (str(time.time_ns())+'-'+kind+'-'+str(name)+'.json')
                fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as f:
                    json.dump(dict(kind=kind, name=name, settings=MessageToDict(current, preserving_proto_field_name=True)), f)
                admin = admin_pb2.AdminMessage()
                if kind == 'channel':
                    admin.set_channel.CopyFrom(candidate)
                elif kind == 'owner':
                    admin.set_owner.CopyFrom(candidate)
                else:
                    getattr(admin.set_config if kind == 'config' else admin.set_module_config, name).CopyFrom(candidate)
                if self.feed_enabled:
                    import mf_feed
                    mf_feed.pause()
                iface.localNode._sendAdmin(admin)
                self.log('WEB_CONFIG_SUBMITTED', f'{kind}/{name}; previous settings backed up')
                result = dict(message='Changes submitted to Receiver; application is not yet confirmed. The radio may reboot. Refresh after it reconnects to verify.')
            else:
                raise ValueError('Unknown control action')
            self.results[request_id] = result
            return result


def start(get_interface, log):
    control = Control(get_interface, log)
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(15)
            try:
                line = self.rfile.readline(262145)
                if len(line) > 262144:
                    raise ValueError('Request too large')
                result = dict(ok=True, data=control.dispatch(json.loads(line)))
            except Exception as error:
                # Never echo supplied secrets or protobuf parser values.
                result = dict(ok=False, error=str(error) if isinstance(error, ValueError) else 'Radio operation failed; refresh and check the connection.')
            self.wfile.write(json.dumps(result).encode()+b'\n')
    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True
    SOCKET.unlink(missing_ok=True)
    server = Server(str(SOCKET), Handler)
    os.chmod(SOCKET, 0o600)
    threading.Thread(target=server.serve_forever, daemon=True, name='node-control').start()
    return server
