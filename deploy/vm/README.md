# Meshcrap VM appliances

**CRAP = CuriousityReportingAndPossibilties**

A ready-to-configure home for exploring your mesh, reporting observations, and investigating possibilities.

These are fresh x86-64 Debian 12 installations, not copies of anyone's collector. Each includes the application and Python dependencies. No radio is connected, no feed is enabled, and no shared login password or application key is embedded.

- **VHDX:** create a Hyper-V **Generation 1** VM, attach the disk to its IDE controller, and connect a private/LAN virtual switch.
- **QCOW2:** import into QEMU/KVM or Proxmox with BIOS boot and a VirtIO disk/network adapter.
- **OVA / OVF + VMDK:** import the appliance into VMware or VirtualBox; choose the intended network. If your importer rejects the descriptor, create a Linux 64-bit BIOS VM and attach the VMDK manually.

Start with 2 CPUs and 2 GiB RAM. The virtual disk is 8 GiB; grow it and its filesystem before retaining months of packet history. The image build tests disposable overlays of all three disk formats in QEMU with BIOS/IDE boot, unique first-boot credentials, configuration setup, and actual dashboard HTTP checks. It also compares the exported disks with the source image. Hyper-V, VMware and VirtualBox imports require testing on those hosts; format conversion alone does not certify them.

## First boot

1. Open the VM's console. A unique temporary password for `meshcrap` appears there once. No network login is enabled.
2. Log in and change that password when prompted. If you lose the first-boot password, discard this unused VM and import a fresh copy.
3. Run `sudo meshcrap-setup`. The wizard shows the VM's addresses. Choose private-network access and enter the browser hostname/IP and trusted client network if you want to reach it from another device. Defaults remain local-only.
4. The dashboard starts after setup. Radio collection starts only if you explicitly choose it and configured a receiver.
5. Use your own private HTTPS proxy/Tailscale configuration for an iPhone Home Screen app and remembered browser controls. This appliance does not automatically expose itself publicly or enroll in anyone's network.

For JSON setup, edit `/opt/meshcrap/config.json`, then restart `meshcrap-dashboard`. Check configuration with `/opt/meshcrap/.venv/bin/python /opt/meshcrap/meshcrap.py check`. Optional radio control and Potato forwarding remain off until you enable them explicitly.

Builds contain `BUILD.txt` with the source revision and base-image checksum, plus `SHA256SUMS` for the exported files. Build your own with `bash deploy/vm/build.sh` on a Linux host with libguestfs and QEMU. The GitHub **Build VM appliances** workflow produces downloadable artifacts; console logs and generated test-boot credentials are never uploaded.
