#!/usr/bin/env python3
"""Configure and run an isolated Meshcrap installation; never copy live state."""
from contextlib import closing
import argparse
import html
import ipaddress
import json
import math
import os
from pathlib import Path
import py_compile
import re
import sqlite3
import subprocess
import sys
from urllib.parse import urlsplit
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding='utf-8'))
    defaults = json.loads((ROOT/'config.example.json').read_text())
    unknown = set(config) - set(defaults)
    if unknown:
        raise ValueError('Unknown configuration keys: '+', '.join(sorted(unknown)))
    config = defaults | config
    for key in ('radio_port','web_port'):
        if type(config[key]) is not int or not 1 <= config[key] <= 65535:
            raise ValueError(key+' must be a TCP port')
    if not re.fullmatch(r'![0-9a-fA-F]{8}', config['receiver_id']):
        raise ValueError('receiver_id must be ! followed by eight hexadecimal digits')
    config['receiver_id'] = config['receiver_id'].lower()
    for key in ('radio_host','bind_host','https_host','weather_station'):
        if not isinstance(config[key],str) or not re.fullmatch(r'[A-Za-z0-9_.:\-]*',config[key]):
            raise ValueError('Invalid '+key)
    for key in ('enable_radio_controls','enable_weather','enable_potato'):
        if type(config[key]) is not bool: raise ValueError(key+' must be boolean')
    if type(config['radio_idle_timeout']) is not int or config['radio_idle_timeout'] < 0:
        raise ValueError('radio_idle_timeout must be a nonnegative integer')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,7}', config['node_prefix']):
        raise ValueError('node_prefix must be 1–8 letters/digits, starting with a letter')
    config['node_prefix'] = config['node_prefix'].upper()
    ZoneInfo(config['timezone'])
    if not re.fullmatch(r'[A-Za-z0-9_+\-/]+',config['timezone']):raise ValueError('Invalid timezone')
    if type(config['potato_channel_slot']) is not int or not 0<=config['potato_channel_slot']<=7:raise ValueError('Invalid Potato channel slot')
    types={'TEXT_MESSAGE_APP','NODEINFO_APP','POSITION_APP','TELEMETRY_APP','NEIGHBORINFO_APP'}
    if not isinstance(config['potato_types'],list) or not config['potato_types'] or any(p not in types for p in config['potato_types']):raise ValueError('Invalid Potato data types')
    if config['potato_url']:
        url=urlsplit(config['potato_url'])
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/') or url.port not in (None,443):raise ValueError('potato_url must be an HTTPS origin without a path or credentials')
        if not re.fullmatch(r'https://[A-Za-z0-9.\-]+(?::443)?/?',config['potato_url']):raise ValueError('Invalid Potato origin')
        config['potato_url']=config['potato_url'].rstrip('/')
    if config['enable_potato'] and (not config['potato_url'] or not config['radio_host'] or config['receiver_id']=='!00000000'):raise ValueError('Configure a Potato origin and receiver before enabling the feed')
    for key,limit in (('home_lat',90),('home_lon',180)):
        if type(config[key]) not in (int,float) or not math.isfinite(config[key]) or abs(config[key])>limit:
            raise ValueError('Invalid '+key)
    if not isinstance(config['allowed_networks'],list) or not config['allowed_networks']:
        raise ValueError('Set at least one allowed network')
    for network in config['allowed_networks']: ipaddress.ip_network(network)
    if not isinstance(config['trusted_hosts'],list) or not config['trusted_hosts']:
        raise ValueError('Set at least one trusted host')
    if any(not isinstance(h,str) or not re.fullmatch(r'[A-Za-z0-9_.:\-]+',h) for h in config['trusted_hosts']):
        raise ValueError('Invalid trusted host')
    if config['initial_lna_state'] not in ('UNKNOWN','OFF','ON'):
        raise ValueError('initial_lna_state must be UNKNOWN, OFF, or ON')
    regions=config['regions']
    if not isinstance(regions,dict) or 'home' not in regions or len(regions)>12:
        raise ValueError('Configure up to 12 regions including home')
    for ident,region in regions.items():
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',ident):raise ValueError('Invalid region ID')
        bounds=region['bounds']
        if len(bounds)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in bounds):
            raise ValueError('Invalid bounds for '+ident)
        s,n,w,e=bounds
        if not -90<=s<n<=90 or not -180<=w<e<=180:raise ValueError('Invalid region extent')
        miles=region['cell_miles']
        if type(miles) not in (int,float) or not 0.25<=miles<=100:raise ValueError('Invalid grid size')
        if (n-s)*69/miles * (e-w)*69/miles > 10000:raise ValueError('Region exceeds 10,000 cells; enlarge grid size')
        if set(region)-{'name','bounds','cell_miles','accent','tagline'}:raise ValueError('Unknown region field')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',region.get('accent','#45d68c')):raise ValueError('Invalid region color')
        region.setdefault('accent','#45d68c');region.setdefault('tagline','Coverage survey')
        for k in ('name','tagline'):
            if not isinstance(region[k],str) or len(region[k])>120 or any(ord(c)<32 for c in region[k]):raise ValueError('Invalid region label')
    if not isinstance(config['channels'],dict) or not config['channels']:raise ValueError('Set message channel labels')
    if any(k not in [str(n) for n in range(8)] or not isinstance(v,str) or len(v)>80 for k,v in config['channels'].items()):raise ValueError('Invalid channel labels')
    data = Path(config['data_dir']).expanduser()
    data = (path.parent/data).resolve() if not data.is_absolute() else data.resolve()
    # Tokens are inserted into Python, JS and HTML strings. Reject ambiguous literal delimiters.
    if any(c in data.as_posix() for c in "'\"\n\r"):
        raise ValueError('data_dir cannot contain quotes or newlines')
    if data == ROOT or ROOT/'source' == data:
        raise ValueError('Use a separate data directory')
    return config,data


