"""First heard must use radio evidence, never metadata or cached history."""
import ast, sqlite3
from pathlib import Path
source=(Path(__file__).resolve().parents[1]/'source/dashboard/app.py').read_text()
tree=ast.parse(source[source.index('def first_radio_heard('):source.index('@app.route("/api/telemetry")')])
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='first_radio_heard')
namespace={};exec(compile(ast.Module(body=[function],type_ignores=[]),'first_heard','exec'),namespace)
c=sqlite3.connect(':memory:')
c.execute('CREATE TABLE packets(from_num,from_id,collector_time,observation_type,transport,rx_snr,rx_rssi,raw_json)')
rows=[(1,'!00000001','2025-01-01','NODE_DB','',2,-90,'{}'),(1,'!00000001','2025-01-02','LIVE','TRANSPORT_MQTT',2,-90,'{}'),(1,'!00000001','2025-01-03','LIVE','',2,-90,'{"viaMqtt":true}'),(1,'!00000001','2025-01-04','LIVE','',None,None,'{}'),(1,'!00000001','2025-01-05','LIVE','',2,-90,'{"_collectorReceiverId":"!00000001"}'),(1,'!00000001','2025-01-06','LIVE','',2,-90,'{}'),(1,'!00000001','2025-01-07','LIVE','',3,-88,'{}')]
c.executemany('INSERT INTO packets VALUES (?,?,?,?,?,?,?,?)',rows)
assert namespace['first_radio_heard'](c,1)=='2025-01-06'
assert namespace['first_radio_heard'](c,2) is None
print('PASS: first heard uses earliest retained RF receipt; snapshots, MQTT, self updates and metadata excluded')
