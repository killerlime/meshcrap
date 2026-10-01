"""Create an OVF/OVA envelope around the stream-optimized VMDK."""
from pathlib import Path
import hashlib, tarfile

out=Path('dist/vm');disk=out/'meshcrap-amd64.vmdk';ovf=out/'meshcrap-amd64.ovf'
ovf.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Envelope xmlns="http://schemas.dmtf.org/ovf/envelope/1" xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData">
<References><File ovf:id="diskfile" ovf:href="{disk.name}" ovf:size="{disk.stat().st_size}"/></References>
<DiskSection><Info>Meshcrap disk</Info><Disk ovf:diskId="disk1" ovf:fileRef="diskfile" ovf:capacity="8589934592" ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/></DiskSection>
<NetworkSection><Info>Choose a private network during import</Info><Network ovf:name="VM Network"><Description>Private appliance network</Description></Network></NetworkSection>
<VirtualSystem ovf:id="meshcrap"><Info>Meshcrap receiver dashboard</Info><Name>Meshcrap</Name>
<OperatingSystemSection ovf:id="96"><Info>Debian 12 64-bit</Info></OperatingSystemSection>
<VirtualHardwareSection><Info>2 CPUs, 2 GiB RAM, BIOS boot</Info><System><vssd:ElementName>Virtual hardware</vssd:ElementName><vssd:InstanceID>0</vssd:InstanceID><vssd:VirtualSystemIdentifier>Meshcrap</vssd:VirtualSystemIdentifier><vssd:VirtualSystemType>vmx-13</vssd:VirtualSystemType></System>
<Item><rasd:AllocationUnits>hertz * 10^6</rasd:AllocationUnits><rasd:Description>Virtual CPUs</rasd:Description><rasd:ElementName>2 virtual CPUs</rasd:ElementName><rasd:InstanceID>1</rasd:InstanceID><rasd:ResourceType>3</rasd:ResourceType><rasd:VirtualQuantity>2</rasd:VirtualQuantity></Item>
<Item><rasd:AllocationUnits>byte * 2^20</rasd:AllocationUnits><rasd:Description>Memory</rasd:Description><rasd:ElementName>2048 MiB memory</rasd:ElementName><rasd:InstanceID>2</rasd:InstanceID><rasd:ResourceType>4</rasd:ResourceType><rasd:VirtualQuantity>2048</rasd:VirtualQuantity></Item>
<Item><rasd:Address>0</rasd:Address><rasd:ElementName>SCSI controller</rasd:ElementName><rasd:InstanceID>3</rasd:InstanceID><rasd:ResourceSubType>lsilogic</rasd:ResourceSubType><rasd:ResourceType>6</rasd:ResourceType></Item>
<Item><rasd:AddressOnParent>0</rasd:AddressOnParent><rasd:ElementName>System disk</rasd:ElementName><rasd:HostResource>ovf:/disk/disk1</rasd:HostResource><rasd:InstanceID>4</rasd:InstanceID><rasd:Parent>3</rasd:Parent><rasd:ResourceType>17</rasd:ResourceType></Item>
<Item><rasd:AutomaticAllocation>true</rasd:AutomaticAllocation><rasd:Connection>VM Network</rasd:Connection><rasd:ElementName>Network adapter</rasd:ElementName><rasd:InstanceID>5</rasd:InstanceID><rasd:ResourceSubType>E1000</rasd:ResourceSubType><rasd:ResourceType>10</rasd:ResourceType></Item>
</VirtualHardwareSection></VirtualSystem></Envelope>''')
manifest=out/'meshcrap-amd64.mf'
lines=[]
for p in (ovf,disk):
    with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    lines.append(f'SHA256({p.name})= {digest}')
manifest.write_text('\n'.join(lines)+'\n')
with tarfile.open(out/'meshcrap-amd64.ova','w',format=tarfile.USTAR_FORMAT) as tar:
    for p in (ovf,manifest,disk):tar.add(p,arcname=p.name)
