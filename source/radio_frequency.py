"""Frequency metadata for the public US MediumFast feed, including automatic slots.

Matches Meshtastic RadioInterface::applyModemConfig: US 902--928 MHz,
250 kHz MediumFast slots, djb2 primary-name selection, and frequency offset.
Unsupported automatic configurations are omitted rather than guessed.
"""
import math

def effective_frequency(lora, primary_name=''):
    override=lora.get('override_frequency',0)
    offset=lora.get('frequency_offset',0)
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (override,offset)):
        return None
    if override:
        frequency=override+offset
    else:
        if lora.get('region') not in ('US',1) or lora.get('modem_preset') not in ('MEDIUM_FAST',4) or not lora.get('use_preset'):
            return None
        if primary_name not in ('','MediumFast','Primary'):
            return None
        slot=lora.get('channel_num',0)
        if type(slot) is not int or not 0<=slot<=104:
            return None
        if slot:
            index=slot-1
        else:
            name_hash=5381
            for ch in 'MediumFast':name_hash=(name_hash*33+ord(ch))&0xffffffff
            index=name_hash%104
        frequency=902.125+index*0.25+offset
    return round(frequency,6) if 100<=frequency<=3000 else None

def from_iface(iface):
    from google.protobuf.json_format import MessageToDict
    return effective_frequency(MessageToDict(iface.localNode.localConfig.lora,preserving_proto_field_name=True),iface.localNode.channels[0].settings.name)

def from_state(state):
    group=next((g for g in state.get('groups',[]) if g.get('kind')=='config' and g.get('name')=='lora'),{})
    lora={f['name']:f.get('value') for f in group.get('fields',[])}
    channel=next((c for c in state.get('channels',[]) if c.get('index')==0),{})
    return effective_frequency(lora,channel.get('name',''))
