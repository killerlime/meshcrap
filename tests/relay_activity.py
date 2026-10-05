import importlib.util
import json
from pathlib import Path

path=Path(__file__).resolve().parents[1]/'source/dashboard/relay_activity.py'
spec=importlib.util.spec_from_file_location('relay_activity',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
nodes=[dict(node_num=1,node_id='!00000001',long_name='Origin',short_name='O',role='CLIENT'),
       dict(node_num=234,node_id='!000000ea',long_name='Relay',short_name='R',role='CLIENT'),
       dict(node_num=490,node_id='!000001ea',long_name='Collision',short_name='C',role='CLIENT')]
def row(id,packet_id,relay=None,hops=None,origin=1,**extra):
    p={} if relay is None else {'relayNode':relay};p.update(extra)
    return dict(row_id=id,packet_id=packet_id,from_num=origin,from_id=f'!{origin:08x}',
       portnum='NODEINFO_APP',hops_used=hops,collector_time=f'2026-10-01T00:00:{id:02d}+00:00',
       rx_snr=3,rx_rssi=-100,raw_json=json.dumps(p))
data=module.summarize([row(1,10,234),row(2,10,234),row(3,11,hops=2),
    row(4,12,1,0),row(5,13),row(6,14,234,viaMqtt=True),row(7,15,234,origin=99),
    row(8,16,0,1)],nodes,'!00000063')
assert data['relayed_packets']==3
assert data['direct_packets']==1 and data['unknown_packets']==1
node=data['nodes'][0]
assert node['nodeinfo']==3 and node['unidentified_relay']==2
assert len(node['relays'][0]['candidates'])==2
assert node['last_heard'].endswith('08+00:00')
assert module.summarize([row(1,1,1,0)],nodes,'!00000063')['nodes']==[]
print('PASS: relay evidence, duplicate suppression, ambiguous IDs, unknown/direct separation, MQTT and receiver exclusion')
