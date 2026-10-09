"""Interactive local setup. Never connects to a radio or external service."""
import json
import os
import re
import ipaddress
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from source.dashboard.rf_sniffer import validate_embed_url


def _save_config(path, config, validate, expected=None, check_unchanged=False):
    """Validate before replacing; private atomic file and restrictive backup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.meshcrap-setup-', suffix='.json', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
            f.write('\n')
        validate(temporary)
        if check_unchanged and (path.read_bytes() if path.exists() else None) != expected:
            raise ValueError('Configuration changed during setup. No settings were replaced; run the wizard again.')
        if path.exists():
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = path.with_name(path.name+'.backup-'+stamp)
            backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(backup_fd, 'wb') as f:
                f.write(path.read_bytes())
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _sniffer_options(config, ask):
    enabled = config.get('rf_sniffer_enabled', False)
    choice = ask('Show a separate RF sniffer dashboard? '+('[Y/n] ' if enabled else '[y/N] ')).strip().lower()
    config['rf_sniffer_enabled'] = choice != 'n' if enabled else choice == 'y'
    if config['rf_sniffer_enabled']:
        print('Its private web dashboard must already run behind HTTPS or your same-origin proxy. No software or receiver is started here.')
        print('Only connect a web page you operate and trust. Keep native ports private and secure the separate controls.')
        while True:
            url = ask('Private HTTPS sniffer URL or same-origin path ['+(config.get('rf_sniffer_url') or '/sniffer/')+']: ').strip() or config.get('rf_sniffer_url') or '/sniffer/'
            try:
                config['rf_sniffer_url'] = validate_embed_url(url)
                break
            except ValueError:
                print('Use a dedicated /sniffer/ path or an HTTPS URL. Do not enter credentials, query strings or fragments.')


def configure_sniffer(path, defaults, validate, ask=input):
    """Small standalone wizard; preserve existing collector and access settings."""
    path = Path(path).resolve()
    original = path.read_bytes() if path.exists() else None
    config = validate(path)[0] if path.exists() else dict(defaults)
    print('Optional RF sniffer — the receiver remains an independent private process.')
    _sniffer_options(config, ask)
    if ask('Save these display settings? [Y/n] ').strip().lower() == 'n':
        print('Canceled; no files changed.')
        return False
    _save_config(path, config, validate, expected=original, check_unchanged=True)
    print('Saved. Restart only your dashboard service, then open RF sniffer → Quick setup to check the web page.')
    return True


def _secondary_options(config, ask):
    enabled = config.get('secondary_enabled', False)
    choice = ask('Compare reception with a second dedicated radio? '+('[Y/n] ' if enabled else '[y/N] ')).strip().lower()
    config['secondary_enabled'] = choice != 'n' if enabled else choice == 'y'
    if not config['secondary_enabled']:
        config['secondary_enable_controls'] = False
        return
    print('Use a different radio and one collector connection. Stop competing TCP clients before starting it.')
    print('This setup saves settings only; it does not connect, probe nodes or change radio settings.')

    def field(label, default, valid, convert=str):
        while True:
            value = ask(f'{label} [{default}]: ').strip() or str(default)
            try:
                value = convert(value)
                if valid(value):
                    return value
            except (ValueError, TypeError):
                pass
            print('Please enter a valid value.')

    config['secondary_radio_host'] = field('Second radio or TCP bridge hostname/IP', config.get('secondary_radio_host', ''),
                                          lambda v: bool(re.fullmatch(r'[A-Za-z0-9_.:\-]+', v)))
    config['secondary_radio_port'] = field('Second radio port', config.get('secondary_radio_port', 4403), lambda v: 1 <= v <= 65535, int)
    config['secondary_receiver_id'] = field('Second receiver ID (! plus 8 hex digits)', config.get('secondary_receiver_id', ''),
                                            lambda v: bool(re.fullmatch(r'![0-9a-fA-F]{8}', v)) and int(v[1:], 16) not in (0, 0xffffffff)).lower()
    config['secondary_label'] = field('Second receiver display name', config.get('secondary_label', 'Secondary'),
                                      lambda v: bool(v.strip()) and len(v) <= 80 and not any(ord(c) < 32 for c in v))
    # A receiver setup never silently grants permission to transmit or administer.
    config['secondary_enable_controls'] = False


def configure_secondary(path, defaults, validate, ask=input):
    """Opt-in second receiver; preserve first receiver and private access settings."""
    path = Path(path).resolve()
    original = path.read_bytes() if path.exists() else None
    config = validate(path)[0] if path.exists() else dict(defaults)
    print('Optional receiver comparison — separate history, one connection per radio.')
    _secondary_options(config, ask)
    if ask('Save these receiver settings? [Y/n] ').strip().lower() == 'n':
        print('Canceled; no files changed.')
        return False
    _save_config(path, config, validate, expected=original, check_unchanged=True)
    print('Saved. Restart the dashboard to show the comparison. Start collect-secondary explicitly when ready.')
    print('Secondary controls remain OFF. Read the receiver comparison guide before enabling them in JSON.')
    return True


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

    config['app_title'] = field('App title', defaults.get('app_title','Meshcrap RF Console'), lambda v: 1 <= len(v) <= 80 and not any(ord(c)<32 for c in v))
    config['data_dir'] = field('Data folder', defaults.get('data_dir', './data'))
    config['web_port'] = field('Dashboard port', 8080, lambda v: 1 <= v <= 65535, int)
    if ask('Configure a radio connection now? [y/N] ').strip().lower() == 'y':
        connection=field('Connection: direct radio or Raspberry Pi TCP bridge (direct/pi)', 'direct', lambda v: v in ('direct','pi'))
        if connection=='pi':
            print('Use your Pi running an existing TCP radio bridge. SSH credentials are not required or stored.')
            print('The wizard configures this app; it does not install a bridge or change the Pi.')
        config['radio_host'] = field('Raspberry Pi bridge hostname or IP' if connection=='pi' else 'Radio hostname or IP', '', lambda v: bool(re.fullmatch(r'[A-Za-z0-9_.:\-]+', v)))
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
    _sniffer_options(config, ask)
    _secondary_options(config, ask)
    print('Radio controls and external forwarding: OFF. Only explicitly configured networks can access the dashboard.')
    print('Map center, regions, private HTTPS and remote access can be set in JSON later.')
    if ask('Save this configuration? [Y/n] ').strip().lower() == 'n':
        print('Canceled; no files changed.')
        return False
    _save_config(path, config, validate)
    print(f'Saved {path}')
    return True
