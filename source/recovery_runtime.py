"""Bounded connection and service supervision helpers; never replay radio actions."""
import os
import socket
import time


def watchdog():
    address = os.environ.get('NOTIFY_SOCKET')
    if not address:
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.settimeout(1)
            client.connect('\0'+address[1:] if address.startswith('@') else address)
            client.sendall(b'WATCHDOG=1')
    except OSError:
        pass


def recovery_sleep(seconds):
    deadline = time.monotonic() + seconds
    while True:
        watchdog()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(5, remaining))


def configure_socket(sock):
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    for name,value in [('TCP_KEEPIDLE',45),('TCP_KEEPINTVL',10),('TCP_KEEPCNT',3),('TCP_USER_TIMEOUT',90000)]:
        option=getattr(socket,name,None)
        if option is not None:
            sock.setsockopt(socket.IPPROTO_TCP,option,value)


def start_dashboard_watchdog():
    if not os.environ.get('NOTIFY_SOCKET'):
        return
    import threading
    import urllib.request
    def monitor():
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while True:
            try:
                with opener.open('http://127.0.0.1:8080/api/recovery-health',timeout=5) as response:
                    if response.status==200 and response.read(128)==b'ok':
                        watchdog()
            except (OSError,ValueError):
                pass
            time.sleep(15)
    threading.Thread(target=monitor,name='dashboard-watchdog',daemon=True).start()
