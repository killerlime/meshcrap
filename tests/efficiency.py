"""Cache behavior, configuration wizard and a real production HTTP server."""
import importlib.util, json, socket, subprocess, sys, tempfile, time
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import urllib.request
from flask import Flask, jsonify

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'source/dashboard')]
from health_cache import shared_health_check
from setup_wizard import configure
import meshcrap as cli

app=Flask(__name__);calls=[]
@shared_health_check(seconds=5)
def health():
    calls.append(1)
    return jsonify(generated=len(calls))
def read():
    with app.test_request_context():return health().get_json()
with patch('health_cache.monotonic',return_value=10):
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(x=={'generated':1} for x in pool.map(lambda _:read(),range(16)))
with patch('health_cache.monotonic',return_value=16):assert read()=={'generated':2}
assert len(calls)==2

with tempfile.TemporaryDirectory() as temporary:
    base=Path(temporary);config=base/'config.json'
    defaults=json.loads((ROOT/'config.example.json').read_text())
    answers=iter(['','0','8080','n','n','n','y'])
    assert configure(config,defaults,cli.load_config,lambda _:next(answers))
    assert json.loads(config.read_text())['enable_potato'] is False
    original=config.read_bytes()
    assert not configure(config,defaults,cli.load_config,lambda _:'n')
    assert config.read_bytes()==original
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    settings=json.loads(config.read_text());settings.update(web_port=port,https_host='mesh.example',trusted_hosts=['localhost','mesh.example','127.0.0.1'])
    config.write_text(json.dumps(settings))
    process=subprocess.Popen([sys.executable,str(ROOT/'meshcrap.py'),'--config',str(config),'serve'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    def get(path,host='localhost',forwarded=False):
        headers={'Host':host}
        if forwarded:headers['X-Forwarded-Proto']='https'
        return urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}'+path,headers=headers),timeout=5)
    try:
        for _ in range(100):
            if process.poll() is not None:raise AssertionError(process.stderr.read().decode())
            try:
                with get('/api/node-control/session') as response:break
            except OSError:time.sleep(.1)
        else:raise AssertionError('Server did not start')
        with get('/api/node-control/session',forwarded=True) as response:assert json.load(response)['secure'] is False
        with get('/api/node-control/session','mesh.example',True) as response:assert json.load(response)['secure'] is True
        for path in ('/','/install','/service-worker.js','/static/vendor/fonts.css','/static/vendor/chart-4.5.1.js','/static/app-assets/icon-180.png','/static/app-assets/manifest.webmanifest'):
            with get(path) as response:assert response.status==200 and response.read()
        with get('/api/self-test') as response:first=json.load(response)
        with get('/api/self-test') as response:assert json.load(response)['generated']==first['generated']
    finally:
        process.terminate();process.wait(timeout=10);process.stderr.close()
print('PASS: shared cache, wizard validation/cancellation, real Waitress serving, proxy trust and local assets')
