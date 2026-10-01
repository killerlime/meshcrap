import sys,tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source/dashboard'))
from flask import Flask
from heywhatsthat import register_heywhatsthat, profile_query
PNG=b'\x89PNG\r\n\x1a\nfixture'
class Reply:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return PNG
    class headers:
        @staticmethod
        def get_content_type():return 'image/png'
class Tests(unittest.TestCase):
    def test_count_cache_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);app=Flask(__name__);register_heywhatsthat(app,root/'mesh.db');client=app.test_client()
            self.assertFalse(client.get('/api/heywhatsthat/usage').json['enabled'])
            (root/'heywhatsthat-config.json').write_text('{"enabled":true}')
            data=dict(lat1=40.2,lon1=-104.9,lat2=40,lon2=-107,height1=10,height2=10)
            headers={'X-Requested-With':'meshcrap-terrain'}
            self.assertEqual(client.post('/api/heywhatsthat/profile',json=data).status_code,403)
            self.assertEqual(client.post('/api/heywhatsthat/profile',json={**data,'lat1':91},headers=headers).status_code,400)
            with patch('heywhatsthat.urllib.request.build_opener') as opener:
                opener.return_value.open.return_value=Reply()
                self.assertEqual(client.post('/api/heywhatsthat/profile',json=data,headers=headers).status_code,200)
                self.assertEqual(client.post('/api/heywhatsthat/profile',json=data,headers=headers).headers['X-Terrain-Cache'],'hit')
                self.assertEqual(opener.return_value.open.call_count,1)
                self.assertEqual(client.post('/api/heywhatsthat/profile',json={**data,'height1':11},headers=headers).status_code,429)
            counts=client.get('/api/heywhatsthat/usage').json['windows']['7']
            self.assertEqual(counts,dict(attempts=1,successes=1,cache_hits=1))
    def test_bad_values(self):
        for value in [None,True,float('nan'),float('inf'),'40']:
            with self.assertRaises(ValueError):profile_query(dict(lat1=value))
if __name__=='__main__':unittest.main()
