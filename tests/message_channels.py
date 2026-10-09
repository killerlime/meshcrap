"""Stored channel slots stay literal; replying does not depend on a feed."""
import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import meshcrap

with tempfile.TemporaryDirectory() as folder:
    config = json.loads((ROOT / 'config.example.json').read_text())
    config['data_dir'] = str(Path(folder) / 'data')
    config['receiver_id'] = '!12345678'
    path = Path(folder) / 'config.json'
    path.write_text(json.dumps(config), encoding='utf-8')
    settings, data = meshcrap.load_config(path)
    runtime = meshcrap.initialize(settings, data)
    sys.path[:0] = [str(runtime), str(runtime / 'dashboard')]
    import sent_messages
    import node_control_bridge
    for channel in (0, 1, 2, 3, 7):
        packet_id = 100 + channel
        sent_messages.record(SimpleNamespace(id=packet_id, channel=channel, to=0xffffffff),
                             0x12345678, 'Synthetic submitted message')
        rows = sent_messages.recent(data / 'mesh.db', channel)
        assert len(rows) == 1 and rows[0]['id'] == 'sent:' + str(packet_id)
        with sqlite3.connect(data / 'mesh.db') as db:
            row_id = db.execute('''INSERT INTO packets(collector_time,packet_id,channel,rx_time,to_num,from_num,portnum,raw_json)
                                    VALUES (?,?,?,?,?,?,?,?)''',
                                 ('2026-01-01T00:00:00+00:00', packet_id, channel or None, 1,
                                  0xffffffff, 0x23456789, 'TEXT_MESSAGE_APP', '{}')).lastrowid
        assert node_control_bridge.reply_target(row_id, channel, '^all', data) == packet_id
        try:
            node_control_bridge.reply_target(row_id, (channel + 1) % 8, '^all', data)
        except ValueError:
            pass
        else:
            raise AssertionError('Replies must match their actual stored channel')
    assert not settings['enable_potato']
print('PASS: all channel slots preserved for submissions and feed-independent replies')
