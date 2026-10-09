"""Exercise the release gate using synthetic values assembled only in memory."""
import hashlib
import unittest
from unittest.mock import patch
import privacy_check as policy


class PrivacyPolicyTests(unittest.TestCase):
    def issues(self, text, name='source/example.py'):
        return policy.scan_source(name, text.encode('utf-8'))

    def test_private_networks_and_paths(self):
        addresses=['10.'+'12.20.30', '192.'+'168.50.20', '172.'+'21.40.8',
                   '100.'+'80.20.30', 'host.'+'tailabc.ts.net']
        for value in addresses:
            with self.subTest(value=value): self.assertTrue(self.issues(value))
        self.assertTrue(self.issues('/home/'+'radio-user/file'))
        self.assertTrue(self.issues('C:'+chr(92)+'Users'+chr(92)+'radio-user'))
        self.assertFalse(self.issues('127.0.0.1 ::1 /home/meshcrap/data'))

    def test_literal_credentials_and_url_credentials(self):
        value='abcDEF0123456789' * 2
        for name in ['api_key', 'api-token', 'pairing_key', 'psk', 'password']:
            with self.subTest(name=name): self.assertIn('credential literal', self.issues(f'"{name}": "{value}"'))
        self.assertIn('URL credentials', self.issues('https://'+'operator:'+value+'@collector.example'))
        self.assertIn('credential in URL', self.issues('https://collector.example/?token='+value))
        self.assertTrue(self.issues('-----BEGIN '+'ENCRYPTED PRIVATE KEY-----'))
        self.assertTrue(self.issues('github_'+'pat_'+value*2))

    def test_public_channel_defaults_are_not_private_keys(self):
        self.assertFalse(self.issues('psk = "AQ=="\nname = "MediumFast"'))
        self.assertFalse(self.issues('api_key = os.environ.get("API_KEY")'))

    def test_fixture_exception_is_narrow(self):
        text='api_key = "'+('x'*40)+'"'
        self.assertFalse(self.issues(text,'tests/test_example.py'))
        self.assertTrue(self.issues(text))
        arbitrary='api_key = "'+('abcd1234'*5)+'"'
        self.assertTrue(self.issues(arbitrary,'tests/test_example.py'))
        login='https://'+'user:password@collector.example'
        self.assertFalse(self.issues(login,'ios/Tests/Example.swift'))
        self.assertTrue(self.issues(login))
        self.assertFalse(self.issues('https://'+'user:password@example.com','tests/rejection.py'))
        hidden='https://'+'user:'+('abcd1234'*5)+'@collector.example'
        self.assertTrue(self.issues(hidden,'tests/rejection.py'))

    def test_private_runtime_files_and_capture_artifacts(self):
        for name in ['config.json','.env','session-secret','sniffer-settings.json',
                     '.ssh/trust.txt','backups/config.txt','data/info.txt',
                     'capture.iq','capture.cf32','capture.pcapng','state.db-wal',
                     'certificate.p12','radio.ppk','image.img','image.vhdx']:
            with self.subTest(name=name): self.assertTrue(self.issues('',name))
        self.assertFalse(self.issues('','config.example.json'))
        self.assertFalse(self.issues('','.env.example'))

    def test_fingerprints_reject_identifiers_without_returning_values(self):
        label='fixture-owner'
        with patch.object(policy,'denied',{hashlib.sha256(label.encode()).hexdigest()}):
            issues=self.issues(label)
            self.assertEqual(issues,['personal deployment identifier'])
            self.assertNotIn(label,str(issues))

    def test_binary_requires_manifest_review(self):
        self.assertIn('unreviewed binary file',policy.scan_source('asset.bin',b'\xff\xfe'))


if __name__=='__main__': unittest.main()
