"""Local IPC only: secondary controls reuse its collector-owned connection."""
import json
import socket
from pathlib import Path

SOCKET = Path('@@DATA_DIR@@') / '.secondary-control.sock'


def dispatch(body, socket_path=SOCKET):
    if not isinstance(body, dict):
        raise ValueError('Invalid secondary control request')
    payload = json.dumps(body).encode() + b'\n'
    if len(payload) > 65536:
        raise ValueError('Secondary control request is too large')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(12)
        client.connect(str(socket_path))
        client.sendall(payload)
        with client.makefile('rb') as stream:
            line = stream.readline(2_000_001)
    if len(line) > 2_000_000:
        raise ValueError('Secondary control response is too large')
    result = json.loads(line)
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise ValueError('Secondary action failed; refresh before trying again')
    return result.get('data', {})
