import importlib.util,json,sqlite3,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('messages_view',Path(__file__).resolve().parents[1]/'source/dashboard/messages_view.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as directory:
    database=Path(directory)/'mesh.db';conn=sqlite3.connect(database)
    conn.execute('CREATE TABLE packets(row_id INTEGER PRIMARY KEY,channel,portnum,to_num,raw_json)')
    for channel,port,to,raw in [(None,'TEXT_MESSAGE_APP',4294967295,json.dumps({'decoded':{'text':'Example'}})),(1,'TEXT_MESSAGE_APP',4294967295,json.dumps({'decoded':{'payload':'4869'}})),(1,'TEXT_MESSAGE_APP',4294967295,'invalid'),(0,'NODEINFO_APP',4294967295,'{}'),(0,'TEXT_MESSAGE_APP',123,json.dumps({'decoded':{'text':'Direct message'}}))]:
        conn.execute('INSERT INTO packets(channel,portnum,to_num,raw_json) VALUES (?,?,?,?)',(channel,port,to,raw))
    conn.commit();conn.close()
    assert module.message_heads(database,['0','1','2'])=={'0':1,'1':2,'2':0}
    assert module.message_text('{"decoded":{"text":""}}') is None
    assert module.message_text('{"decoded":{"payload":"not hex"}}') is None
print('PASS: unread heads cover configured broadcast channels, slot zero, payload text; skip malformed and direct messages')
