"""Explicit, backed-up removal of a node's local collector records."""
import json,re,secrets,sqlite3,time
from contextlib import closing
from pathlib import Path
from flask import jsonify,request,session

def node_number(value):
    if not isinstance(value,str) or not re.fullmatch(r'![0-9a-fA-F]{8}',value):
        raise ValueError('Choose a canonical node ID such as !00000000')
    num=int(value[1:],16)
    if not 3<num<0xffffffff:raise ValueError('Choose a valid node ID')
    return num

def attach_feed(c,database):
    path=Path(database).parent/'potato-feed'/'outbox.db'
    if path.exists():c.execute('ATTACH DATABASE ? AS feed',(str(path),))

def plan(c,num):
    ident=f'!{num:08x}'
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    result={}
    direct={'nodes':['node_num'],'node_notes':['node_num'],'node_reappearance_guards':['node_num'],
            'node_metadata_backfills':['node_num'],'node_metadata_refreshes':['node_num'],
            'pki_jobs':['node_num'],'pki_samples':['node_num'],'pki_schedule':['node_num'],
            'web_sent_messages':['sender_num','destination_num'],'packets':['from_num','to_num']}
    for table,cols in direct.items():
        if table in tables:
            result[table]={r[0] for r in c.execute('SELECT rowid FROM '+table+' WHERE '+' OR '.join(k+'=?' for k in cols),[num]*len(cols))}
    for table in ('external_node_snapshots','furthest_direct_history','furthest_reached_history'):
        if table in tables:result[table]={r[0] for r in c.execute('SELECT rowid FROM '+table+' WHERE lower(node_id)=?',(ident,))}
    # Include traceroutes, neighbors and other stored payloads referencing this node.
    def references(v):
        if isinstance(v,dict):return any(references(k) or references(x) for k,x in v.items())
        if isinstance(v,list):return any(references(x) for x in v)
        return type(v) is int and v==num or isinstance(v,str) and v.lower() in (ident,str(num))
    for table,column in (('packets','raw_json'),('pki_samples','payload_json'),('external_node_snapshots','raw_json')):
        if table not in tables:continue
        for rowid,raw in c.execute(f'SELECT rowid,{column} FROM {table}'):
            try:hit=references(json.loads(raw))
            except (ValueError,TypeError):hit=False
            if hit:result.setdefault(table,set()).add(rowid)
    if any(r[1]=='feed' for r in c.execute('PRAGMA database_list')):
        feed_tables={r[0] for r in c.execute("SELECT name FROM feed.sqlite_master WHERE type='table'")}
        for table in ('queue','quarantined_before_primary_swap'):
            if table not in feed_tables:continue
            result['feed.'+table]=set()
            for rowid,sender,raw in c.execute('SELECT rowid,sender,payload FROM feed.'+table):
                try:hit=sender.lower()==ident or references(json.loads(raw))
                except (ValueError,TypeError,AttributeError):hit=False
                if hit:result['feed.'+table].add(rowid)
    if 'collector_events' in tables:
        pattern=re.compile(r'(?<![\w])(?:'+re.escape(ident)+'|'+str(num)+r')(?![\w])',re.I)
        result['collector_events']={r for r,m in c.execute('SELECT rowid,message FROM collector_events') if pattern.search(m or '')}
    # Site setup is not history: detach its name association, preserve the site.
    node=c.execute('SELECT long_name FROM nodes WHERE node_num=?',(num,)).fetchone()
    sites=[]
    if node and node[0] and 'sites' in tables:
        sites=[r[0] for r in c.execute('SELECT rowid FROM sites WHERE node_long_name=?',(node[0],))]
    return result,sites

def purge(database,num,request_token=None):
    root=Path(database).parent
    backup=root/'backups'/('node-purge-'+str(time.time_ns()));backup.mkdir(parents=True,mode=0o700)
    with closing(sqlite3.connect(database,timeout=15)) as c:
        attach_feed(c,database)
        c.execute('BEGIN IMMEDIATE')
        try:
            c.execute('CREATE TABLE IF NOT EXISTS node_purge_requests(token TEXT PRIMARY KEY,completed_at REAL NOT NULL)')
            if request_token and c.execute('SELECT 1 FROM node_purge_requests WHERE token=?',(request_token,)).fetchone():raise ValueError('This purge was already performed; preview again')
            if not c.execute('SELECT 1 FROM nodes WHERE node_num=?',(num,)).fetchone():raise ValueError('Node no longer exists; refresh the list')
            with closing(sqlite3.connect(database,timeout=15)) as source, closing(sqlite3.connect(backup/'mesh.db')) as dest:source.backup(dest)
            feed=root/'potato-feed'/'outbox.db'
            if feed.exists():
                with closing(sqlite3.connect(feed,timeout=15)) as source, closing(sqlite3.connect(backup/'outbox.db')) as dest:source.backup(dest)
            rows,sites=plan(c,num)
            for table,ids in rows.items():c.executemany('DELETE FROM '+table+' WHERE rowid=?',[(i,) for i in ids])
            c.executemany('UPDATE sites SET node_long_name=NULL WHERE rowid=?',[(i,) for i in sites])
            if request_token:c.execute('INSERT INTO node_purge_requests VALUES(?,?)',(request_token,time.time()))
            assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok'
            if feed.exists():assert c.execute('PRAGMA feed.quick_check').fetchone()[0]=='ok'
            c.commit()
        except:
            c.rollback();raise
    return {'deleted':{t:len(ids) for t,ids in rows.items() if ids},'sites_detached':len(sites),'backup':str(backup)}

def register_utilities(app,database):
    @app.get('/api/utilities/nodes')
    def utility_nodes():
        with closing(sqlite3.connect(database)) as c:
            rows=c.execute('SELECT node_num,long_name,short_name FROM nodes ORDER BY lower(coalesce(long_name,short_name,""))').fetchall()
        return jsonify(nodes=[dict(id=f'!{n:08x}',name=long or short or f'!{n:08x}') for n,long,short in rows])

    @app.post('/api/utilities/purge-preview')
    def preview():
        try:
            num=node_number(request.json.get('node_id'))
            with closing(sqlite3.connect(database)) as c:
                attach_feed(c,database)
                if not c.execute('SELECT 1 FROM nodes WHERE node_num=?',(num,)).fetchone():raise ValueError('Node no longer exists')
                rows,sites=plan(c,num)
            token=secrets.token_hex(24);session['node_purge']={'num':num,'token':token,'expires':time.time()+600}
            return jsonify(token=token,counts={k:len(v) for k,v in rows.items() if v},sites_detached=len(sites))
        except ValueError as e:return jsonify(error=str(e)),400

    @app.post('/api/utilities/purge-node')
    def remove():
        try:
            num=node_number(request.json.get('node_id'));pending=session.get('node_purge') or {}
            if pending.get('num')!=num or pending.get('expires',0)<time.time() or not secrets.compare_digest(str(pending.get('token','')),str(request.json.get('token',''))):raise ValueError('Preview this node again before deleting')
            if request.json.get('confirmation')!=f'!{num:08x}':raise ValueError('Type the exact node ID to confirm')
            session.pop('node_purge',None)
            result=purge(database,num,pending['token'])
            return jsonify(**result,message='Node and its local collector history purged. It may reappear when observed again.')
        except ValueError as e:return jsonify(error=str(e)),400
        except sqlite3.Error:return jsonify(error='Database busy or unavailable. Refresh and preview again.'),503
