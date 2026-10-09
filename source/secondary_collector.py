"""Persistent Secondary receiver collector and controls, sharing one verified radio connection."""
import fcntl
import json
import os
import signal
import socket
import socketserver
import threading
import time
from pathlib import Path

from meshtastic.tcp_interface import TCPInterface
from pubsub import pub
from node_control_bridge import Control
from recovery_runtime import configure_socket, recovery_sleep, watchdog
from receiver_provenance import observation_type, radio_profile
import secondary_storage as store

ROOT = Path('@@DATA_DIR@@')
ENABLED = @@SECONDARY_ENABLED@@
HOST = @@SECONDARY_RADIO_HOST_PY@@
PORT = @@SECONDARY_RADIO_PORT@@
EXPECTED = @@SECONDARY_RECEIVER_NUM@@
LABEL = @@SECONDARY_LABEL_PY@@
CONTROLS = @@ENABLE_RADIO_CONTROLS@@ and @@SECONDARY_ENABLE_CONTROLS@@
SOCKET = ROOT / '.secondary-control.sock'
STATUS = store.BASE_DIR / 'status.json'
running = True
radio = None
ready = False
session_id = None
session_started = None
last_packet = None
last_update = None
profile = None
error = None
guard = threading.RLock()


class ReceiverIdentityError(ValueError):
    """A wrong receiver must not be retried automatically."""


def current():
    with guard:
        return radio if ready and radio is not None and radio.localNode.nodeNum == EXPECTED else None


def publish_status():
    with guard:
        status = dict(receiver=LABEL, receiver_id=f'!{EXPECTED:08x}', connected=bool(ready and radio and radio.isConnected.is_set()),
                      heartbeat=store.now_iso(), session_id=session_id, last_packet=last_packet,
                      last_update=last_update, profile=profile, error=error)
    tmp = STATUS.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        json.dump(status, output)
    tmp.replace(STATUS)


def receive(packet, interface):
    global last_packet, last_update
    if not isinstance(packet, dict):
        return
    # Handshake replay is excluded; collection begins after identity and node snapshot validation.
    with guard:
        if not ready or interface is not radio or interface.localNode.nodeNum != EXPECTED:
            return
        packet = dict(packet)
        packet['_collectorObservationType'] = observation_type(packet, session_started, time.time())
        store.on_receive(packet, interface)
        last_update = store.now_iso()
        transport = packet.get('transportMechanism')
        if packet['_collectorObservationType'] == 'LIVE' and packet.get('from') != EXPECTED and not packet.get('viaMqtt') and transport not in ('TRANSPORT_MQTT', 'TRANSPORT_INTERNAL'):
            if transport == 'TRANSPORT_LORA' or 'rxSnr' in packet or 'rxRssi' in packet:
                last_packet = last_update


class RecoveringInterface(TCPInterface):
    def myConnect(self):
        sock = socket.create_connection((self.hostname, self.portNumber), timeout=10)
        try:
            configure_socket(sock)
            sock.settimeout(None)
        except Exception:
            sock.close()
            raise
        self.socket = sock

    def _reconnect(self):
        self.isConnected.clear()
        self._wantExit = True
        self.failure = ConnectionError('Secondary receiver transport disconnected')
        raise self.failure


def serve_controls():
    control = Control(current, store.log_event, base_dir=store.BASE_DIR, feed_enabled=False, expected_receiver_id=EXPECTED)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(15)
            try:
                line = self.rfile.readline(65537)
                if len(line) > 65536:
                    raise ValueError('Request too large')
                body = json.loads(line)
                if not isinstance(body, dict):
                    raise ValueError('Invalid control request')
                # Control's existing lock preserves serialization and action idempotency.
                result = dict(ok=True, data=control.dispatch(body))
            except Exception as exc:
                result = dict(ok=False, error=str(exc) if isinstance(exc, ValueError)
                              else 'Secondary receiver operation failed; refresh before trying again.')
            self.wfile.write(json.dumps(result).encode() + b'\n')

    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    SOCKET.unlink(missing_ok=True)
    server = Server(str(SOCKET), Handler)
    SOCKET.chmod(0o600)
    threading.Thread(target=server.serve_forever, daemon=True, name='secondary-controls').start()
    return server


