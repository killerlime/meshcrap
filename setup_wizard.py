"""Interactive local setup. Never connects to a radio or external service."""
import json
import os
import re
import ipaddress
import tempfile
from pathlib import Path
from datetime import datetime, timezone


def configure(path, defaults, validate, ask=input):
    path = Path(path).resolve()
    print('Meshcrap setup — press Enter to accept a default.')
    print('Start with an empty private dashboard; add your radio now or later.')
    if path.exists():
        if ask('Configuration exists. Replace it and save a backup? [y/N] ').strip().lower() != 'y':
            print('Kept existing configuration. You can edit its JSON directly.')
            return False
    config = dict(defaults)

    def field(label, default, valid=lambda v: bool(v), convert=str):
        while True:
            value = ask(f'{label} [{default}]: ').strip() or str(default)
            try:
                value = convert(value)
                if valid(value): return value
            except (ValueError, TypeError):
                pass
            print('Please enter a valid value.')

    config['data_dir'] = field('Data folder', './data')
    config['web_port'] = field('Dashboard port', 8080, lambda v: 1 <= v <= 65535, int)
    if ask('Configure a TCP radio now? [y/N] ').strip().lower() == 'y':
        config['radio_host'] = field('Radio hostname or IP', '', lambda v: bool(re.fullmatch(r'[A-Za-z0-9_.:\-]+', v)))
        config['radio_port'] = field('Radio port', 4403, lambda v: 1 <= v <= 65535, int)
        config['receiver_id'] = field('Receiver ID (! plus 8 hex digits)', '', lambda v: bool(re.fullmatch(r'![0-9a-fA-F]{8}', v)) and int(v[1:],16) not in (0,0xffffffff)).lower()
    if ask('Customize display labels? [y/N] ').strip().lower() == 'y':
        config['node_prefix'] = field('Your node-name prefix', 'MY', lambda v: bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,7}',v)))
        config['channels'] = {'0':field('Channel 0 label', 'Primary'), '1':field('Channel 1 label', 'Secondary')}
    if ask('Allow dashboard access from your private network? [y/N] ').strip().lower() == 'y':
        def valid_host(value):
            return bool(re.fullmatch(r'[A-Za-z0-9_.:\-]+',value)) and value not in ('0.0.0.0','::')
        def valid_network(value):
            try:
                net=ipaddress.ip_network(value)
                return net.prefixlen>0 and net.is_private
            except ValueError:return False
        host=field('This server hostname or IP (as used in your browser)', '', valid_host)
        network=field('Trusted private client network in CIDR notation', '', valid_network)
        config['bind_host']='0.0.0.0'
        config['trusted_hosts']=list(dict.fromkeys(config['trusted_hosts']+[host]))
        config['allowed_networks']=list(dict.fromkeys(config['allowed_networks']+[network]))
        print('Viewing is allowed from that network; write controls remain locked. Use private HTTPS for remembered devices and the iPhone app.')
    print('Radio controls and external forwarding: OFF. Only explicitly configured networks can access the dashboard.')
    print('Map center, regions, private HTTPS and remote access can be set in JSON later.')
    if ask('Save this configuration? [Y/n] ').strip().lower() == 'n':
        print('Canceled; no files changed.')
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.meshcrap-setup-', suffix='.json', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
            f.write('\n')
        validate(temporary)
        if path.exists():
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = path.with_name(path.name+'.backup-'+stamp)
            backup.write_bytes(path.read_bytes())
            backup.chmod(0o600)
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Saved {path}')
    return True
