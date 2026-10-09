"""Optional receiver setup is private, reversible and never opens a radio."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import meshcrap
from setup_wizard import configure_secondary


class SecondarySetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config.json'
        self.config = json.loads((ROOT / 'config.example.json').read_text())
        self.config.update(radio_host='primary.example', receiver_id='!12345678')
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.config), encoding='utf-8')

    def ask(self, answers):
        values = iter(answers)
        return lambda _: next(values)

    def test_default_is_off_and_rejects_collect(self):
        loaded, _ = meshcrap.load_config(self.path)
        self.assertFalse(loaded['secondary_enabled'])
        with patch.object(sys, 'argv', ['meshcrap.py', '--config', str(self.path), 'collect-secondary']), patch.object(meshcrap, 'initialize') as init:
            with self.assertRaisesRegex(ValueError, 'disabled'):
                meshcrap.main()
            init.assert_not_called()

    def test_setup_preserves_primary_and_backs_up(self):
        original = self.path.read_bytes()
        with patch('socket.create_connection', side_effect=AssertionError('No network during setup')):
            self.assertTrue(configure_secondary(self.path, self.config, meshcrap.load_config,
                            self.ask(['y', 'second.example', '', '!abcdef12', 'Field receiver', 'y'])))
        loaded, _ = meshcrap.load_config(self.path)
        self.assertEqual(loaded['radio_host'], 'primary.example')
        self.assertEqual(loaded['receiver_id'], '!12345678')
        self.assertTrue(loaded['secondary_enabled'])
        self.assertFalse(loaded['secondary_enable_controls'])
        self.assertFalse(loaded['enable_radio_controls'])
        backups = list(self.path.parent.glob('config.json.backup-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        if os.name != 'nt':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_cancel_preserves_bytes(self):
        original = self.path.read_bytes()
        self.assertFalse(configure_secondary(self.path, self.config, meshcrap.load_config,
                         self.ask(['y', 'second.example', '', '!abcdef12', 'Field', 'n'])))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(list(self.path.parent.glob('config.json.backup-*')))

    def test_duplicate_receiver_or_endpoint_rejected(self):
        self.config.update(secondary_enabled=True, secondary_radio_host='second.example', secondary_receiver_id='!12345678')
        self.save()
        with self.assertRaisesRegex(ValueError, 'different radios'):
            meshcrap.load_config(self.path)
        self.config.update(secondary_receiver_id='!abcdef12', secondary_radio_host='PRIMARY.EXAMPLE.')
        self.save()
        with self.assertRaisesRegex(ValueError, 'different endpoints'):
            meshcrap.load_config(self.path)

    def test_invalid_values_rejected(self):
        for name, value in [('secondary_radio_host', 'user@second.example'), ('secondary_receiver_id', 'not-an-id'),
                            ('secondary_radio_port', True), ('secondary_label', 'bad\nlabel'), ('secondary_enabled', 'yes')]:
            with self.subTest(name=name):
                config = self.config | {name: value}
                self.path.write_text(json.dumps(config), encoding='utf-8')
                with self.assertRaises(ValueError):
                    meshcrap.load_config(self.path)

    def test_concurrent_change_not_overwritten(self):
        original = self.path.read_bytes()
        def answer(prompt):
            if prompt.startswith('Save'):
                self.path.write_bytes(original + b'\n')
                return 'y'
            return 'n'
        with self.assertRaisesRegex(ValueError, 'changed during setup'):
            configure_secondary(self.path, self.config, meshcrap.load_config, answer)
        self.assertEqual(self.path.read_bytes(), original + b'\n')
        self.assertFalse(list(self.path.parent.glob('config.json.backup-*')))


if __name__ == '__main__':
    unittest.main()
