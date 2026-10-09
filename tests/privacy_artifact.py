"""Check ZIP/DEX release inspection without publishing real deployment data."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('release_audit',Path(__file__).resolve().parents[1]/'tools/audit_artifact.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class ArtifactPrivacyTests(unittest.TestCase):
    def archive(self,entries):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'release.zip'
            with zipfile.ZipFile(path,'w') as output:
                for name,value in entries.items():output.writestr(name,value)
            return audit.audit(path)

    def test_example_rejection_fixture_and_policy_source_are_safe(self):
        text='https://'+'user:password@collector.example'
        result=self.archive({'meshcrap-preview/ios/Tests/Example.swift':text,
                             'meshcrap-preview/tests/privacy_check.py':(audit.ROOT/'tests/privacy_check.py').read_bytes()})
        self.assertFalse(result['findings'])
        self.assertEqual(len(result['entries']),2)

    def test_realistic_secret_is_not_exempt_in_fixture(self):
        secret='abcd0123EFGH4567' * 2
        result=self.archive({'tests/example.py':'api_key="'+secret+'"'})
        self.assertIn(('tests/example.py','credential literal'),result['findings'])
        self.assertNotIn(secret,str(result))

    def test_private_capture_and_unsafe_paths_are_flagged(self):
        result=self.archive({'../state.txt':'', 'capture.iq':'', '.ssh/config':''})
        self.assertTrue(any(label=='unsafe archive path' for _,label in result['findings']))
        self.assertTrue(any(name=='capture.iq' for name,_ in result['findings']))
        self.assertTrue(any(name=='.ssh/config' for name,_ in result['findings']))

    def test_binary_strings_are_checked(self):
        value=('api_key="'+('abcd0123EFGH4567' * 2)+'"').encode('utf-16-le')
        result=self.archive({'resources.arsc':value})
        self.assertIn(('resources.arsc','credential literal'),result['findings'])

    def test_approved_vendor_binary_requires_exact_hash(self):
        name='source/dashboard/static/vendor/font-0.ttf'
        raw=(audit.ROOT/name).read_bytes()
        self.assertFalse(self.archive({name:raw})['findings'])
        changed=self.archive({name:raw+b'changed'})
        self.assertIn((name,'vendor checksum mismatch'),changed['findings'])

    def test_valid_dex_strings_and_malformed_bounds(self):
        raw=bytearray(72);raw[:8]=b'dex\n035\0'
        struct.pack_into('<II',raw,56,1,64);struct.pack_into('<I',raw,64,68)
        raw[68:72]=b'\x02ok\0'
        self.assertEqual(audit.dex_strings(raw),'ok')
        struct.pack_into('<I',raw,64,5000)
        with self.assertRaises(ValueError):audit.dex_strings(raw)
        with self.assertRaises(ValueError):audit.dex_strings(b'dex\n035\0')


if __name__=='__main__':unittest.main()
