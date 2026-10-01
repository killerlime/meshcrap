#!/bin/bash
set -euo pipefail
install -d "${ROOTFS_DIR}/opt/meshcrap"
tar xzf files/source.tar.gz -C "${ROOTFS_DIR}/opt/meshcrap"
on_chroot <<'EOF'
set -eu
python3 -m venv /opt/meshcrap/.venv
/opt/meshcrap/.venv/bin/pip install --no-cache-dir -r /opt/meshcrap/requirements.txt
/opt/meshcrap/.venv/bin/pip check
useradd --system --create-home --home-dir /var/lib/meshcrap --shell /usr/sbin/nologin meshcrap
chown -R meshcrap:meshcrap /opt/meshcrap
install -m 755 /opt/meshcrap/deploy/pi/meshcrap-setup /usr/local/sbin/meshcrap-setup
install -m 644 /opt/meshcrap/deploy/meshcrap-dashboard.service /etc/systemd/system/
install -m 644 /opt/meshcrap/deploy/meshcrap-collector.service /etc/systemd/system/
systemctl disable meshcrap-dashboard meshcrap-collector
mkdir -p /opt/meshcrap/image-manifest
dpkg-query -W > /opt/meshcrap/image-manifest/debian-packages.txt
/opt/meshcrap/.venv/bin/pip freeze > /opt/meshcrap/image-manifest/python-packages.txt
cd /opt/meshcrap
.venv/bin/python tests/smoke.py
.venv/bin/python tests/efficiency.py
test ! -e config.json
test ! -e /var/lib/tailscale/tailscaled.state
cat > /etc/motd <<'MOTD'
Meshcrap — unofficial Raspberry Pi OS image
Run sudo meshcrap-setup to configure your dashboard and radio.
Collection and remote access remain off until you configure them.
MOTD
EOF
