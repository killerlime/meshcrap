"""Container adapter. All operator configuration and mutable state stay in /data."""
import ipaddress
import json
import os
from pathlib import Path
import socket
import struct
import sys
import urllib.request

from meshcrap import ROOT, load_config, initialize
from setup_wizard import configure

CONFIG = Path('/data/config.json')


def bridge_gateway(route_text):
    for line in route_text.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 4 and columns[1] == '00000000' and int(columns[3], 16) & 2:
            address = socket.inet_ntoa(struct.pack('<I', int(columns[2], 16)))
            parsed = ipaddress.ip_address(address)
            if parsed.is_private and not (parsed.is_loopback or parsed.is_unspecified or parsed.is_link_local):
                return address + '/32'
    raise ValueError('No private Docker bridge gateway found. Use a standard Docker bridge network.')


def container_config(path):
    config, data = load_config(path)
    if not data.is_relative_to(Path('/data')):
        raise ValueError('Container data_dir must be inside /data for persistence')
    if config['bind_host'] != '0.0.0.0' or config['web_port'] != 8080:
        raise ValueError('Container requires bind_host 0.0.0.0 and web_port 8080; change the host port in Compose instead')
    return config, data


def main():
    os.umask(0o077)
    command = sys.argv[1] if len(sys.argv) == 2 else ''
    if command == 'setup':
        defaults = json.loads((ROOT/'config.example.json').read_text())
        defaults.update(data_dir='/data/state', bind_host='0.0.0.0', web_port=8080)
        gateway = bridge_gateway(Path('/proc/net/route').read_text())
        defaults['allowed_networks'].append(gateway)
        print('Docker setup: host-only access through the bridge gateway; Compose binds to localhost.')
        print('Keep port 8080 and the /data/state folder. Network access is optional; HTTPS is separate.')
        if configure(CONFIG, defaults, container_config):
            config, data = container_config(CONFIG)
            initialize(config, data)
            print('Ready: docker compose up -d dashboard; open http://localhost:8080')
        return
    if command == 'health':
        with urllib.request.urlopen('http://127.0.0.1:8080/api/summary', timeout=3) as response:
            if response.status != 200:
                raise ValueError('Dashboard health request failed')
        return
    if command not in ('serve', 'collect', 'check', 'init', 'feed'):
        raise ValueError('Use setup, serve, collect, check, init, or feed')
    if not CONFIG.exists():
        raise ValueError('Run docker compose run --rm dashboard setup first')
    container_config(CONFIG)
    os.execv(sys.executable, [sys.executable, str(ROOT/'meshcrap.py'), '--config', str(CONFIG), command])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        print('Container setup: '+str(error), file=sys.stderr)
        sys.exit(2)
