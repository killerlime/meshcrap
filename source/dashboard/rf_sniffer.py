"""Optional browser presentation of an independently operated RF receiver.

This module never contacts a backend, opens an SDR, reads captures or keys, or
shares the collector database. The installation's reverse proxy owns access to
the separate receiver, including authentication for its control endpoints.
"""
import re
import ipaddress
from urllib.parse import urlsplit


def validate_embed_url(value):
    """Dedicated same-origin path or operator-owned HTTPS page; no fetcher."""
    message = 'rf_sniffer_url must be a dedicated /sniffer/ path or an HTTPS URL without credentials, queries or fragments'
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError(message)
    if value == '' or re.fullmatch(r'/(?:sniffer|rf-sniffer)(?:-[a-z0-9]{1,24})?/', value):
        return value
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or not url.hostname or url.username is not None or url.password is not None
                or url.query or url.fragment or url.port is not None and not 1 <= url.port <= 65535
                or not re.fullmatch(r'(?:/[A-Za-z0-9_-]+)*/?', url.path)
                or '?' in value or '#' in value or '%' in value or '\\' in value
                or any(ord(c) < 33 or ord(c) > 126 for c in value)):
            raise ValueError(message)
        if not re.fullmatch(r'(?:\[[0-9a-fA-F:]+\]|[A-Za-z0-9][A-Za-z0-9.-]*)(?::[0-9]{1,5})?', url.netloc):
            raise ValueError(message)
        hostname = url.hostname
        if ':' in hostname:
            ipaddress.IPv6Address(hostname)
        elif not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', hostname):
            raise ValueError(message)
        expected = 'https://' + url.netloc + url.path
        if value != expected:
            raise ValueError(message)
        return value
    except (TypeError, ValueError):
        raise ValueError(message) from None


def register_rf_sniffer(app, enabled=False, url=''):
    from flask import jsonify
    if type(enabled) is not bool:
        raise ValueError('rf_sniffer_enabled must be boolean')
    url = validate_embed_url(url)
    if enabled and not url:
        raise ValueError('Set rf_sniffer_url before enabling the RF sniffer view')

    @app.get('/api/rf-sniffer/integration')
    def rf_sniffer_integration():
        response = jsonify(enabled=enabled, url=url if enabled else None,
                           separate=True, setup_command='python meshcrap.py sniffer-setup')
        response.headers['Cache-Control'] = 'no-store'
        return response

    def rf_sniffer_frame_policy(response):
        # Frame exactly the configured trusted HTTPS origin; do not open this
        # policy to all HTTPS sites. No server-side connection is made.
        policy = response.headers.get('Content-Security-Policy', '')
        if 'frame-src' not in policy:
            sources = "'self'"
            if enabled and url.startswith('https://'):
                parsed = urlsplit(url)
                sources += ' https://' + parsed.netloc
            response.headers['Content-Security-Policy'] = policy.rstrip('; ') + ('; ' if policy else '') + 'frame-src ' + sources
        return response
    # Flask executes response hooks in reverse registration order. Run after
    # the dashboard's security headers so this narrow policy is retained.
    app.after_request_funcs.setdefault(None, []).insert(0, rf_sniffer_frame_policy)
