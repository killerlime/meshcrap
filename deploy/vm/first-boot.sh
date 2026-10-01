#!/bin/bash
set -euo pipefail
marker=/var/lib/meshcrap-first-boot-complete
test ! -f "$marker" || exit 0
password=$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')
printf 'meshcrap:%s\n' "$password" | chpasswd
chage -d 0 meshcrap
for console in /dev/tty1 /dev/ttyS0; do
  printf '\nMeshcrap appliance is ready.\nConsole user: meshcrap\nTemporary password: %s\nChange it at login, then run: sudo meshcrap-setup\nNo network login or dashboard is enabled yet.\nMESHCRAP_FIRST_BOOT_READY\n' "$password" > "$console" 2>/dev/null || true
done
unset password
touch "$marker"
