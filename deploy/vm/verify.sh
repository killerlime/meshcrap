#!/bin/bash
set -euo pipefail
work=$1
# Test disposable overlays only; never boot an image intended for distribution.
cat > "$work/check-app.sh" <<'EOF'
#!/bin/bash
set -eu
cd /opt/meshcrap
.venv/bin/python tests/efficiency.py > /tmp/meshcrap-test.log 2>&1
.venv/bin/python tests/smoke.py >> /tmp/meshcrap-test.log 2>&1
printf '\nMESHCRAP_APP_VERIFIED\n' > /dev/ttyS0
EOF
cat > "$work/check-app.service" <<'EOF'
[Unit]
Description=Disposable image verification
After=meshcrap-first-boot.service
[Service]
Type=oneshot
ExecStart=/bin/bash /root/check-app.sh
StandardOutput=null
[Install]
WantedBy=multi-user.target
EOF
for format in qcow2 vhdx vmdk; do
  echo "Testing $format BIOS boot and dashboard"
  disk=$(realpath "dist/vm/meshcrap-amd64.$format")
  overlay="$work/test-$format.qcow2"
  qemu-img compare -f qcow2 -F "$format" "$work/appliance.qcow2" "$disk"
  qemu-img create -f qcow2 -F "$format" -b "$disk" "$overlay"
  virt-customize -a "$overlay" --upload "$work/check-app.sh:/root/check-app.sh" --upload "$work/check-app.service:/etc/systemd/system/check-app.service" --run-command 'systemctl enable check-app.service'
  accel=tcg
  if test -r /dev/kvm && test -w /dev/kvm; then accel=kvm; fi
  # IDE exercises the BIOS/IDE boot path used by Hyper-V Generation 1.
  qemu-system-x86_64 -accel "$accel" -m 2048 -smp 2 -display none -serial "file:$work/boot-$format.log" -drive "file=$overlay,if=ide,format=qcow2" -netdev user,id=n -device e1000,netdev=n -no-reboot &
  boot_pid=$!
  ready=0
  for i in $(seq 1 300); do
    if grep -q MESHCRAP_APP_VERIFIED "$work/boot-$format.log" && grep -q MESHCRAP_FIRST_BOOT_READY "$work/boot-$format.log"; then ready=1; break; fi
    if ! kill -0 "$boot_pid" 2>/dev/null; then break; fi
    sleep 2
  done
  kill "$boot_pid" 2>/dev/null || true
  wait "$boot_pid" 2>/dev/null || true
  if test "$ready" != 1; then
    echo "$format verification failed; console credentials are not printed."
    virt-cat -a "$overlay" /tmp/meshcrap-test.log || true
    exit 1
  fi
  echo "PASS: $format image equivalence, first boot, setup, dashboard and HTTP checks"
done
