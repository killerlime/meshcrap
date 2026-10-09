"""Inspect ZIP/APK contents for the same private markers as outgoing source.

This is a release gate, not a guarantee of absence. Review findings and inspect
the artifact inventory manually. Never extract an untrusted archive to disk.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR=ROOT/'source/dashboard/static/vendor'
VENDOR_MANIFEST=json.loads((VENDOR/'manifest.json').read_text(encoding='utf-8'))
ASSET_MANIFEST=json.loads((ROOT/'source/dashboard/static/app-assets/asset-checksums.json').read_text(encoding='utf-8'))
_spec=importlib.util.spec_from_file_location('meshcrap_release_privacy',ROOT/'tests/privacy_check.py')
privacy=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(privacy)


def policy():
    return privacy.rules, privacy.denied


def policy_name(name):
    # Git source archives may contain one conventional project-root prefix.
    parts=name.replace('\\','/').split('/')
    if len(parts)>1 and (parts[0]=='meshcrap' or parts[0].startswith('meshcrap-')):
        return '/'.join(parts[1:])
    return name.replace('\\','/')


def dex_strings(raw):
    if len(raw)<64:raise ValueError('Invalid DEX header')
    count,offset=struct.unpack_from('<II',raw,56)
    if count>1_000_000 or offset+count*4>len(raw):raise ValueError('Invalid DEX string table')
    strings=[]
    for index in range(count):
        cursor=struct.unpack_from('<I',raw,offset+index*4)[0]
        if cursor>=len(raw):raise ValueError('Invalid DEX string offset')
        for _ in range(5):
            if cursor>=len(raw):raise ValueError('Invalid DEX string length')
            byte=raw[cursor];cursor+=1
            if not byte&128:break
        else:raise ValueError('Invalid DEX string length')
        end=raw.find(b'\x00',cursor)
        if end<0:raise ValueError('Unterminated DEX string')
        strings.append(raw[cursor:end].decode('utf-8',errors='replace'))
    return '\n'.join(strings)


def audit(path):
    findings = []
    inventory = []
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist())>20000 or sum(item.file_size for item in archive.infolist()) > 512*1024*1024:
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
            normalized=policy_name(name)
            vendor_name=None
            for prefix in ('source/dashboard/static/vendor/','vendor/'):
                if normalized.startswith(prefix):vendor_name=normalized[len(prefix):];break
            if vendor_name is not None and vendor_name!='manifest.json':
                # Do not interpret glyph binary bytes as private identifiers.
                # Approved upstream assets still require their pinned checksum.
                expected=VENDOR_MANIFEST.get(vendor_name,{}).get('sha256')
                if hashlib.sha256(raw).hexdigest()!=expected:findings.append((name,'vendor checksum mismatch'))
                continue
            if normalized.startswith('source/dashboard/static/app-assets/') and normalized.endswith('.png'):
                expected=ASSET_MANIFEST.get(Path(normalized).name)
                if hashlib.sha256(raw).hexdigest()!=expected:findings.append((name,'app icon checksum mismatch'))
                continue
            # Includes strings in DEX and UTF-16 resources; do not print matches.
            if raw.startswith(b'dex\n'):
                text=dex_strings(raw)
            else:
                text = raw.replace(b'\x00', b'').decode('utf-8', errors='replace')
            # Shared source policy retains narrow, recognizable fixture exceptions.
            for label in privacy.scan_source(normalized,text.encode('utf-8')):
                if (name,label) not in findings:findings.append((name,label))
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
