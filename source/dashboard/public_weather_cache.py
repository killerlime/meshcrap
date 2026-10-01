"""Opt-in, bounded NWS JSON fetches. No polling threads or dashboard imports.

Call from a separate worker. Cache hits perform no HTTP request; failures keep
the last good result and delay the next attempt. URLs are operator configuration.
"""
from contextlib import closing
import hashlib
import math
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

LIMIT = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def validate_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'api.weather.gov' or
        parsed.username or parsed.password or parsed.fragment or
        not parsed.path.startswith(('/points/', '/gridpoints/', '/stations/', '/alerts'))):
        raise ValueError('Only supported HTTPS api.weather.gov resources are allowed')
    if len(url) > 2048 or any(ord(c) < 32 for c in url):
        raise ValueError('Invalid URL')


def fetch(url, cache_path, ttl=900, now=None, opener=None):
    # NWS redirects this convenience path; request its canonical equivalent once.
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == 'https' and parsed.netloc == 'api.weather.gov' and parsed.path == '/alerts/active':
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query = [('active', 'true')] + [(k,v) for k,v in query if k != 'active']
        url = urllib.parse.urlunsplit(parsed._replace(path='/alerts', query=urllib.parse.urlencode(query)))
    validate_url(url)
    if type(ttl) is not int or not 300 <= ttl <= 86400:
        raise ValueError('Cache interval must be 5 minutes to 24 hours')
    now = time.time() if now is None else now
    if type(now) not in (int, float) or not math.isfinite(now):
        raise ValueError('Invalid cache time')
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(url.encode()).hexdigest()
    with closing(sqlite3.connect(cache_path, timeout=3)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, body TEXT, etag TEXT, modified TEXT, checked REAL, due REAL, failures INTEGER, error TEXT)')
        cache_path.chmod(0o600)
        # A short transaction serializes workers so simultaneous calls cannot duplicate a fetch.
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT body,etag,modified,checked,due,failures,error FROM cache WHERE key=?',(key,)).fetchone()
        if row and now < row[4]:
            return dict(data=json.loads(row[0]) if row[0] else None, cached=True,
                        last_checked=row[3], stale=bool(row[6]), error=row[6], next_attempt=row[4])
        headers={'User-Agent':'Meshcrap/0.1 (https://github.com/killerlime/meshcrap)',
                 'Accept':'application/geo+json, application/json', 'Accept-Encoding':'identity'}
        if row and row[1]:headers['If-None-Match']=row[1]
        if row and row[2]:headers['If-Modified-Since']=row[2]
        body, etag, modified, checked = (row[:4] if row else (None,None,None,None))
        error=None;failures=0;due=now+ttl;retry_after=0
        try:
            client=opener or urllib.request.build_opener(NoRedirect())
            with client.open(urllib.request.Request(url,headers=headers),timeout=10) as response:
                raw=response.read(LIMIT+1)
                if len(raw)>LIMIT:raise ValueError('Response limit exceeded')
                value=json.loads(raw)
                if not isinstance(value,dict):raise ValueError('Expected JSON object')
                body=json.dumps(value,allow_nan=False,separators=(',',':'))
                etag=response.headers.get('ETag');modified=response.headers.get('Last-Modified');checked=now
        except urllib.error.HTTPError as exc:
            if exc.code==304 and body is not None:checked=now
            else:
                error='HTTP '+str(exc.code)
                value=exc.headers.get('Retry-After','') if exc.headers else ''
                try:
                    retry_after=float(value) if value.isdigit() else parsedate_to_datetime(value).timestamp()-now
                    if not math.isfinite(retry_after):retry_after=0
                except (ValueError, TypeError, OverflowError):retry_after=0
        except (OSError, ValueError) as exc:
            error=type(exc).__name__  # Do not expose URLs or response bodies in logs.
        if error:
            failures=min(8,(row[5] if row else 0)+1)
            due=now+max(min(86400,ttl*(2**failures)),max(0,retry_after))
        db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?,?,?,?)',
                   (key,body,etag,modified,checked,due,failures,error))
        # Fixed storage ceiling: at most 32 configured resources (2 MiB each).
        db.execute('DELETE FROM cache WHERE key NOT IN (SELECT key FROM cache ORDER BY due DESC LIMIT 32)')
        db.commit()
        return dict(data=json.loads(body) if body else None,cached=False,last_checked=checked,
                    stale=bool(error),error=error,next_attempt=due)
