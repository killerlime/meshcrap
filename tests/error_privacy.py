"""Unexpected parser/backend errors must never be reflected to clients."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, g

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source/dashboard'))
import heywhatsthat
import node_control_web
import node_utilities
import survey_phone

DETAIL = 'synthetic-private-parser-detail'


class ErrorPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = Flask(__name__)
        self.app.secret_key = 'synthetic-session'
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def assert_private_error(self, response, status=400):
        self.assertEqual(response.status_code, status)
        self.assertNotIn(DETAIL, response.get_data(as_text=True))
        self.assertTrue(response.json['error'])

    def test_node_parser_details_are_private(self):
        node_utilities.register_utilities(self.app, self.root / 'mesh.db')
        for route in ('purge-preview', 'purge-node'):
            with patch.object(node_utilities, 'node_number', side_effect=ValueError(DETAIL)):
                self.assert_private_error(self.client.post('/api/utilities/' + route, json={}))

    def test_node_validation_is_useful_and_rejects_nonobjects(self):
        node_utilities.register_utilities(self.app, self.root / 'mesh.db')
        for route in ('purge-preview', 'purge-node'):
            response = self.client.post('/api/utilities/' + route, json=[])
            self.assertEqual(response.json['error'], 'Expected a node request object')
            self.assertEqual(response.status_code, 400)
            response = self.client.post('/api/utilities/' + route, json={'node_id': 'invalid'})
            self.assertEqual(response.status_code, 400)
            self.assertIn('canonical node ID', response.json['error'])

    def test_survey_unexpected_errors_are_private(self):
        # Exercise the upload handler without creating a database or radio connection.
        phone = survey_phone.SurveyPhone.__new__(survey_phone.SurveyPhone)
        self.app.add_url_rule('/sync', view_func=phone.sync, methods=['POST'])
        @self.app.before_request
        def authorize_fixture():
            g.survey_phone_client = {'id': 1}
        for kind in (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            with patch.object(survey_phone, 'integer', side_effect=kind(DETAIL)):
                self.assert_private_error(self.client.post('/sync', json={'source': 1}))

    def test_survey_validation_keeps_safe_guidance(self):
        phone = survey_phone.SurveyPhone.__new__(survey_phone.SurveyPhone)
        self.app.add_url_rule('/sync', view_func=phone.sync, methods=['POST'])
        @self.app.before_request
        def authorize_fixture():
            g.survey_phone_client = {'id': 1}
        response = self.client.post('/sync', json={'source': 'invalid'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], 'Invalid integer field')

    def test_terrain_parser_details_are_private(self):
        (self.root / 'heywhatsthat-config.json').write_text('{"enabled":true}', encoding='utf-8')
        heywhatsthat.register_heywhatsthat(self.app, self.root / 'mesh.db')
        with patch.object(heywhatsthat, 'profile_query', side_effect=ValueError(DETAIL)):
            response = self.client.post('/api/heywhatsthat/profile', json={},
                                        headers={'X-Requested-With': 'meshcrap-terrain'})
            self.assert_private_error(response)
            self.assertIn('two different locations', response.json['error'])

    def test_secondary_backend_details_are_private_and_missing_backend_is_handled(self):
        class Security:
            def __init__(self, *args): pass
            def may_act(self, body): return True
        with patch.dict(sys.modules, dashboard_security=types.SimpleNamespace(Security=Security, COOKIE='fixture')):
            node_control_web.register_node_control(self.app, self.root)
        headers = {'Origin': 'http://localhost'}
        backend = types.SimpleNamespace(dispatch=lambda body: None)
        with patch.dict(sys.modules, secondary_control_connection=backend), \
                patch.object(backend, 'dispatch', side_effect=ValueError(DETAIL)):
            response = self.client.post('/api/secondary-control/action', json={'action': 'state'}, headers=headers)
            self.assert_private_error(response)
        with patch.dict(sys.modules, secondary_control_connection=None):
            response = self.client.post('/api/secondary-control/action', json={'action': 'state'}, headers=headers)
            self.assert_private_error(response, 503)


if __name__ == '__main__':
    unittest.main()
