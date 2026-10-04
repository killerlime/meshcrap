#!/bin/bash
set -euo pipefail
install -d "${ROOTFS_DIR}/opt/meshcrap"
tar xzf files/source.tar.gz -C "${ROOTFS_DIR}/opt/meshcrap"
on_chroot <<'EOF'
set -eu
python3 -m venv /opt/meshcrap/.venv
/opt/meshcrap/.venv/bin/pip install --no-cache-dir -r /opt/meshcrap/requirements.txt
/opt/meshcrap/.venv/bin/pip check
/opt/meshcrap/.venv/bin/python /opt/meshcrap/tools/license_inventory.py /opt/meshcrap/third-party
dpkg-query -W > /opt/meshcrap/BUILD-OS-PACKAGES.txt
useradd --system --no-create-home --home-dir /var/lib/meshcrap --shell /usr/sbin/nologin meshcrap
install -d -m 700 -o meshcrap -g meshcrap /var/lib/meshcrap
# The service owns its state, not the executable application or dependencies.
chown -R root:root /opt/meshcrap
install -m 755 /opt/meshcrap/deploy/pi/meshcrap-setup /usr/local/sbin/meshcrap-setup
install -m 644 /opt/meshcrap/deploy/meshcrap-dashboard.service /etc/systemd/system/
install -m 644 /opt/meshcrap/deploy/meshcrap-collector.service /etc/systemd/system/
sed -i 's|/opt/meshcrap/config.json|/var/lib/meshcrap/config.json|g' /etc/systemd/system/meshcrap-*.service
systemctl disable meshcrap-dashboard meshcrap-collector
mkdir -p /opt/meshcrap/image-manifest
dpkg-query -W > /opt/meshcrap/image-manifest/debian-packages.txt
/opt/meshcrap/.venv/bin/pip freeze > /opt/meshcrap/image-manifest/python-packages.txt
cd /opt/meshcrap
.venv/bin/python tests/smoke.py
.venv/bin/python tests/efficiency.py
.venv/bin/python tests/pi_setup.py
systemd-analyze verify /etc/systemd/system/meshcrap-dashboard.service /etc/systemd/system/meshcrap-collector.service
test ! -e config.json
test ! -e /var/lib/tailscale/tailscaled.state
test -z "$(find /var/lib/meshcrap -mindepth 1 -print -quit)"
cat > /etc/motd <<'MOTD'
Meshcrap — unofficial Raspberry Pi OS image
Run sudo meshcrap-setup to configure your dashboard and radio.
Collection and remote access remain off until you configure them.
MOTD
EOF
