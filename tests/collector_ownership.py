"""Synthetic primary receiver ownership/provenance checks; no network or radio access."""
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('collector_test_cli', ROOT / 'meshcrap.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
INSTALLATION = tempfile.TemporaryDirectory(prefix='collector-ownership-')
config = json.loads((ROOT / 'config.example.json').read_text())
config.update(data_dir=str(Path(INSTALLATION.name) / 'data'), receiver_id='!12345678', radio_host='192.0.2.10')
settings = Path(INSTALLATION.name) / 'config.json'
settings.write_text(json.dumps(config))
config, data = cli.load_config(settings)
runtime = cli.initialize(config, data)
sys.path[:0] = [str(runtime), str(runtime / 'dashboard')]
import collector


def packet(identity, received=None):
    value = dict(id=identity, fromId='!23456789', to=0xffffffff, channel=0, rxSnr=3,
                 decoded=dict(portnum='NODEINFO_APP', user=dict(id='!23456789', longName='Synthetic node', shortName='TEST')))
    value['from'] = 0x23456789
    if received is not None:
        value['rxTime'] = received
    return value


class Radio:
    def __init__(self, number=0x12345678):
        self.localNode = NS(nodeNum=number)
        self.isConnected = threading.Event()
        self.isConnected.set()
        self.failure = None
        self.nodes = {}
        self.closed = False

    def connect(self):
        # Simulate SDK replay during the configuration handshake.
        collector.on_receive(packet(990, int(time.time())), self)
        assert collector.current_interface() is None

    def close(self):
        self.closed = True
        self.isConnected.clear()


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        collector.db = collector.open_database()
        with collector.db:
            collector.db.execute('DELETE FROM packets')
            collector.db.execute('DELETE FROM nodes')
        self.radio = Radio()
        collector.interface = self.radio
        collector.receiver_ready = True
        collector.session_started = time.time()
        collector.receiver_profile = {'lora': {'modem_preset': 'MEDIUM_FAST'}, 'channels': []}

    def tearDown(self):
        collector.interface = None
        collector.receiver_ready = False
        collector.db.close()
        collector.db = None

    def count(self):
        return collector.db.execute('SELECT COUNT(*) FROM packets').fetchone()[0]

    def test_only_verified_active_interface_records_packets(self):
        previous = collector.last_receive_monotonic
        with patch.object(collector.mf_feed, 'capture') as capture:
            collector.on_receive(packet(1, int(time.time())), Radio())
            collector.on_receive(packet(2, int(time.time())), None)
            collector.receiver_ready = False
            collector.on_receive(packet(3, int(time.time())), self.radio)
            collector.receiver_ready = True
            self.radio.localNode.nodeNum = 0x34567890
            collector.on_receive(packet(4, int(time.time())), self.radio)
            self.assertEqual(self.count(), 0)
            self.assertEqual(collector.last_receive_monotonic, previous)
            capture.assert_not_called()
            self.radio.localNode.nodeNum = 0x12345678
            collector.on_receive(packet(5, int(time.time())), self.radio)
            self.assertEqual(self.count(), 1)
            capture.assert_called_once()

    def test_controls_exclude_handshake_wrong_identity_and_disconnected_transport(self):
        self.assertIs(collector.current_interface(), self.radio)
        collector.receiver_ready = False
        self.assertIsNone(collector.current_interface())
        collector.receiver_ready = True
        self.radio.localNode.nodeNum = 0x34567890
        self.assertIsNone(collector.current_interface())
        self.radio.localNode.nodeNum = 0x12345678
        self.radio.failure = ConnectionError('Synthetic connection failure')
        self.assertIsNone(collector.current_interface())
        self.radio.failure = None
        self.radio.isConnected.clear()
        self.assertIsNone(collector.current_interface())

    def test_provenance_preserves_history_without_claiming_bootstrap_is_live(self):
        now = time.time()
        collector.session_started = now
        samples = [packet(1, int(now)), packet(2, int(now - 3600)), packet(3, int(now + 120)), packet(4)]
        with patch.object(collector.mf_feed, 'capture'):
            for sample in samples:
                collector.on_receive(sample, self.radio)
        rows = collector.db.execute('SELECT observation_type,raw_json FROM packets ORDER BY row_id').fetchall()
        self.assertEqual([row[0] for row in rows], ['LIVE', 'BUFFERED', 'CLOCK_SKEW', 'UNDATED'])
        for kind, raw in rows:
            value = json.loads(raw)
            self.assertEqual(value['_collectorObservationType'], kind)
            self.assertEqual(value['_collectorReceiverId'], '!12345678')

    @unittest.skipUnless(sys.platform == 'linux', 'The collector is supported on Linux')
    def test_primary_lock_rejects_duplicates_and_releases_on_failure(self):
        with collector.collector_lock():
            with self.assertRaisesRegex(ValueError, 'already running'):
                with collector.collector_lock():
                    self.fail('Duplicate primary collector acquired the lock')
        with self.assertRaisesRegex(RuntimeError, 'Synthetic'):
            with collector.collector_lock():
                raise RuntimeError('Synthetic startup failure')
        with collector.collector_lock():
            self.assertTrue((data / '.collector.lock').is_file())
        self.assertEqual((data / '.collector.lock').stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(sys.platform == 'linux', 'Private status files are used by the Linux collector')
    def test_connect_gates_replay_and_publishes_verified_profile_without_controls(self):
        collector.receiver_ready = False
        with patch.object(collector, 'RecoveringTCPInterface', return_value=self.radio) as construct, \
                patch.object(collector.time, 'sleep'), patch.object(collector, 'radio_profile', return_value=collector.receiver_profile), \
                patch.object(collector.mf_feed, 'connected', return_value=False), patch.object(collector.mf_feed, 'pause'):
            collector.connect()
            self.assertFalse(construct.call_args.kwargs['connectNow'])
            self.assertEqual(self.count(), 0)
            self.assertIs(collector.current_interface(), self.radio)
            status_file = data / 'receiver-status.json'
            status = json.loads(status_file.read_text())
            self.assertEqual(status['receiver_id'], '!12345678')
            self.assertTrue(status['connected'])
            self.assertIsNotNone(status['profile'])
            self.assertGreater(status['session_started_epoch'], 0)
            self.assertEqual(status_file.stat().st_mode & 0o777, 0o600)
            collector.close_interface()
            self.assertTrue(self.radio.closed)
            self.assertIsNone(collector.current_interface())
            self.assertFalse(json.loads(status_file.read_text())['connected'])

    @unittest.skipUnless(sys.platform == 'linux', 'The collector is supported on Linux')
    def test_wrong_radio_handshake_never_populates_history_or_controls(self):
        wrong = Radio(0x34567890)
        with patch.object(collector, 'RecoveringTCPInterface', return_value=wrong), patch.object(collector.mf_feed, 'pause'):
            with self.assertRaises(collector.ReceiverIdentityMismatch):
                collector.connect()
            self.assertEqual(self.count(), 0)
            self.assertIsNone(collector.current_interface())
            collector.close_interface()
            self.assertTrue(wrong.closed)

    @unittest.skipUnless(sys.platform == 'linux', 'The collector is supported on Linux')
    def test_wrong_verified_identity_exits_without_reclaiming_radio(self):
        wrong = Radio(0x34567890)
        collector.running = True
        with patch.object(collector, 'RecoveringTCPInterface', return_value=wrong) as construct, \
                patch.object(collector.mf_feed, 'pause'), patch.object(collector, 'recovery_sleep') as sleeping:
            with self.assertRaises(SystemExit) as result:
                collector.main()
            self.assertEqual(result.exception.code, 78)
            construct.assert_called_once()
            sleeping.assert_not_called()
            self.assertTrue(wrong.closed)
            self.assertIsNone(collector.db)
            self.assertIsNone(collector.current_interface())
            with collector.collector_lock():
                pass
        collector.db = collector.open_database()

    @unittest.skipUnless(sys.platform == 'linux', 'Private status files are used by the Linux collector')
    def test_heartbeat_is_throttled_but_disconnect_is_immediate(self):
        with patch.object(collector.time, 'monotonic', return_value=1000):
            collector.publish_status()
        with patch.object(collector.time, 'monotonic', return_value=1009), patch.object(collector.os, 'open') as opening:
            collector.publish_status(heartbeat_only=True)
            opening.assert_not_called()
        with patch.object(collector.time, 'monotonic', return_value=1010):
            collector.publish_status(heartbeat_only=True)
            self.assertEqual(collector.last_status_write, 1010)
        with patch.object(collector.time, 'monotonic', return_value=1011), patch.object(collector.mf_feed, 'pause'):
            collector.close_interface()
            self.assertEqual(collector.last_status_write, 1011)
            self.assertFalse(json.loads((data / 'receiver-status.json').read_text())['connected'])

    def test_status_write_failure_still_closes_radio(self):
        with patch.object(collector, 'publish_status', side_effect=OSError('Synthetic disk unavailable')), \
                patch.object(collector.mf_feed, 'pause'):
            with self.assertRaises(OSError):
                collector.close_interface()
        self.assertTrue(self.radio.closed)
        self.assertIsNone(collector.current_interface())


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        INSTALLATION.cleanup()
