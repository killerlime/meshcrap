"""Filtering node evidence must not filter receiver coverage or health stats."""
import ast, json, sqlite3, sys, tempfile, types
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify

root = Path(__file__).resolve().parents[1]
source = (root/'source/dashboard/app.py').read_text(encoding='utf-8')
section = source[source.index('@app.route("/api/rf-health-hourly")'):source.index('@app.route("/api/self-test")')]
gap_source = (root/'source/dashboard/lna_experiment.py').read_text(encoding='utf-8')
gap = next(n for n in ast.parse(gap_source).body if isinstance(n, ast.FunctionDef) and n.name == 'gap_hours')
module = types.ModuleType('lna_experiment')
module.__dict__['timedelta'] = timedelta
exec(compile(ast.Module(body=[gap], type_ignores=[]), 'gap_hours', 'exec'), module.__dict__)
sys.modules['lna_experiment'] = module

with tempfile.TemporaryDirectory() as directory:
    base = Path(directory); database = base/'mesh.db'
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)-timedelta(hours=2)
    (base/'reports').mkdir()
    (base/'reports/lna-experiment.json').write_text(json.dumps(dict(start_utc=start.isoformat(),
        transitions=[dict(time_utc=start.isoformat(), state='OFF')], fixed_setup={})), encoding='utf-8')
    conn = sqlite3.connect(database)
    conn.executescript('''CREATE TABLE nodes(node_num, role, long_name, short_name);
        CREATE TABLE packets(collector_time,from_id,from_num,portnum,rx_snr,rx_rssi,hops_used,raw_json,observation_type);
        CREATE TABLE collector_events(event_time,event_type);''')
    conn.executemany('INSERT INTO nodes VALUES (?,?,?,?)', [(1,'CLIENT','Example One','EX1'),(2,'CLIENT_MUTE','Other','OT'),(3,None,'Unknown','EX3')])
    for minute in range(60):
        stats = dict(numPacketsRx=minute*2,numPacketsRxBad=minute,channelUtilization=12,airUtilTx=2)
        conn.execute('INSERT INTO packets VALUES (?,?,?,?,?,?,?,?,?)', ((start+timedelta(minutes=minute)).isoformat(),
            '@@RECEIVER_ID@@',99,'TELEMETRY_APP',None,None,0,json.dumps({'decoded':{'telemetry':{'localStats':stats}}}),'LIVE'))
    for num in (1,2,3,4):
        conn.execute('INSERT INTO packets VALUES (?,?,?,?,?,?,?,?,?)', ((start+timedelta(minutes=30)).isoformat(),
            f'!{num:08x}',num,'TEXT_MESSAGE_APP',5,-90,0 if num==1 else 1,'{}','LIVE'))
    conn.commit();conn.close()
    def db():
        connection=sqlite3.connect(database);connection.row_factory=sqlite3.Row;return connection
    app=Flask(__name__)
    namespace=dict(app=app,request=request,jsonify=jsonify,DB=database,db=db)
    function=next(n for n in ast.parse(section.replace('@@NODE_PREFIX_LOWER@@','ex')).body if isinstance(n,ast.FunctionDef) and n.name=='rf_health_hourly')
    exec(compile(ast.Module(body=[function],type_ignores=[]),'rf_health_hourly','exec'),namespace)
    client=app.test_client()
    def get(query=''):
        response=client.get('/api/rf-health-hourly?hours=3'+query);assert response.status_code==200
        return next(r for r in response.json['timeline'] if r['hour']==start.isoformat())
    all_nodes=get();assert all_nodes['unique_nodes']==4 and all_nodes['direct_nodes']==1
    assert get('&device_mode=CLIENT')['unique_nodes']==1
    assert get('&device_mode=CLIENT_MUTE')['unique_nodes']==1
    assert get('&device_mode=UNKNOWN')['unique_nodes']==2
    assert get('&node_group=only_local')['unique_nodes']==2
    assert get('&node_group=exclude_local')['unique_nodes']==2
    combined=get('&node_group=only_local&device_mode=CLIENT_MUTE');assert combined['unique_nodes']==0
    for query in ('&node_group=only_local','&device_mode=CLIENT','&node_group=only_local&device_mode=CLIENT_MUTE'):
        row=get(query)
        for key in ('observed_minutes','channel_utilization','air_util_tx','rx_bad_share_pct'):
            assert row[key]==all_nodes[key], key
    assert client.get('/api/rf-health-hourly?device_mode=CLIENT%27').status_code==400
    assert client.get('/api/rf-health-hourly?node_group=bogus').status_code==400
print('PASS: device-mode and local-prefix filters compose; unknown nodes and receiver-wide observation/health data remain correct')