def render(config,data):
    runtime = data/'.runtime'
    tokens={key.upper():repr(value) if isinstance(value,(bool,int,float,list,dict)) else str(value) for key,value in config.items()}
    tokens.update(DATA_DIR=data.as_posix(),RECEIVER_NUM=str(int(config['receiver_id'][1:],16)),
        NODE_PREFIX_LOWER=config['node_prefix'].lower(),AREAS=repr(config['regions']),
        AREA_IDS=json.dumps(list(config['regions'])),
        AREA_OPTIONS=''.join('<option value="'+k+'">'+html.escape(v['name'])+'</option>' for k,v in config['regions'].items()),
        CHANNEL_OPTIONS=''.join('<option value="'+k+'">'+html.escape(v)+'</option>' for k,v in config['channels'].items()))
    for source in (ROOT/'source').rglob('*'):
        if not source.is_file() or '__pycache__' in source.parts or source.suffix in ('.pyc','.pyo'):continue
        target=runtime/source.relative_to(ROOT/'source');target.parent.mkdir(parents=True,exist_ok=True)
        if any(part in ('vendor','app-assets') for part in source.relative_to(ROOT/'source').parts):
            stage=target.with_name(target.name+'.tmp');stage.write_bytes(source.read_bytes());stage.replace(target)
            continue
        text=source.read_text(encoding='utf-8')
        def substitute(match):
            if match[1] not in tokens:raise ValueError('Unknown source token: '+match[1])
            return tokens[match[1]]
        text=re.sub(r'@@([A-Z_]+)@@',substitute,text)
        stage=target.with_name(target.name+'.tmp');stage.write_text(text,encoding='utf-8',newline='\n');stage.replace(target)
        if target.suffix=='.py':py_compile.compile(str(target),doraise=True)
    (runtime/'dashboard/messages_config.json').write_text(json.dumps({'channel':next(iter(config['channels'])),'channels':config['channels']}))
    return runtime


def initialize(config,data):
    # Serialize first installation and runtime rendering when both services start.
    data.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (data/".init-lock").open("a+") as lock:
        if sys.platform == "linux":
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        return _initialize(config,data)


def _initialize(config,data):
    data.mkdir(parents=True,exist_ok=True,mode=0o700)
    database=data/'mesh.db'
    if not database.exists():
        with closing(sqlite3.connect(database)) as db,db:
            db.executescript((ROOT/'schema.sql').read_text());db.execute('PRAGMA user_version=1')
    else:
        with closing(sqlite3.connect(database)) as db,db:
            if db.execute('PRAGMA user_version').fetchone()[0]!=1:
                raise ValueError('Unsupported database version; never initialize over a live installation database')
    for folder in ('reports','backups','potato-feed','dashboard-security'):(data/folder).mkdir(exist_ok=True,mode=0o700)
    experiment=data/'reports/lna-experiment.json'
    if not experiment.exists():
        now=datetime.now(timezone.utc).isoformat()
        experiment.write_text(json.dumps({'start_utc':now,'transitions':[{'time_utc':now,'state':config['initial_lna_state'],'basis':'Initial configuration; confirm physical state'}],
           'fixed_setup':{'note':'Record your antenna, filter, feed line and receiver setup here'}}))
    (data/'dashboard-security/network.json').write_text(json.dumps({'https_host':config['https_host'] or None}))
    (data/'potato-feed/primary-policy-start').write_text('0')
    # Legacy diagnostic table; the optional exporter creates its own queue on startup.
    with closing(sqlite3.connect(data/'potato-feed/outbox.db')) as db,db:
        db.execute('CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,created REAL,payload TEXT,status TEXT)')
    return render(config,data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(ROOT/'config.json'))
    parser.add_argument('command',choices=('setup','init','serve','collect','check','feed'))
    args=parser.parse_args()
    if args.command=='setup':
        from setup_wizard import configure
        if not configure(args.config,json.loads((ROOT/'config.example.json').read_text()),load_config):return
        config,data=load_config(args.config)
        initialize(config,data)
        print(f'Ready. Run: python meshcrap.py --config "{Path(args.config).resolve()}" serve')
        print(f'Then open http://127.0.0.1:{config["web_port"]}')
        print('To receive packets, run the collect command separately after configuring a radio.')
        return
    config,data=load_config(args.config)
    if args.command=='collect' and (not config['radio_host'] or int(config['receiver_id'][1:],16) in (0,0xffffffff)):
        raise ValueError('Set radio_host and the actual receiver_id before starting collection')
    if args.command in ('serve','collect','feed') and sys.platform!='linux':
        raise ValueError('The collector/dashboard currently require Linux. Use Linux, a Raspberry Pi, or WSL2.')
    runtime=initialize(config,data)
    if args.command in ('init','check'):
        with closing(sqlite3.connect(data/'mesh.db')) as db:assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        print('Configuration, source compilation and database integrity OK')
        return
    program=runtime/({'serve':'dashboard/app.py','collect':'collector.py','feed':'potato_feed.py'}[args.command])
    env=dict(os.environ,PYTHONPATH=str(runtime)+os.pathsep+str(runtime/'dashboard'),PYTHONUNBUFFERED='1')
    os.execve(sys.executable,[sys.executable,str(program)],env)


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as error:
        print('Setup error: '+str(error),file=sys.stderr);raise SystemExit(2)
