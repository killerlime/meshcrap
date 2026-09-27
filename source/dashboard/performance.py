"""Bounded short-lived cache for read-only analytics; controls never cached."""
import gzip
from collections import OrderedDict
from threading import Lock
from time import monotonic
from flask import g, request, make_response

PATHS = {'/api/summary','/api/map','/api/noc','/api/history','/api/node',
         '/api/telemetry-history','/api/rf-environment','/api/rf-health-hourly'}

def register_performance(app):
    cache=OrderedDict()
    lock=Lock()
    generation=0
    total_bytes=0

    # Registered before the cache hook: Flask runs response hooks in reverse,
    # so the cache always stores the original uncompressed representation.
    @app.after_request
    def compress_read_response(response):
        safe = request.path in PATHS | {'/','/api/coverage','/api/coverage-survey'} or (
            request.path.startswith('/static/') and request.path.endswith(('.js','.css')))
        if not safe or request.method != 'GET':
            return response
        response.vary.add('Accept-Encoding')
        if response.status_code != 200 or response.headers.get('Content-Encoding') or 'Range' in request.headers or request.accept_encodings['gzip'] <= 0:
            return response
        response.direct_passthrough = False
        body = response.get_data()
        if len(body) < 1024:
            return response
        packed = gzip.compress(body,compresslevel=4,mtime=0)
        if len(packed) >= len(body):
            return response
        response.set_data(packed)
        response.headers['Content-Encoding'] = 'gzip'
        etag = response.get_etag()[0]
        if etag:
            response.set_etag(etag,weak=True)
        return response

    @app.before_request
    def cached_analytics():
        if request.method!='GET' or request.path not in PATHS:
            return
        key=(request.path,tuple(sorted(request.args.items(multi=True))))
        with lock:
            g.analytics_cache=(key,generation)
            item=cache.get(key)
            if item and monotonic()-item[0]<5:
                cache.move_to_end(key)
                response=make_response(item[1])
                response.content_type='application/json'
                response.headers['Cache-Control']='no-store'
                response.headers['X-Analytics-Cache']='hit'
                return response

    @app.after_request
    def store_analytics(response):
        nonlocal generation,total_bytes
        if request.method not in ('GET','HEAD','OPTIONS') and response.status_code<400:
            with lock:
                cache.clear();total_bytes=0;generation+=1
        context=getattr(g,'analytics_cache',None)
        if context and response.status_code==200 and response.is_json and not response.headers.get('X-Analytics-Cache'):
            key,observed=context
            body=response.get_data()
            response.headers['Cache-Control']='no-store'
            response.headers['X-Analytics-Cache']='miss'
            if len(body)<=1_000_000:
                with lock:
                    if observed==generation:
                        old=cache.pop(key,None)
                        if old:total_bytes-=len(old[1])
                        cache[key]=(monotonic(),body);total_bytes+=len(body)
                        while len(cache)>128 or total_bytes>8_000_000:
                            _,old=cache.popitem(last=False);total_bytes-=len(old[1])
        return response

    @app.teardown_request
    def close_connections(error):
        for conn in g.pop('database_connections',[]):
            conn.close()
