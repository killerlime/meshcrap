"""Local submissions, kept separate from received RF measurements."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DATABASE = Path('@@DATA_DIR@@') / 'mesh.db'

def record(packet, sender, text, database=DATABASE, submitted_at=None):
    if not packet.id:
        raise ValueError('Missing submitted packet ID')
    with closing(sqlite3.connect(database, timeout=10)) as conn:
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS web_sent_messages (
                sender_num INTEGER NOT NULL, packet_id INTEGER NOT NULL,
                channel INTEGER NOT NULL, destination_num INTEGER NOT NULL,
                text TEXT NOT NULL, submitted_at TEXT NOT NULL,
                PRIMARY KEY(sender_num, packet_id))''')
            conn.execute('INSERT OR IGNORE INTO web_sent_messages VALUES (?,?,?,?,?,?)',
                         (sender, packet.id, packet.channel, packet.to, text,
                          submitted_at or datetime.now(timezone.utc).isoformat()))

def recent(database, channel, limit=100):
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True, timeout=3)) as conn:
        conn.row_factory = sqlite3.Row
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='web_sent_messages'").fetchone():
            return []
        rows = conn.execute('''SELECT s.*, n.long_name, n.short_name
            FROM web_sent_messages s LEFT JOIN nodes n ON n.node_num=s.sender_num
            WHERE (CASE WHEN s.sender_num=@@RECEIVER_NUM@@ AND s.channel IN (2,3) THEN 5-s.channel ELSE s.channel END)=? AND s.destination_num=4294967295
            AND NOT EXISTS (SELECT 1 FROM packets p WHERE p.from_num=s.sender_num
                AND p.packet_id=s.packet_id AND p.portnum='TEXT_MESSAGE_APP')
            ORDER BY s.submitted_at DESC, s.packet_id DESC LIMIT ?''', (channel,limit)).fetchall()
        return [dict(id='sent:'+str(r['packet_id']), received_at=r['submitted_at'],
                     sender_id=f"!{r['sender_num']:08x}",
                     sender=r['long_name'] or r['short_name'] or f"!{r['sender_num']:08x}",
                     text=r['text'], snr=None, hops=None, direction='sent') for r in rows]
