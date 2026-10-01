#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p dist/vm
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
origin=https://cloud.debian.org/images/cloud/bookworm/latest
base=debian-12-generic-amd64.qcow2
curl -fL "$origin/$base" -o "$work/$base"
curl -fL "$origin/SHA512SUMS" -o "$work/SHA512SUMS"
(cd "$work"; grep " $base$" SHA512SUMS | sha512sum -c -)
git archive HEAD | gzip > "$work/meshcrap-source.tar.gz"
qemu-img create -f qcow2 "$work/appliance.qcow2" 8G
export LIBGUESTFS_BACKEND=direct
virt-resize --expand /dev/sda1 "$work/$base" "$work/appliance.qcow2"
virt-customize -a "$work/appliance.qcow2" --hostname meshcrap --upload "$work/meshcrap-source.tar.gz:/tmp/meshcrap-source.tar.gz" --run deploy/vm/customize.sh
qemu-img convert -O qcow2 -c "$work/appliance.qcow2" dist/vm/meshcrap-amd64.qcow2
qemu-img convert -O vhdx -o subformat=dynamic "$work/appliance.qcow2" dist/vm/meshcrap-amd64.vhdx
qemu-img convert -O vmdk -o subformat=streamOptimized "$work/appliance.qcow2" dist/vm/meshcrap-amd64.vmdk
python3 deploy/vm/ovf.py
bash deploy/vm/verify.sh "$work"
cp deploy/vm/README.md dist/vm/
printf 'Source commit: %s\nBase: %s/%s\nBase SHA512: %s\nVerified: QEMU BIOS boot and application checks for QCOW2, VHDX and VMDK; native hypervisor imports not verified\n' "$(git rev-parse HEAD)" "$origin" "$base" "$(sha512sum "$work/$base" | cut -d' ' -f1)" > dist/vm/BUILD.txt
(cd dist/vm; sha256sum *.qcow2 *.vhdx *.vmdk *.ova *.ovf > SHA256SUMS)
