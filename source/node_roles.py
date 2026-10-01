"""Interpret roles only when a node identity report supplies evidence."""
from meshtastic.protobuf import mesh_pb2

def reported_role(user):
    if not isinstance(user, dict) or not any(user.get(k) for k in ('longName','shortName','hwModel')):
        return None
    descriptor=mesh_pb2.User.DESCRIPTOR.fields_by_name['role']
    value=user.get('role',descriptor.default_value)
    if isinstance(value,bool):return None
    if isinstance(value,int):
        item=descriptor.enum_type.values_by_number.get(value)
        return item.name if item else None
    if isinstance(value,str) and value in descriptor.enum_type.values_by_name:return value
    return None
