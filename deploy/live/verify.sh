#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
work=$(mktemp -d)
pid=''
trap 'if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi; rm -rf "$work"' EXIT
iso="$PWD/dist/live/meshcrap-live-amd64.iso"
xorriso -osirrox on -indev "$iso" -extract /live/vmlinuz "$work/vmlinuz" -extract /live/initrd.img "$work/initrd.img"
accel=tcg
if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then accel=kvm; fi
qemu-system-x86_64 -accel "$accel" -m 4096 -smp 2 -display none -no-reboot \
  -kernel "$work/vmlinuz" -initrd "$work/initrd.img" -cdrom "$iso" \
  -append 'boot=live components toram nopersistence noswap username=meshcrap meshcrap.selftest console=ttyS0' \
  -serial "file:$work/console.log" -nic none &
pid=$!
for _ in $(seq 1 300); do
  if grep -q MESHCRAP_LIVE_VERIFIED "$work/console.log" 2>/dev/null; then
    echo 'PASS: live kernel/RAM overlay, no swap, isolated dashboard and setup tests'
    printf 'Verified: QEMU direct-kernel live RAM boot and app tests; firmware boot menu and physical USB unverified\n' >> dist/live/BUILD.txt
    exit 0
  fi
  kill -0 "$pid" 2>/dev/null || break
  sleep 2
done
echo 'Live ISO verification failed; no release artifact should be published.'
tail -n 60 "$work/console.log"
exit 1
