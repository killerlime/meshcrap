"""Short, process-local health cache; authorization still runs on every request."""
from functools import wraps
from threading import Lock
from time import monotonic
from flask import make_response


def shared_health_check(seconds=5):
    def decorate(function):
        lock = Lock()
        saved = None
        expires = 0

        @wraps(function)
        def wrapped(*args, **kwargs):
            nonlocal saved, expires
            with lock:
                if saved is None or monotonic() >= expires:
                    response = make_response(function(*args, **kwargs))
                    if response.status_code != 200:
                        return response
                    saved = (response.get_data(), response.status_code, response.content_type)
                    expires = monotonic() + seconds
                body, status, content_type = saved
                # A fresh response avoids sharing mutable headers across requests.
                return make_response((body, status, {'Content-Type': content_type}))
        return wrapped
    return decorate
