"""Reject common accidental state/credential additions to the outgoing Git tree."""
from pathlib import Path
import re,subprocess,sys,hashlib,json

root=Path(__file__).resolve().parents[1]
result=subprocess.run(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=root,capture_output=True,check=True)
errors=[]
for name in result.stdout.decode().split('\0'):
    if not name:continue
    p=root/name
    if not p.is_file():continue
    if any(part in ('data','.runtime','.venv','backups','snapshots') for part in p.relative_to(root).parts):errors.append(name+': private state directory')
    if p.suffix.lower() in ('.db','.sqlite','.sqlite3','.pem','.key','.dpapi','.jks','.keystore','.ppk','.apk','.aab'):errors.append(name+': private state or binary artifact')
    raw=p.read_bytes()
    vendor=root/'source/dashboard/static/vendor'
    if p.is_relative_to(vendor) and p.name!='manifest.json':
        manifest=json.loads((vendor/'manifest.json').read_text())
        entry=manifest.get(p.relative_to(vendor).as_posix(),{})
        if hashlib.sha256(raw).hexdigest()!=entry.get('sha256'):errors.append(name+': vendor checksum mismatch')
        continue
    assets=root/'source/dashboard/static/app-assets'
    if p.is_relative_to(assets) and p.suffix=='.png':
        manifest=json.loads((assets/'asset-checksums.json').read_text())
        if hashlib.sha256(raw).hexdigest()!=manifest.get(p.name):errors.append(name+': app icon checksum mismatch')
        continue
    try:text=raw.decode('utf-8')
    except UnicodeDecodeError:errors.append(name+': unreviewed binary file');continue
    if name==str(Path(__file__).relative_to(root)).replace('\\','/'):continue
    if p.name in ('authorized_keys','known_hosts','id_rsa','id_ed25519'):errors.append(name+': SSH identity or trust material')
    if p.name in ('tailscaled.state','tailscaled.log.conf'):errors.append(name+': Tailscale deployment state')
    rules={
      'Tailscale credential':r'\btskey-[A-Za-z0-9_-]{10,}',
      'SSH public key':r'\b(?:ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+)\s+[A-Za-z0-9+/]{30,}={0,3}',
      'Tailscale address':r'\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b',
      'private key':r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',
      'GitHub token':r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b',
      'personal home path':r'(?:/home/(?!meshcrap\b)[a-z][a-z0-9_-]+/|[A-Za-z]:[\\/]Users[\\/])',
      'private network literal':r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
      'Tailscale deployment hostname':r'\b[a-z0-9-]+\.tail[a-z0-9]+\.ts\.net\b',
    }
    # Fingerprints avoid republishing the private labels this check rejects.
    if '/proto/' not in name and not name.startswith('licenses/'):
        denied={'313f63a03b64a6deb4dff8bfe931825f89b7af9e64011d2d2e21e705ed2e5e3d', 'c9f5b7e52716ade5d621c97ffd845a64ea2946746d959b8ee6a057444ca6f8e9', '226015df8a6ee1cd5f690a3ecae3666057355f105e1ede087fce6a62e923cb91', '31b25869b39f1baa9e7fc279255901b696c36629e57294d4455f479534139852', '0b29840c2c1eec11b89bcc6078d86406afad04d30ca5ce67e0fef350845efb5e', '27d300fe53b3b94f115cfd63be02d868bcb8f755e56893709418084c1bfab1cd', '3293c9f8c7f1a0363cd54d6ca49c28ae160f4461d57b16a8ea8b4ffc5fe966be', '95fd8a89b0edb9824c750830d2043e9eb28238a313b249bb49803dfd26d7c47f', '2022d9212721bdd79490399a3ff328f3eef1ddf110edf7f4ab0e837e6f76e4d6', 'd2dbb2be65d9c5fd405224832a5cda87e4e09542c20ff2efe82aa5f3ee056760'}
        words=re.findall(r'[a-z0-9]+',text.lower())
        candidates=words+[a+sep+b for a,b in zip(words,words[1:]) for sep in ('-',' ')]
        if any(hashlib.sha256(w.encode()).hexdigest() in denied for w in candidates):
            errors.append(name+': personal deployment label')
    for label,pattern in rules.items():
        if re.search(pattern,text,re.I):errors.append(name+': '+label)
if errors:
    print('\n'.join(errors));raise SystemExit(1)
print('PASS: outgoing tracked/untracked source contains no detected private state, personal paths, private network literals or common credentials')
