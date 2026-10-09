"""Optional sniffer is display-only, private by default and cannot fetch URLs."""
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
from setup_wizard import configure, configure_sniffer
from source.dashboard.rf_sniffer import register_rf_sniffer, validate_embed_url
from flask import Flask


class OptionalSnifferTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'config.json'
        self.defaults = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))

    def save(self, changes=None):
        config = self.defaults | (changes or {})
        self.path.write_text(json.dumps(config), encoding='utf-8')
        return config

    def test_off_by_default_and_backward_compatible(self):
        config = self.save()
        del config['rf_sniffer_enabled']
        del config['rf_sniffer_url']
        self.path.write_text(json.dumps(config), encoding='utf-8')
        settings, _ = meshcrap.load_config(self.path)
        self.assertFalse(settings['rf_sniffer_enabled'])
        self.assertEqual(settings['rf_sniffer_url'], '')

    def test_paths_reject_urls_secrets_escapes_and_dashboard_routes(self):
        for path in ('http://example.com/sniffer/', '//example.com/sniffer/',
                     '/sniffer/?key=secret', '/sniffer/#secret', '/sniffer/../api/',
                     '/sniffer/%2e%2e/', '/sniffer/\\evil/', '/api/', '/static/',
                     '/', '/sniffer', '/sniffer/\n', '/sniffer/%2f/', None,
                     'https://user:password@example.com/', 'https://example.com/?key=secret',
                     'https://example.com/#key', 'https://example.com/../sniffer/',
                     'https://example.com/%2e%2e/', 'https://example.com/\n',
                     "https://example.com/'", 'https://example.com:99999/',
                     'https://example.com/?', 'https://example.com/#',
                     'https://@example.com/', 'https://example.com:/'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_embed_url(path)
        for path in ('', '/sniffer/', '/rf-sniffer/', '/sniffer-lab/',
                     'https://sniffer.example.com/', 'https://sniffer.example.com:8443/'):
            self.assertEqual(validate_embed_url(path), path)

    def test_config_boolean_and_path_validation(self):
        for changes in ({'rf_sniffer_enabled': 'true'}, {'rf_sniffer_enabled': 1},
                        {'rf_sniffer_enabled': True, 'rf_sniffer_url': ''}, {'rf_sniffer_url': '/api/'}):
            self.save(changes)
            with self.assertRaises(ValueError):
                meshcrap.load_config(self.path)

    def test_default_new_install_is_off_without_connecting(self):
        answers = iter(['', '', '', 'n', 'n', 'n', '', 'n', 'y'])
        with patch('urllib.request.urlopen', side_effect=AssertionError('Must not connect')):
            self.assertTrue(configure(self.path, self.defaults, meshcrap.load_config,
                                      lambda _: next(answers)))
        self.assertFalse(meshcrap.load_config(self.path)[0]['rf_sniffer_enabled'])

    def test_quick_wizard_preserves_configuration_and_creates_backup(self):
        original_config = self.save({'app_title': 'Private field dashboard',
                                    'receiver_id': '!12345678', 'node_prefix': 'FIELD',
                                    'channels': {'0': 'Primary local'}, 'enable_radio_controls': True})
        original = self.path.read_bytes()
        answers = iter(['y', 'http://example.com/', '/sniffer-lab/', 'y'])
        self.assertTrue(configure_sniffer(self.path, self.defaults, meshcrap.load_config,
                                        lambda _: next(answers)))
        result = meshcrap.load_config(self.path)[0]
        self.assertEqual(result, original_config | {'rf_sniffer_enabled': True,
                                                   'rf_sniffer_url': '/sniffer-lab/'})
        backups = list(self.path.parent.glob('config.json.backup-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        if os.name == 'posix':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_cancel_wizard_never_changes_files(self):
        self.save()
        original = self.path.read_bytes()
        answers = iter(['y', '/sniffer/', 'n'])
        self.assertFalse(configure_sniffer(self.path, self.defaults, meshcrap.load_config,
                                         lambda _: next(answers)))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('config.json.backup-*')), [])

    def test_disabling_keeps_data_and_previous_path(self):
        config = self.save({'rf_sniffer_enabled': True, 'rf_sniffer_url': '/sniffer-lab/'})
        answers = iter(['n', 'y'])
        self.assertTrue(configure_sniffer(self.path, self.defaults, meshcrap.load_config,
                                        lambda _: next(answers)))
        self.assertEqual(meshcrap.load_config(self.path)[0], config | {'rf_sniffer_enabled': False})

    def test_quick_wizard_preserves_concurrent_edits(self):
        config = self.save()
        answers = iter(['y', '/sniffer/', 'y'])
        def answer(prompt):
            if prompt.startswith('Save'):
                self.path.write_text(json.dumps(config | {'app_title': 'Another administrator edit'}), encoding='utf-8')
            return next(answers)
        with self.assertRaisesRegex(ValueError, 'changed during setup'):
            configure_sniffer(self.path, self.defaults, meshcrap.load_config, answer)
        self.assertEqual(meshcrap.load_config(self.path)[0]['app_title'], 'Another administrator edit')
        self.assertEqual(list(self.path.parent.glob('config.json.backup-*')), [])

    def test_integration_endpoint_has_no_backend_actions_or_secret(self):
        for enabled in (False, True):
            app = Flask(__name__)
            register_rf_sniffer(app, enabled, '/sniffer-lab/')
            with patch('urllib.request.urlopen', side_effect=AssertionError('Must not fetch')):
                response = app.test_client().get('/api/rf-sniffer/integration?url=https://example.com')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['url'], '/sniffer-lab/' if enabled else None)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(app.test_client().post('/api/rf-sniffer/integration').status_code, 405)

    def test_frame_policy_allows_only_configured_origin_after_existing_headers(self):
        app = Flask(__name__)
        @app.after_request
        def existing_policy(response):
            response.headers['Content-Security-Policy'] = "frame-ancestors 'self'; object-src 'none'"
            return response
        register_rf_sniffer(app, True, 'https://sniffer.example.com:8443/')
        response = app.test_client().get('/api/rf-sniffer/integration')
        self.assertEqual(response.headers['Content-Security-Policy'],
                         "frame-ancestors 'self'; object-src 'none'; frame-src 'self' https://sniffer.example.com:8443")


if __name__ == '__main__':
    unittest.main()
