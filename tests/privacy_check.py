"""Reject accidental state, deployment identifiers and credential additions.

This is a release gate, not a guarantee. It examines tracked and nonignored
untracked files without printing matched values. Build archives receive a
separate inspection with tools/audit_artifact.py.
"""
from pathlib import Path
import re, subprocess, hashlib, json, os, sys

ROOT=Path(__file__).resolve().parents[1]

rules={
 'Tailscale credential':r'\btskey-[A-Za-z0-9_-]{10,}',
 'SSH public key':r'\b(?:ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+[A-Za-z0-9+/]{30,}={0,3}',
 'Tailscale address':r'\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b',
 'private key':r'-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----',
 'GitHub token':r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b',
 'personal home path':r'(?:/home/(?!meshcrap\b)[a-z][a-z0-9_-]+/|[A-Za-z]:[\\/]Users[\\/])',
 'private network literal':r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
 'Tailscale deployment hostname':r'\b[a-z0-9-]+\.tail[a-z0-9]+\.ts\.net\b',
 'credential literal':r'''(?:["']?(?:api[_-]?key|api[_-]?token|access[_-]?token|auth[_-]?key|pairing[_-]?key|private[_-]?key|password|psk)["']?\s*[:=]\s*["'])([A-Za-z0-9_+/=-]{20,})["']''',
 'URL credentials':r'''https?://[^\s/"'<>]+:[^\s/"'<>]+@[^\s/"'<>]+''',
 'credential in URL':r'''https?://[^\s"'<>]+[?&](?:api[_-]?key|token|access[_-]?token|key)=[A-Za-z0-9_+/=%-]{20,}''',
}

PRIVATE_POLICY_ENV='MESHCRAP_PRIVATE_PRIVACY_POLICY'


def load_private_policy(path=None):
    """Keep installation-specific markers outside public source and artifacts.

    Deterministic hashes of names are guessable; they are private policy data,
    not anonymized values that belong in a public default configuration.
    """
    if path is None:path=os.environ.get(PRIVATE_POLICY_ENV)
    if path is None:return set()
    try:
        if not isinstance(path,(str,os.PathLike)) or not str(path).strip():raise ValueError()
        location=Path(path).expanduser()
        if not location.is_absolute():raise ValueError()
        location=location.resolve(strict=True)
        if location.is_relative_to(ROOT.resolve()) or not location.is_file() or location.stat().st_size>65536:
            raise ValueError()
        value=json.loads(location.read_text(encoding='utf-8'))
        if not isinstance(value,dict) or set(value)!={'fingerprints'}:raise ValueError()
        entries=value['fingerprints']
        if not isinstance(entries,list) or len(entries)>512 or any(
            not isinstance(entry,str) or not re.fullmatch(r'[0-9a-f]{64}',entry) for entry in entries):
            raise ValueError()
        return set(entries)
    except (OSError,ValueError,TypeError,UnicodeError,RuntimeError):
        raise ValueError('Invalid private privacy policy. Use a valid external JSON file.') from None


try:
    denied=load_private_policy()
except ValueError as error:
    if __name__=='__main__':
        print(str(error),file=sys.stderr);raise SystemExit(2)
    raise

STATE_PARTS={'data','.runtime','.venv','backups','snapshots','.ssh','.tailscale'}
PRIVATE_NAMES={'authorized_keys','known_hosts','id_rsa','id_ed25519','tailscaled.state',
 'tailscaled.log.conf','config.json','api-token','weather-api-key','.node-control-key',
 'session-secret','local.properties','sniffer-config.json','sniffer-settings.json'}
PRIVATE_SUFFIXES={'.db','.sqlite','.sqlite3','.pem','.key','.dpapi','.jks','.keystore',
 '.ppk','.p12','.pfx','.apk','.aab','.iq','.cf32','.cu8','.cfile','.pcap','.pcapng',
 '.img','.iso','.vhd','.vhdx','.qcow2','.ova','.exe'}


def private_label(text):
    if not denied:return False
    words=re.findall(r'[a-z0-9]+',text.lower())
    joined=re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)+',text.lower())
    candidates=words+joined+[a+sep+b for a,b in zip(words,words[1:]) for sep in ('-',' ')]
    return any(hashlib.sha256(w.encode()).hexdigest() in denied for w in candidates)


def scan_source(name,raw):
    """Return issue categories only; callers never expose matching bytes."""
    path=Path(name);errors=[]
    if any(part in STATE_PARTS for part in path.parts):errors.append('private state directory')
    if path.name in PRIVATE_NAMES or path.name.startswith(('config.local.','.env')) and path.name!='.env.example':errors.append('private configuration or trust material')
    if path.suffix.lower() in PRIVATE_SUFFIXES or re.search(r'\.(?:db|sqlite|sqlite3)-(?:wal|shm|journal)$',path.name):errors.append('private state or binary artifact')
    try:text=raw.decode('utf-8')
    except UnicodeDecodeError:return errors+['unreviewed binary file']
    if '/proto/' not in name and not name.startswith('licenses/') and private_label(text):errors.append('personal deployment identifier')
    fixture=name.startswith(('tests/','ios/Tests/','android/app/src/test/'))
    for label,pattern in rules.items():
        for match in re.finditer(pattern,text,re.I):
            # Recognizable synthetic credentials belong only in test fixtures.
            if fixture and label=='credential literal' and (
                len(set(match[1]))==1 or match[1].startswith('synthetic-')):continue
            # Generic example-host rejection tests do not expose a real login.
            if fixture and label=='URL credentials' and re.fullmatch(
                r'https?://user:password@(?:[a-z0-9-]+\.)*example(?:\.com|\.net|\.org)?(?::\d+)?',
                match[0],re.I):continue
            errors.append(label);break
    return list(dict.fromkeys(errors))


def check(root=ROOT):
    result=subprocess.run(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=root,capture_output=True,check=True)
    errors=[]
    vendor=root/'source/dashboard/static/vendor';assets=root/'source/dashboard/static/app-assets'
    for name in result.stdout.decode().split('\0'):
        if not name:continue
        p=root/name
        if not p.is_file():continue
        raw=p.read_bytes()
        if p.is_relative_to(vendor) and p.name!='manifest.json':
            manifest=json.loads((vendor/'manifest.json').read_text(encoding='utf-8'))
            entry=manifest.get(p.relative_to(vendor).as_posix(),{})
            if hashlib.sha256(raw).hexdigest()!=entry.get('sha256'):errors.append(name+': vendor checksum mismatch')
            continue
        if p.is_relative_to(assets) and p.suffix=='.png':
            manifest=json.loads((assets/'asset-checksums.json').read_text(encoding='utf-8'))
            if hashlib.sha256(raw).hexdigest()!=manifest.get(p.name):errors.append(name+': app icon checksum mismatch')
            continue
        errors.extend(name+': '+issue for issue in scan_source(name,raw))
    return errors


if __name__=='__main__':
    findings=check()
    if findings:
        print('\n'.join(findings));raise SystemExit(1)
    print('PASS: outgoing source and nonignored files contain no detected private state, deployment identifiers or credentials')
