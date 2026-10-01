#!/bin/bash
set -euo pipefail
umask 077
echo 'Meshcrap portable session — settings and collected data are temporary.'
echo 'Save any wanted exports to storage you explicitly choose before shutdown.'
echo 'This does not install Meshcrap onto the computer or connect a radio automatically.'
config="$HOME/.config/meshcrap/config.json"
mkdir -p "$(dirname "$config")"
python=/opt/meshcrap/.venv/bin/python
if [ ! -f "$config" ]; then "$python" /opt/meshcrap/meshcrap.py --config "$config" setup; fi
test -f "$config" || exit 0
"$python" /opt/meshcrap/meshcrap.py --config "$config" check
"$python" /opt/meshcrap/meshcrap.py --config "$config" serve &
server=$!
trap 'kill "$server" 2>/dev/null || true' EXIT
port=$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["web_port"])' "$config")
sleep 2
firefox "http://127.0.0.1:$port" >/dev/null 2>&1 &
echo 'Dashboard running. Keep this terminal open; Ctrl+C stops it.'
echo 'Collection is separate: use the documented collect command after configuring a radio.'
wait "$server"
