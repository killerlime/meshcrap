"""Receiver timestamps and cached profiles; never request radio information."""
import math

LORA_FIELDS = ('use_preset', 'modem_preset', 'bandwidth', 'spread_factor', 'coding_rate',
               'region', 'channel_num', 'override_frequency', 'frequency_offset')


def observation_type(packet, session_started, arrived):
    """Keep undated/backlog packets in history without treating them as live RF."""
    value = packet.get('rxTime')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return 'UNDATED'
    if value > arrived + 60:
        return 'CLOCK_SKEW'
    if value < session_started - 5:
        return 'BUFFERED'
    return 'LIVE'


def radio_profile(iface):
    """Return already-cached modem settings without keys or security configuration."""
    from google.protobuf.json_format import MessageToDict
    config = MessageToDict(iface.localNode.localConfig.lora, preserving_proto_field_name=True,
                           always_print_fields_with_no_presence=True)
    metadata = MessageToDict(iface.metadata) if getattr(iface, 'metadata', None) else {}
    return dict(lora={key: config.get(key) for key in LORA_FIELDS},
                channels=[dict(index=c.index, name=c.settings.name or ('Primary' if c.index == 0 else f'Channel {c.index}'),
                               enabled=bool(c.role)) for c in iface.localNode.channels or []],
                metadata={key: value for key, value in metadata.items()
                          if key in ('firmwareVersion', 'hwModel', 'hasWifi', 'hasBluetooth')})
