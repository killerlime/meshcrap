"""Bounded API timings without URLs, query arguments, bodies or credentials."""
from collections import defaultdict, deque
import os
import threading
import time


def register_performance(app):
    from flask import g, jsonify, request
    records=defaultdict(lambda:deque(maxlen=128));lock=threading.Lock()
    @app.before_request
    def start():g.performance_start=time.monotonic()
    @app.after_request
    def finish(response):
        if request.path.startswith('/api/') and request.endpoint and request.endpoint!='explorer_performance':
            # Do not drain a streaming response merely to measure its size.
            size=response.content_length if response.is_streamed else response.calculate_content_length()
            with lock:
                records[request.endpoint].append((round((time.monotonic()-getattr(g,'performance_start',time.monotonic()))*1000,2),response.status_code,size))
        return response
    @app.get('/api/explorer/performance')
    def explorer_performance():
        rss=None
        try:
            with open('/proc/self/statm') as f:rss=int(f.read().split()[1])*os.sysconf('SC_PAGE_SIZE')
        except (OSError,ValueError,AttributeError):pass
        rows=[]
        with lock:
            for name,values in records.items():
                times=sorted(v[0] for v in values);n=len(times)
                rows.append(dict(endpoint=name,samples=n,p50_ms=times[n//2],p95_ms=times[min(n-1,int(n*.95))],max_ms=times[-1],latest_bytes=values[-1][2],unchanged=sum(v[1]==304 for v in values),errors=sum(v[1]>=500 for v in values)))
        response=jsonify(endpoints=rows,resident_bytes=rss,scope='Last 128 requests per endpoint in this process; timings include response construction, not network delivery.')
        response.headers['Cache-Control']='no-store'
        return response