def disconnect():
    global radio, ready, session_id
    with guard:
        ready = False
        old = radio
        radio = None
        previous_session, session_id = session_id, None
    try:
        if previous_session is not None:
            with store.db_lock:
                store.db.execute('UPDATE collection_sessions SET ended_at=? WHERE session_id=? AND ended_at IS NULL',
                                 (store.now_iso(), previous_session))
                store.db.commit()
        publish_status()
    finally:
        if old is not None:
            try:
                old.close()
            except Exception:
                pass


def stop(signum, frame):
    global running
    running = False


def main():
    global radio, ready, session_id, session_started, profile, error, running
    if not ENABLED or not HOST or not 0 < EXPECTED < 0xffffffff:
        raise SystemExit(78)
    os.umask(0o077)
    store.BASE_DIR.mkdir(mode=0o700, exist_ok=True)
    lock = (store.BASE_DIR / 'collector.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    store.db = store.open_database()
    # Bound a previously interrupted session using its final heartbeat, never assume coverage through downtime.
    try:
        previous = json.loads(STATUS.read_text())
        end = previous.get('heartbeat') or store.now_iso()
    except (OSError, ValueError):
        end = store.now_iso()
    store.db.execute('UPDATE collection_sessions SET ended_at=? WHERE ended_at IS NULL', (end,))
    store.db.commit()
    store.log_event('START', 'Secondary receiver passive collection starting')
    server = serve_controls() if CONTROLS else None
    pub.subscribe(receive, 'meshtastic.receive')
    identity_failed = False
    try:
        while running:
            error = None
            publish_status()
            try:
                store.log_event('CONNECTING', 'Connecting to the configured secondary receiver')
                candidate = RecoveringInterface(HOST, portNumber=PORT, connectNow=False, timeout=45)
                radio = candidate
                candidate.connect()
                if candidate.localNode.nodeNum != EXPECTED:
                    raise ReceiverIdentityError('Receiver identity does not match configuration; collection and controls blocked')
                if not candidate.isConnected.is_set():
                    raise ConnectionError('Secondary receiver did not finish connecting')
                store.log_event('CONNECTED', 'Verified configured secondary receiver')
                store.snapshot_nodes(candidate)
                with guard, store.db_lock:
                    profile = radio_profile(candidate)
                    started = store.now_iso()
                    session_started = time.time()
                    session_id = store.db.execute('INSERT INTO collection_sessions(started_at,profile_json) VALUES (?,?)',
                                                 (started, json.dumps(profile))).lastrowid
                    store.db.commit()
                    store.last_receive_monotonic = time.monotonic()
                    ready = True
                publish_status()
                status_at = time.monotonic()
                while running:
                    recovery_sleep(5)
                    thread = getattr(candidate, '_rxThread', None)
                    if not candidate.isConnected.is_set() or getattr(candidate, 'failure', None) or getattr(candidate, '_wantExit', False) or (thread and not thread.is_alive()):
                        raise ConnectionError('Secondary receiver connection lost')
                    # TCP keepalive checks reachability; a quiet RF mesh is not an outage.
                    if time.monotonic() - status_at >= 10:
                        publish_status()
                        status_at = time.monotonic()
            except ReceiverIdentityError as exc:
                error = str(exc)
                identity_failed, running = True, False
                store.log_event('IDENTITY_ERROR', error)
            except Exception as exc:
                error = str(exc) if isinstance(exc, ValueError) else 'Secondary receiver unavailable; retrying automatically'
                store.log_event('CONNECTION_ERROR', error)
            finally:
                disconnect()
            if running:
                recovery_sleep(15)
    finally:
        try:
            disconnect()
        finally:
            pub.unsubscribe(receive, 'meshtastic.receive')
            if server is not None:
                server.shutdown()
                server.server_close()
                SOCKET.unlink(missing_ok=True)
            store.log_event('STOP', 'Secondary receiver collector stopped')
            store.db.close()
            lock.close()
    if identity_failed:
        raise SystemExit(78)


if __name__ == '__main__':
    main()
