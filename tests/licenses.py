"""Fail when vendored assets lose provenance or required bundled notices."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];vendor=root/'source/dashboard/static/vendor'
manifest=json.loads((vendor/'manifest.json').read_text())
for name,entry in manifest.items():
    assert entry['source'].startswith('https://'),name
    assert hashlib.sha256((vendor/name).read_bytes()).hexdigest()==entry['sha256'],name
for name in ['licenses/Leaflet-LICENSE','android/LICENSE','android/app/src/main/assets/licenses/GPL-3.0.txt','android/app/src/main/assets/licenses/Protobuf-LICENSE.txt','android/app/src/main/assets/licenses/NOTICE.txt','THIRD_PARTY_NOTICES.md']:
    assert len((root/name).read_bytes())>100,name
assert (root/'licenses/Leaflet-LICENSE').read_text().strip()==(vendor/'Leaflet-LICENSE').read_text().strip()
assert (root/'source/dashboard/static/lcd-leaflet.js').read_text().strip()==(vendor/'leaflet-1.9.4.js').read_text().strip()
protos=json.loads((root/'android/proto-sources.json').read_text(encoding='utf-8'))
assert protos['repository']=='https://github.com/meshtastic/protobufs'
assert len(protos['revision'])==40 and all(c in '0123456789abcdef' for c in protos['revision'])
assert protos['license']=='GPL-3.0'
folder=root/'android/app/src/main/proto/meshtastic'
assert set(protos['files'])=={p.name for p in folder.glob('*.proto')}
for name,entry in protos['files'].items():
    assert entry['source']==f"https://github.com/meshtastic/protobufs/blob/{protos['revision']}/meshtastic/{name}"
    assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==entry['sha256'],name
print('PASS: vendored hashes, immutable protocol sources and required license files')
