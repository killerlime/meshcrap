import io,json,sys,tempfile,unittest,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source/dashboard'))
from public_weather_cache import fetch,validate_url,LIMIT
URL='https://api.weather.gov/alerts/active?area=MN'


class Response(io.BytesIO):
    headers={'ETag':'fixture'}


class Client:
    def __init__(self,body=b'{"features":[]}'):self.body=body;self.calls=0
    def open(self,request,timeout):
        self.url=request.full_url
        self.calls+=1
        if isinstance(self.body,Exception):raise self.body
        return Response(self.body)


class CacheTests(unittest.TestCase):
    def test_cache_and_failure_preserve_last_good_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cache.sqlite';client=Client()
            first=fetch(URL,path,now=1000,opener=client)
            self.assertEqual(first['data'],{'features':[]})
            self.assertTrue(fetch(URL,path,now=1100,opener=client)['cached'])
            self.assertEqual(client.calls,1)
            client.body=OSError('do not log this URL')
            failed=fetch(URL,path,now=2000,opener=client)
            self.assertTrue(failed['stale']);self.assertEqual(failed['data'],first['data'])
            fetch(URL,path,now=2100,opener=client)
            self.assertEqual(client.calls,2)

    def test_oversize_and_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cache.sqlite';client=Client()
            fetch(URL,path,now=1000,opener=client)
            client.body=urllib.error.HTTPError(URL,304,'',{},None)
            self.assertFalse(fetch(URL,path,now=2000,opener=client)['stale'])
            client.body=b' '*(LIMIT+1)
            self.assertEqual(fetch(URL,path,now=3000,opener=client)['error'],'ValueError')

    def test_endpoints_and_intervals(self):
        for url in ('http://api.weather.gov/alerts','https://api.weather.gov.evil.example/alerts',
                    'https://user@api.weather.gov/alerts','https://localhost/alerts'):
            with self.assertRaises(ValueError):validate_url(url)
        with self.assertRaises(ValueError):fetch(URL,'unused',ttl=1)

    def test_canonical_alerts_and_retry_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=Client();path=Path(tmp)/'cache.sqlite'
            fetch(URL,path,now=1000,opener=client)
            self.assertEqual(client.url,'https://api.weather.gov/alerts?active=true&area=MN')
            client.body=urllib.error.HTTPError(URL,429,'',{'Retry-After':'10000'},None)
            result=fetch(URL,path,now=2000,opener=client)
            self.assertEqual(result['next_attempt'],12000)
            self.assertTrue(result['stale'])
            fetch(URL,path,now=11000,opener=client)
            self.assertEqual(client.calls,2)


if __name__=='__main__':unittest.main()
