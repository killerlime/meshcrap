#!/bin/sh
set -eu
grep -qw toram /proc/cmdline
test "$(findmnt -n -o FSTYPE /)" = overlay
test -z "$(swapon --show --noheadings)"
cd /opt/meshcrap
.venv/bin/python tests/smoke.py
.venv/bin/python tests/efficiency.py
.venv/bin/python tests/setup_labels.py
echo MESHCRAP_LIVE_VERIFIED
