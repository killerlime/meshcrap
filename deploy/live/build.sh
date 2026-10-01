#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
repo=$PWD
test "$(id -u)" = 0 || { echo 'Build on a disposable Debian/Ubuntu host as root.'; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p dist/live
cd "$work"
lb config --mode debian --distribution bookworm --architectures amd64 \
  --binary-images iso-hybrid --debian-installer none \
  --archive-areas main --bootappend-live 'boot=live components toram nopersistence noswap username=meshcrap hostname=meshcrap-live'
mkdir -p config/package-lists config/includes.chroot/opt/meshcrap config/hooks/normal \
  config/includes.chroot/usr/local/bin config/includes.chroot/etc/skel/Desktop
cat > config/package-lists/meshcrap.list.chroot <<'EOF'
live-boot
live-config
live-config-systemd
linux-image-amd64
task-xfce-desktop
firefox-esr
python3-venv
ca-certificates
EOF
git -c safe.directory="$repo" -C "$repo" archive HEAD | tar -x -C config/includes.chroot/opt/meshcrap
install -m 755 "$repo/deploy/live/start.sh" config/includes.chroot/usr/local/bin/meshcrap-live-start
install -m 755 "$repo/deploy/live/self-test.sh" config/includes.chroot/usr/local/bin/meshcrap-live-self-test
mkdir -p config/includes.chroot/etc/systemd/system/multi-user.target.wants
cat > config/includes.chroot/etc/systemd/system/meshcrap-live-self-test.service <<'EOF'
[Unit]
Description=Opt-in live image verification
ConditionKernelCommandLine=meshcrap.selftest
After=local-fs.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/meshcrap-live-self-test
StandardOutput=tty
TTYPath=/dev/ttyS0
EOF
ln -s ../meshcrap-live-self-test.service config/includes.chroot/etc/systemd/system/multi-user.target.wants/meshcrap-live-self-test.service
cat > config/includes.chroot/etc/skel/Desktop/meshcrap.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Start Meshcrap
Comment=Configure a temporary dashboard in RAM
Exec=xfce4-terminal --command=/usr/local/bin/meshcrap-live-start
Icon=network-wireless
Terminal=false
EOF
chmod 755 config/includes.chroot/etc/skel/Desktop/meshcrap.desktop
cat > config/hooks/normal/090-meshcrap.hook.chroot <<'EOF'
#!/bin/sh
set -eu
python3 -m venv /opt/meshcrap/.venv
/opt/meshcrap/.venv/bin/pip install --no-cache-dir -r /opt/meshcrap/requirements.txt
/opt/meshcrap/.venv/bin/pip check
/opt/meshcrap/.venv/bin/pip freeze > /opt/meshcrap/BUILD-DEPENDENCIES.txt
systemctl mask ssh.service ssh.socket 2>/dev/null || true
# Prevent desktop removable-volume automounting; operators can explicitly save exports.
mkdir -p /etc/xdg/xfce4/xfconf/xfce-perchannel-xml
cat > /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/thunar-volman.xml <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="thunar-volman" version="1.0"><property name="automount-drives" type="bool" value="false"/><property name="automount-media" type="bool" value="false"/><property name="autobrowse" type="bool" value="false"/></channel>
XML
EOF
chmod 755 config/hooks/normal/090-meshcrap.hook.chroot
lb build
install -m 644 live-image-amd64.hybrid.iso "$repo/dist/live/meshcrap-live-amd64.iso"
cd "$repo/dist/live"
sha256sum meshcrap-live-amd64.iso > SHA256SUMS
printf 'Source: %s\nExperimental live-build ISO; boot verification required.\n' "$(git -c safe.directory="$repo" -C "$repo" rev-parse HEAD)" > BUILD.txt
cp "$repo/deploy/live/README.md" .
