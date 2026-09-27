"""Status of the optional operator-configured Potato feed."""
import json,sqlite3
from pathlib import Path
from contextlib import closing
from flask import jsonify
def register_feed_status(app):
    root=Path('@@DATA_DIR@@/potato-feed')
    @app.get('/api/potato-feed/status')
    def feed_status():
        status=dict(enabled=@@ENABLE_POTATO@@,state='disabled',sent=0,pending=0,data_types=@@POTATO_TYPES@@,slot=@@POTATO_CHANNEL_SLOT@@)
        if not status['enabled']:return jsonify(status)
        status['state']='waiting_for_collector'
        try:status.update(json.loads((root/'status.json').read_text()))
        except (OSError,ValueError):pass
        try:
            with closing(sqlite3.connect((root/'outbox.db').as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
                status['pending']=db.execute('SELECT count(*) FROM queue WHERE sent_at IS NULL').fetchone()[0]
                status['sent']=db.execute('SELECT count(*) FROM queue WHERE sent_at IS NOT NULL').fetchone()[0]
        except sqlite3.Error:pass
        status['capture_paused']=(root/'capture-paused').exists();status['operator_hold']=(root/'upload-hold').exists()
        return jsonify(status)
