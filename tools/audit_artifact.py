"""Inspect ZIP/APK contents for the same private markers as outgoing source.

This is a release gate, not a guarantee of absence. Review findings and inspect
the artifact inventory manually. Never extract an untrusted archive to disk.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def policy():
    tree = ast.parse((ROOT/'tests/privacy_check.py').read_text())
    values = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('rules', 'denied'):
                    values[target.id] = ast.literal_eval(node.value)
    return values['rules'], values['denied']


def audit(path):
    rules, denied = policy()
    findings = []
    inventory = []
    with zipfile.ZipFile(path) as archive:
        if sum(item.file_size for item in archive.infolist()) > 512*1024*1024:
            raise ValueError('Archive exceeds review size limit')
        for item in archive.infolist():
            if item.is_dir(): continue
            name = item.filename
            parts = Path(name.replace('\\', '/')).parts
            if '..' in parts or name.startswith(('/', '\\')):
                findings.append((name, 'unsafe archive path'))
            if any(part in ('backups', 'snapshots', '.ssh', '.git', '.runtime') for part in parts):
                findings.append((name, 'private directory'))
            if Path(name).suffix.lower() in ('.db', '.sqlite', '.sqlite3', '.pem', '.key', '.ppk', '.dpapi', '.jks', '.keystore'):
                findings.append((name, 'private state or credentials'))
            raw = archive.read(item)
            inventory.append(dict(name=name, size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            # Includes strings in DEX and UTF-16 resources; do not print matches.
            if raw.startswith(b'dex\n'):
                count, offset = struct.unpack_from('<II', raw, 56)
                strings = []
                for index in range(count):
                    cursor = struct.unpack_from('<I', raw, offset+index*4)[0]
                    while raw[cursor] & 128: cursor += 1
                    cursor += 1
                    end = raw.index(b'\x00', cursor)
                    strings.append(raw[cursor:end].decode('utf-8', errors='replace'))
                text = '\n'.join(strings)
            else:
                text = raw.replace(b'\x00', b'').decode('utf-8', errors='replace')
            # The policy source contains its own detection patterns.
            if name.endswith('tests/privacy_check.py'): continue
            for label, pattern in rules.items():
                if re.search(pattern, text, re.I): findings.append((name, label))
            words = re.findall(r'[a-z0-9]+', text.lower())
            candidates = words + [a+sep+b for a,b in zip(words,words[1:]) for sep in ('-', ' ')]
            if any(hashlib.sha256(word.encode()).hexdigest() in denied for word in candidates):
                findings.append((name, 'private deployment marker'))
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                entries=inventory, findings=findings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.archive)
    args.report.write_text(json.dumps(result, indent=2)+'\n')
    print(f"Audited {len(result['entries'])} entries; {len(result['findings'])} findings. Review the private report.")
    raise SystemExit(bool(result['findings']))
