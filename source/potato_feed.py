"""Optional single-batch Potato upload. No original station, keys or node exceptions."""
import json,sqlite3,time,urllib.request
from datetime import datetime,timezone
from contextlib import closing
from mf_feed import OUTBOX,ROOT,POLICY,ENABLED,BASE_URL,PAUSED,UPLOAD_HOLD,initialize,validate_payload,valid_meta

PATHS={'TEXT_MESSAGE_APP':'messages','NODEINFO_APP':'nodes','POSITION_APP':'positions','TELEMETRY_APP':'telemetry','NEIGHBORINFO_APP':'neighbors'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def iso(timestamp):
    return datetime.fromtimestamp(timestamp,timezone.utc).isoformat()


def omit_zero_sensor_readings(records):
    """Omit numeric zero metrics at export; retain reception and identity fields."""
    from meshtastic.protobuf import telemetry_pb2
    families={field.name:field.message_type for field in telemetry_pb2.Telemetry.DESCRIPTOR.fields if field.message_type}
    sensor_names={field.name for descriptor in families.values() for field in descriptor.fields}
    sensor_names.update(field.json_name for descriptor in families.values() for field in descriptor.fields)
    def clean(value):
        if isinstance(value,dict):
            return {k:clean(v) for k,v in value.items() if not (type(v) in (int,float) and v==0)}
        if isinstance(value,list):return [clean(v) for v in value]
        return value
    for record in records:
        record['telemetry']=dict(record.get('telemetry',{}))
        for key in list(record):
            if key in sensor_names and type(record[key]) in (int,float) and record[key]==0:
                del record[key]
            elif key in families:
                record[key]=clean(record[key])
        for field in telemetry_pb2.Telemetry.DESCRIPTOR.fields:
            if field.message_type:
                for key in (field.name,field.json_name):
                    if key in record.get('telemetry',{}):record['telemetry'][key]=clean(record['telemetry'][key])
    return records


def wire_payload(payloads):
    if not payloads or not all(validate_payload(p) for p in payloads): raise ValueError('Invalid public payload')
    port=payloads[0]['portnum']
    if any(p['portnum']!=port for p in payloads): raise ValueError('Mixed types')
    # Strip radio metadata from queued records, including older captured packets.
    records=[dict({k:v for k,v in p.items() if k not in ('lora_freq','modem_preset')},rx_iso=iso(p['rx_time'])) for p in payloads]
    if port=='TELEMETRY_APP':
        from meshtastic.protobuf import telemetry_pb2
        from google.protobuf.json_format import ParseDict, MessageToDict
        families={'device_metrics':'device','environment_metrics':'environment','power_metrics':'power','air_quality_metrics':'air_quality','health_metrics':'health','local_stats':'local_stats','host_metrics':'host','traffic_management_stats':'traffic'}
        for record,p in zip(records,payloads):
            metrics=MessageToDict(ParseDict(p['telemetry'],telemetry_pb2.Telemetry()),preserving_proto_field_name=True)
            record['node_id']=p['from_id']
            if metrics.get('time',0)>0:record['telemetry_time']=metrics['time']
            for family,kind in families.items():
                if family in metrics:
                    record['telemetry_type']=kind
                    # Preserve supported sensor fields before applying export filtering.
                    record[family]=metrics[family]
                    if family in ('device_metrics','environment_metrics'):
                        record.update(metrics[family])
    if port=='NODEINFO_APP':
        nodes={}
        for p in payloads:
            node={'num':int(p['from_id'][1:],16),'user':p['user'],'lastHeard':p['rx_time'],'protocol':'meshtastic'}
            for key in ('snr',):
                if key in p: node[key]=p[key]
            if p.get('hop_start',0)>0 and 0<=p.get('hop_limit',99)<=p['hop_start']:
                node['hopsAway']=p['hop_start']-p['hop_limit']
            nodes[p['from_id']]=node
        return {'protocol':'meshtastic','ingestor':payloads[0]['ingestor'],**nodes}
    if port=='NEIGHBORINFO_APP':
        records=[]
        for p in payloads:
            section=p['neighborinfo']
            record={k:p[k] for k in ('rx_time','ingestor','protocol') if k in p}
            record.update(node_id=p['from_id'],node_num=int(p['from_id'][1:],16),rx_iso=iso(p['rx_time']),neighbors=[])
            for n in section.get('neighbors',[]):
                heard=n.get('lastRxTime',p['rx_time']) or p['rx_time']
                entry=dict(neighbor_id=f"!{n['nodeId']:08x}",neighbor_num=n['nodeId'],rx_time=heard,rx_iso=iso(heard))
                if valid_meta('snr',n.get('snr')):entry['snr']=n['snr']
                record['neighbors'].append(entry)
            if 'nodeBroadcastIntervalSecs' in section:record['node_broadcast_interval_secs']=section['nodeBroadcastIntervalSecs']
            if section.get('lastSentById',0)>0:record['last_sent_by_id']=f"!{section['lastSentById']:08x}"
            records.append(record)
    if port=='TELEMETRY_APP':records=omit_zero_sensor_readings(records)
    return records


def main():
    if not ENABLED:raise SystemExit('Potato feeding is disabled; no request made')
    initialize()
    if PAUSED.exists() or UPLOAD_HOLD.exists():raise SystemExit('Feed capture is paused or awaiting operator review')
    token=(ROOT/'potato-feed/api-token').read_text().strip()
    if not token or any(c.isspace() for c in token):raise SystemExit('Set your own private Potato API token')
    with closing(sqlite3.connect(OUTBOX)) as db:
        rows=db.execute('SELECT sequence,payload FROM queue WHERE sent_at IS NULL AND policy=? ORDER BY sequence LIMIT 20',(POLICY,)).fetchall()
    if not rows:print('No eligible queued packets');return
    first=json.loads(rows[0][1])['portnum']
    rows=[(seq,json.loads(raw)) for seq,raw in rows if json.loads(raw)['portnum']==first]
    payload=wire_payload([p for seq,p in rows])
    request=urllib.request.Request(BASE_URL+'/api/'+PATHS[first],data=json.dumps(payload,allow_nan=False).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token},method='POST')
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=20) as response:
            if response.status!=201 or json.loads(response.read(4096)).get('status')!='ok':raise ValueError('Server did not confirm acceptance')
    except Exception:
        # A lost response may follow an accepted POST. Stop until an operator reviews it.
        UPLOAD_HOLD.write_text('Upload response failed or uncertain; review destination before removing this hold and restarting collection/feed')
        raise
    with closing(sqlite3.connect(OUTBOX)) as db,db:
        db.executemany('UPDATE queue SET sent_at=? WHERE sequence=?',[(int(time.time()),seq) for seq,p in rows])
    (ROOT/'potato-feed/status.json').write_text(json.dumps({'state':'uploaded','updated_at':int(time.time()),'last_batch':len(rows)}))
    print('Accepted public broadcast records:',len(rows))

if __name__=='__main__':main()
