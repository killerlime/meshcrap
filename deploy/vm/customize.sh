#!/bin/sh
set -eu
export DEBIAN_FRONTEND=noninteractive
# The cloud image's resolved symlink has no target in the offline chroot.
# Use public DNS only during the disposable build; restored to DHCP below.
rm -f /etc/resolv.conf
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\noptions timeout:3 attempts:2\n' > /etc/resolv.conf
# Cloud NSS can require systemd-resolved's IPC even with a usable resolv.conf.
# The offline customization chroot has no running system bus.
sed -i 's/^hosts:.*/hosts: files dns/' /etc/nsswitch.conf
getent hosts deb.debian.org >/dev/null || { echo 'Build appliance DNS lookup failed'; exit 1; }
apt-get update -o APT::Update::Error-Mode=any
apt-get install -y python3-venv python3-pip sudo systemd-resolved qemu-guest-agent
mkdir -p /opt/meshcrap
tar xzf /tmp/meshcrap-source.tar.gz -C /opt/meshcrap
python3 -m venv /opt/meshcrap/.venv
/opt/meshcrap/.venv/bin/pip install --no-cache-dir -r /opt/meshcrap/requirements.txt
/opt/meshcrap/.venv/bin/pip check
/opt/meshcrap/.venv/bin/python /opt/meshcrap/tools/license_inventory.py /opt/meshcrap/third-party
dpkg-query -W > /opt/meshcrap/BUILD-OS-PACKAGES.txt
id meshcrap >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo meshcrap
passwd -l meshcrap
passwd -l root
chown -R meshcrap:meshcrap /opt/meshcrap
install -m 755 /opt/meshcrap/deploy/vm/first-boot.sh /usr/local/sbin/meshcrap-first-boot
install -m 755 /opt/meshcrap/deploy/vm/meshcrap-setup /usr/local/sbin/meshcrap-setup
cp /opt/meshcrap/deploy/meshcrap-*.service /etc/systemd/system/
cat > /etc/systemd/system/meshcrap-first-boot.service <<'EOF'
[Unit]
Description=Create unique local console credentials
Before=getty@tty1.service serial-getty@ttyS0.service
ConditionPathExists=!/var/lib/meshcrap-first-boot-complete
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/meshcrap-first-boot
StandardOutput=null
StandardError=journal
[Install]
WantedBy=multi-user.target
EOF
mkdir -p /etc/systemd/network
cat > /etc/systemd/network/20-meshcrap.network <<'EOF'
[Match]
Name=en* eth*
[Network]
DHCP=yes
EOF
ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
touch /etc/cloud/cloud-init.disabled
systemctl disable networking.service ssh.service ssh.socket 2>/dev/null || true
systemctl mask ssh.service ssh.socket
systemctl enable systemd-networkd systemd-resolved meshcrap-first-boot qemu-guest-agent
rm -f /etc/ssh/ssh_host_* /var/lib/dbus/machine-id
truncate -s 0 /etc/machine-id
rm -f /tmp/meshcrap-source.tar.gz
apt-get clean
