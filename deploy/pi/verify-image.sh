#!/bin/bash
# Inspect the completed filesystem read-only; never execute boot or enable services.
set -euo pipefail
image=$(realpath "$1")
report=$(realpath -m "$2")
test "$(id -u)" = 0
mountpoint=$(mktemp -d /var/tmp/meshcrap-inspect.XXXXXXXX)
loop=''
cleanup() {
  mountpoint -q "$mountpoint" && umount "$mountpoint"
  if [ -n "$loop" ]; then losetup -d "$loop"; fi
  rmdir "$mountpoint"
}
trap cleanup EXIT
loop=$(losetup --find --show --read-only --partscan "$image")
udevadm settle
test -b "${loop}p2"
mount -o ro,noload "${loop}p2" "$mountpoint"
python3 - "$mountpoint" "$report" <<'PY'
import json, pathlib, sys
root, report = map(pathlib.Path, sys.argv[1:])
def absent(pattern):
    assert not list(root.glob(pattern)), 'Unexpected identity/state: '+pattern
for pattern in ('etc/ssh/ssh_host_*', 'var/lib/tailscale/tailscaled.state',
                'home/*/.ssh/authorized_keys', 'root/.ssh/authorized_keys',
                'opt/meshcrap/config.json', 'var/lib/meshcrap/*',
                'etc/systemd/system/multi-user.target.wants/meshcrap-*'):
    absent(pattern)
assert not list((root/'var/lib/meshcrap').iterdir()), 'Application state must be empty'
assert (root/'etc/machine-id').read_text().strip() in ('', 'uninitialized')
shadow = dict(line.split(':', 2)[:2] for line in (root/'etc/shadow').read_text().splitlines())
assert all(shadow.get(user, '').startswith(('!', '*')) for user in ('root', 'pi', 'meshcrap')), 'Default account is not locked'
for name in ('meshcrap-dashboard', 'meshcrap-collector'):
    unit=(root/f'etc/systemd/system/{name}.service').read_text()
    assert 'User=meshcrap' in unit and '/var/lib/meshcrap/config.json' in unit
assert (root/'opt/meshcrap').stat().st_uid == 0
assert (root/'var/lib/meshcrap').stat().st_mode & 0o777 == 0o700
for name in ('debian-packages.txt', 'python-packages.txt'):
    assert (root/'opt/meshcrap/image-manifest'/name).stat().st_size > 0
assert (root/'opt/meshcrap/LICENSE').is_file()
assert (root/'opt/meshcrap/THIRD_PARTY_NOTICES.md').is_file()
report.write_text(json.dumps({'filesystem_audit':'passed','state':'empty','default_passwords':'locked',
    'ssh_host_keys':'absent','machine_identity':'first boot','radio_services':'disabled',
    'physical_boot':'not tested'}, indent=2)+'\n')
print('PASS: final image identity, empty state, service defaults and license inventory')
PY
