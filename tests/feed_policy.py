"""Synthetic public/private packet policy checks; no HTTP or radio access."""
import importlib.util,json,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packaging_cli',ROOT/'meshcrap.py');cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
with tempfile.TemporaryDirectory(prefix='feed-policy-') as directory:
    path=Path(directory)/'config.json';config=json.loads((ROOT/'config.example.json').read_text())
    config.update(data_dir=str(Path(directory)/'data'),receiver_id='!12345678',radio_host='192.0.2.10',enable_potato=True,potato_url='https://example.invalid')
    path.write_text(json.dumps(config));config,data=cli.load_config(path);runtime=cli.initialize(config,data)
    sys.path[:0]=[str(runtime),str(runtime/'dashboard')]
    import mf_feed
    mf_feed.initialize()
    descriptor=NS(fields_by_name={'modem_preset':NS(enum_type=NS(values_by_number={1:NS(name='MEDIUM_FAST')}))})
    lora=NS(use_preset=True,modem_preset=1,DESCRIPTOR=descriptor)
    node=NS(nodeNum=0x12345678,channels=[NS(index=0,role=1,settings=NS(name='MediumFast',psk=b'\x01'))],localConfig=NS(lora=lora))
    radio=NS(isConnected=NS(is_set=lambda:True),localNode=node)
    # RF frequency is a separate helper; this fake radio intentionally has no full modem config.
    import radio_frequency;radio_frequency.from_iface=lambda iface:None
    packet=dict(to=0xffffffff,**{'from':0x23456789},id=1,rxTime=int(time.time()),decoded=dict(portnum='TEXT_MESSAGE_APP',text='Synthetic test'))
    assert mf_feed.connected(radio)
    valid=mf_feed.eligible_payload(packet,radio);assert valid and mf_feed.validate_payload(valid)
    for mutation in ({'channel':1},{'to':0x34567890},{'pkiEncrypted':True},{'viaMqtt':True},{'from':0x12345678},{'rxTime':1},{'decoded':{'portnum':'POSITION_APP','position':{'latitudeI':100,'longitudeI':100}}}):
        assert mf_feed.eligible_payload(packet|mutation,radio) is None,mutation
    assert not mf_feed.validate_payload(valid|{'secret':'must not pass'})
    assert not mf_feed.validate_payload(valid|{'ingestor':'!34567890'})
    assert mf_feed.capture(packet,radio)
    import potato_feed
    from unittest.mock import patch
    token=mf_feed.ROOT/'potato-feed/api-token';token.write_text('synthetic-test-token')
    payload=potato_feed.wire_payload([valid]);assert payload[0]['text']=='Synthetic test'
    def radio_metadata(value,frequency=None):
        records=value if isinstance(value,list) else [v for k,v in value.items() if k.startswith('!')]
        assert records
        for record in records:
            assert record['modem_preset']=='MediumFast'
            if frequency is not None:assert record['lora_freq']==frequency
    sections={'TEXT_MESSAGE_APP':'Synthetic test','NODEINFO_APP':{'id':valid['from_id'],'longName':'Test'},'POSITION_APP':{'latitudeI':440000000,'longitudeI':-930000000},'TELEMETRY_APP':{'time':valid['rx_time'],'deviceMetrics':{'batteryLevel':0,'voltage':0}},'NEIGHBORINFO_APP':{'nodeId':int(valid['from_id'][1:],16),'neighbors':[{'nodeId':0x34567890,'snr':0}]}}
    original_allowed=mf_feed.ALLOWED
    mf_feed.ALLOWED=set(sections)
    for port,section in sections.items():
        sample={k:v for k,v in valid.items() if k!='text'}
        sample.update(portnum=port,lora_freq=906.875,snr=0)
        sample[mf_feed.SECTIONS[port]]=mf_feed.clean_section(port,section,sample['from_id'])
        before=json.dumps(sample,sort_keys=True)
        output=potato_feed.wire_payload([sample]);radio_metadata(output,906.875)
        assert json.dumps(sample,sort_keys=True)==before
        if isinstance(output,list):assert output[0]['rx_iso']==potato_feed.iso(sample['rx_time'])
        if port=='TELEMETRY_APP':
            assert 'battery_level' not in output[0] and 'voltage' not in output[0]
            assert not output[0]['device_metrics']
            assert not output[0]['telemetry']['deviceMetrics']
    mf_feed.ALLOWED=original_allowed
    class Reply:
        status=201
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'{"status":"ok"}'
    with patch('urllib.request.build_opener') as opener:
        opener.return_value.open.return_value=Reply()
        potato_feed.main()
        assert opener.return_value.open.call_count==1
        request=opener.return_value.open.call_args.args[0]
        assert request.full_url=='https://example.invalid/api/messages'
        radio_metadata(json.loads(request.data))
    assert mf_feed.capture(packet|{'id':2},radio)
    with patch('urllib.request.build_opener') as opener:
        opener.return_value.open.side_effect=TimeoutError('Synthetic uncertain response')
        try:potato_feed.main()
        except TimeoutError:pass
        else:raise AssertionError('Expected uncertain response')
        assert opener.return_value.open.call_count==1
        assert mf_feed.UPLOAD_HOLD.exists()
        assert not mf_feed.connected(radio) # Reconnection must not clear an operator hold.
        assert mf_feed.eligible_payload(packet,radio) is None
    mf_feed.UPLOAD_HOLD.unlink()
    assert mf_feed.connected(radio)
    radio.localNode.channels[0].settings.psk=b'private-key'
    assert mf_feed.eligible_payload(packet,radio) is None
    mf_feed.ENABLED=False
    assert mf_feed.eligible_payload(packet,radio) is None
print('PASS: opt-in, public key/preset/channel, broadcast-only, configured data types, receiver exclusion, timestamp and payload allowlists')
