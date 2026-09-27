"""Reject common accidental state/credential additions to the outgoing Git tree."""
from pathlib import Path
import re,subprocess,sys

root=Path(__file__).resolve().parents[1]
result=subprocess.run(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=root,capture_output=True,check=True)
errors=[]
for name in result.stdout.decode().split('\0'):
    if not name:continue
    p=root/name
    if not p.is_file():continue
    if any(part in ('data','.runtime','.venv','backups','snapshots') for part in p.relative_to(root).parts):errors.append(name+': private state directory')
    if p.suffix.lower() in ('.db','.sqlite','.sqlite3','.pem','.key','.dpapi','.jks','.keystore','.apk','.aab'):errors.append(name+': private state or binary artifact')
    raw=p.read_bytes()
    try:text=raw.decode('utf-8')
    except UnicodeDecodeError:errors.append(name+': unreviewed binary file');continue
    if name==str(Path(__file__).relative_to(root)).replace('\\','/'):continue
    rules={
      'private key':r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',
      'GitHub token':r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b',
      'personal home path':r'(?:/home/(?!meshcrap\b)[a-z][a-z0-9_-]+/|[A-Za-z]:[\\/]Users[\\/])',
      'private network literal':r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
      'Tailscale deployment hostname':r'\b[a-z0-9-]+\.tail[a-z0-9]+\.ts\.net\b',
    }
    for label,pattern in rules.items():
        if re.search(pattern,text,re.I):errors.append(name+': '+label)
if errors:
    print('\n'.join(errors));raise SystemExit(1)
print('PASS: outgoing tracked/untracked source contains no detected private state, personal paths, private network literals or common credentials')
