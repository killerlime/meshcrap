"""Native-image test: first setup and HTTP serving as the unprivileged account."""
import json
import os
import pwd
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
account = pwd.getpwnam('meshcrap')
python = str(root / '.venv/bin/python')
assert os.geteuid() == 0, 'Run in the disposable image build chroot'
with tempfile.TemporaryDirectory(prefix='meshcrap-pi-test-') as temporary:
    base = Path(temporary)
    os.chown(base, account.pw_uid, account.pw_gid)
    config = base / 'config.json'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    command = ['runuser', '-u', 'meshcrap', '--', python, str(root/'meshcrap.py'), '--config', str(config)]
    subprocess.run(command+['setup'], input=f'\n\n{port}\nn\nn\nn\nn\n\n', text=True, check=True)
    settings = json.loads(config.read_text())
    assert settings['radio_host'] == '' and not settings['enable_potato']
    assert config.stat().st_mode & 0o777 == 0o600
    assert config.stat().st_uid == account.pw_uid
    before = config.read_bytes()
    subprocess.run(command+['setup'], input='n\n', text=True, check=True)
    assert config.read_bytes() == before
    subprocess.run(command+['check'], check=True)
    refused = subprocess.run(command+['collect'], capture_output=True)
    assert refused.returncode != 0  # No configured radio; never connect.
    process = subprocess.Popen(command+['serve'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError(process.stderr.read().decode())
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/summary', timeout=2) as response:
                    assert response.status == 200 and isinstance(json.load(response), dict)
                break
            except OSError:
                time.sleep(.1)
        else:
            raise AssertionError('Non-root dashboard failed to start')
        with sqlite3.connect(base/'data/mesh.db') as db:
            assert db.execute('select count(*) from nodes').fetchone()[0] == 0
            assert db.execute('select count(*) from packets').fetchone()[0] == 0
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)
        process.stderr.close()
subprocess.run(['runuser', '-u', 'meshcrap', '--', 'test', '!', '-w', str(root)], check=True)
print('PASS: non-root Pi setup, cancellation, private permissions, empty database and HTTP serving')
