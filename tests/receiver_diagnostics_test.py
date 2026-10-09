import sys
import base64
import json
import subprocess
import tempfile
import unittest
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]/'source'
sys.path[:0]=[str(ROOT),str(ROOT/'dashboard')]
import receiver_log_reader as reader
import receiver_diagnostics as diagnostics
import debug_logs
from flask import Flask

BASE_US=int(datetime.now(timezone.utc).timestamp()*1e6)-1000000

def row(i,message,priority='6'):
    return {'us':BASE_US+i, '__CURSOR':'s=abc;i='+str(i), 'message':message,'PRIORITY':priority}

class DiagnosticsTests(unittest.TestCase):
    def saved_connection(self,folder):
        root=Path(folder);identity=root/'reader-key';known=root/'reader-known-hosts'
        identity.write_text('synthetic restricted key');known.write_text('synthetic pinned host')
        return dict(host='receiver.example',user='meshcrap',identity=str(identity),known_hosts=str(known))

    def test_remote_request_is_fixed_protocol_not_a_command(self):
        cursor='s=abc;i=10;b=1234'
        request=dict(action='logs',window='day',level='warning',limit=100,before=cursor)
        encoded=diagnostics.journal_command(request)
        self.assertRegex(encoded,r'^journal-read:[A-Za-z0-9_-]+={0,2}$')
        self.assertEqual(json.loads(base64.urlsafe_b64decode(encoded.split(':',1)[1])),request)
        for invalid in [dict(action='restart'),dict(action='summary',unit='other.service'),
                        dict(action='logs',window='day',level='all',limit=100,before='; touch /tmp/bad'),
                        dict(action='logs',window='day',level='all',limit=True),
                        dict(action='logs',window='day',level='all',limit=100,before='x'*1025)]:
            with self.subTest(request=invalid),patch.object(diagnostics.subprocess,'run') as run:
                with self.assertRaises(RuntimeError):diagnostics.remote_read('/missing',invalid)
                run.assert_not_called()

    def test_ssh_options_are_fixed_and_host_arguments_terminated(self):
        with tempfile.TemporaryDirectory() as folder:
            config=self.saved_connection(folder)
            (Path(folder)/'receiver-log-access.json').write_text(json.dumps(config))
            result=subprocess.CompletedProcess([],0,stdout='{"counts":{}}',stderr='')
            with patch.object(diagnostics.subprocess,'run',return_value=result) as run:
                self.assertEqual(diagnostics.remote_read(folder,{'action':'summary'}),{'counts':{}})
            command=run.call_args.args[0]
            self.assertEqual(command[:4],['ssh','-F','/dev/null','-T'])
            self.assertEqual(command[-3:-1],['--','receiver.example'])
            self.assertIn('-oStrictHostKeyChecking=yes',command)
            self.assertIn('-oIdentitiesOnly=yes',command)
            self.assertEqual(run.call_args.kwargs['timeout'],18)
            self.assertNotIn('shell',run.call_args.kwargs)
            config['host']='::1'
            self.assertEqual(diagnostics.ssh_connection(config)[0],'::1')

    def test_saved_connection_cannot_inject_ssh_options(self):
        with tempfile.TemporaryDirectory() as folder:
            config=self.saved_connection(folder);settings=Path(folder)/'receiver-log-access.json'
            attacks=[('host','-oProxyCommand=touch /tmp/bad'),('host','receiver.example;bad'),
                     ('host','receiver.example\nProxyCommand=bad'),('user','-oProxyCommand=bad'),
                     ('identity','relative-key'),('known_hosts','/tmp/known%h'),
                     ('known_hosts',str(Path(folder)/'not-present'))]
            for field,value in attacks:
                bad=dict(config);bad[field]=value;settings.write_text(json.dumps(bad))
                with self.subTest(field=field,value=value),patch.object(diagnostics.subprocess,'run') as run:
                    with self.assertRaises(RuntimeError):diagnostics.remote_read(folder,{'action':'summary'})
                    run.assert_not_called()

    def test_summary_separates_causes_and_excludes_private_data(self):
        data=reader.summary([row(1,'ERROR | 1 [RadioIf] Ignore rx packet, error=-7 (fr=0x12345678)'),row(2,"ERROR | 1 [Router] Can't decode protobuf reason='wire'"),row(3,'Node database full: 200 nodes, 100 bytes free. Erase oldest'),row(4,'Client dropped connection'),row(5,'Disconnect from phone')])
        self.assertEqual(data['counts']['crc_errors'],1)
        self.assertEqual(data['counts']['client_disconnects'],1)
        self.assertEqual(data['capacity_at_last_eviction'],200)
        self.assertNotIn('12345678',str(data))
        self.assertEqual(reader.summary([])['counts'],{})
    def test_embedded_error_level(self):
        self.assertEqual(reader.severity(row(1,'\x1b[31mERROR | 1 [RadioIf] bad')), '3')
        self.assertEqual(reader.severity(row(2,'WARN | message')), '4')
    def test_cursor_no_duplicate_and_empty_warning_page_advances(self):
        rows=[row(i,'INFO | quiet') for i in range(101,0,-1)]
        with patch.object(reader,'records',return_value=rows) as read:
            data=reader.handle(dict(action='logs',window='day',level='warning',limit=100,before='s=abc;i=101'))
        self.assertFalse(any(a.startswith('--since') for a in read.call_args.args[0]))
        self.assertEqual(data['entries'],[])
        self.assertEqual(data['next_cursor'],'s=abc;i=1')
        with patch.object(reader,'records',return_value=rows[:3]):
            data=reader.handle(dict(action='logs',window='day',level='all',limit=100,before='s=abc;i=101'))
        self.assertEqual(len(data['entries']),2)
        self.assertLess(data['entries'][0]['time'],data['entries'][1]['time'])
    def test_invalid_requests_never_run_journal(self):
        with patch.object(reader,'records') as read:
            for r in [dict(action='restart'),dict(action='logs',window='day',level='all',limit=999),dict(action='logs',window='day',level='all',limit=100,before='; touch /tmp/bad')]:
                with self.assertRaises(ValueError): reader.handle(r)
            read.assert_not_called()
    def test_redaction(self):
        self.assertNotIn('private123',reader.scrub('password=private123 psk=private123'))
    def test_connection_history_no_private_messages(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'mesh.db';db=sqlite3.connect(p);db.execute('CREATE TABLE collector_events(event_id INTEGER PRIMARY KEY,event_time TEXT,event_type TEXT,message TEXT)')
            now=datetime.now(timezone.utc)
            db.executemany('INSERT INTO collector_events VALUES(?,?,?,?)',[(1,now.isoformat(),'CONNECTION_ERROR',"No route to host private-ip"),(2,now.isoformat(),'CONNECTED','private-id')]);db.commit();db.close()
            data=diagnostics.connection_summary(p,now)
            self.assertEqual(data['no_route_48h'],1);self.assertEqual(data['last_event']['type'],'CONNECTED');self.assertNotIn('private',str(data))
    def test_existing_endpoint_validation_and_remote_failure(self):
        app=Flask(__name__);debug_logs.register_debug_logs(app,Path('/missing'))
        client=app.test_client()
        self.assertEqual(client.get('/api/debug-logs?service=arbitrary').status_code,400)
        with patch.object(diagnostics,'remote_read',side_effect=RuntimeError('private info')):
            response=client.get('/api/debug-logs?service=receiver')
            self.assertEqual(response.status_code,503);self.assertNotIn('private info',response.get_data(as_text=True));self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_summary_cache_and_unknown_on_failure(self):
        app=Flask(__name__);diagnostics.register_receiver_diagnostics(app,Path('/missing/mesh.db'))
        with patch.object(diagnostics,'remote_read',side_effect=RuntimeError('offline')) as read:
            a=app.test_client().get('/api/receiver-diagnostics').get_json();app.test_client().get('/api/receiver-diagnostics')
            self.assertIsNone(a['radio']);self.assertTrue(a['stale']);self.assertEqual(read.call_count,1)

if __name__=='__main__':unittest.main()
