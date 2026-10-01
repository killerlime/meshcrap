# Raspberry Pi image (build recipe preview)

This replaces the live-ISO packaging plan. It produces `meshcrap-arm64.img.xz`,
a compressed native SD-card image for **Raspberry Pi Imager → Use custom**.
Imager can decompress it while writing; `unxz -k meshcrap-arm64.img.xz` produces
the raw `.img` if another flasher requires it. Select the intended SD card: flashing erases it.

**No built or physically boot-tested Pi image is available yet.** The initial
validation targets are Pi 4 and Pi 5; other ARM64-capable Pis remain unverified.
This is persistent Raspberry Pi OS Lite, not a RAM-only session. Use a 16 GB or
larger quality SD card, adequate power and Ethernet for the first test.

## First boot

1. Write the image and allow Imager to verify it. Use a current Imager version.
2. Complete Raspberry Pi OS user creation with a keyboard/display. The image
   contains no shared login password. Imager customization is not yet verified
   for this custom image; do not rely on it for unattended access.
3. Log in and run `sudo meshcrap-setup`. The existing wizard configures the app
   title, private network access, data storage and your radio connection.
4. Start collection only after checking that radio configuration. The dashboard
   and collector use a dedicated non-login service account.

Private configuration lives in `/var/lib/meshcrap/config.json`; the default data
directory is `/var/lib/meshcrap/data`. Installed code and dependencies under
`/opt/meshcrap` are root-owned. Canceling setup leaves services unchanged; saving
new settings validates them and restarts the dashboard. Radio collection requires
an explicit choice and a configured receiver.

## Automated build candidates

The **Raspberry Pi image validation** GitHub Actions workflow builds on a disposable
native ARM64 runner. It runs the clean-install and efficiency checks inside the
image, verifies setup and HTTP serving as the non-login application user, then
mounts the completed image read-only to check its empty private state, locked
default accounts, fresh machine identity and disabled application services.
Successful candidates include checksums, the matching application source archive,
build provenance and `IMAGE-AUDIT.json`. They are retained as workflow artifacts
for seven days; they are **not physically boot-certified release downloads**.

Run the workflow manually from Actions after it is merged. Build dependencies and
downloads require internet access. A successful build does not verify Imager
customization, Wi-Fi, SD-card expansion or actual Pi hardware. Those still require
the spare-card checks below.

The first version uses the collector's existing network-radio connection. USB,
Bluetooth and board-mounted SPI radio setup are not automatically configured.
Wi-Fi, SSH and Tailscale are optional user-owned configuration; no keys, network
profiles, personal endpoints, channel data or node history are embedded.

## Build from source

Use a **disposable native ARM64 Debian/Raspberry Pi OS Linux machine**, with
roughly 30 GB free Linux filesystem space. Do not build on a working collector.
Install the [official pi-gen dependencies](https://github.com/RPi-Distro/pi-gen/tree/arm64#dependencies),
plus Python 3. Commit the reviewed application tree locally, then run:

```sh
sudo bash deploy/pi/build.sh
```

The script pins official pi-gen to commit
`4d8ee447dd3d37e8b0ef8752e460d9082d9d435d`, adds the application after its Lite
stage and exports only that final image. Source is taken from Git, not copied
from a live Pi. Output, checksums and build provenance go into `dist/pi/`.
The temporary build tree is retained for diagnostics because failed image builds
can leave mounts; unmount it safely before deleting it.

## Release gates

Before distribution: inspect the mounted image for credentials and personal data;
verify fresh user/machine identity, clean data directory, package/license inventory
and source availability; flash a spare card and test boot, wizard, dashboard,
collection, restart persistence and expansion to the full SD-card size on Pi 4/5.
The build runs application smoke tests in the target root filesystem, but those
do not replace real boot and hardware tests. No image is uploaded automatically.

The application licenses remain included under `/opt/meshcrap`; OS packages retain
their own licenses under `/usr/share/doc`. The image records installed Debian and
Python packages. This is an unofficial derivative, not endorsed by Raspberry Pi.
See [official Imager instructions](https://www.raspberrypi.com/documentation/computers/getting-started.html#install-an-operating-system)
and [pi-gen](https://github.com/RPi-Distro/pi-gen) for upstream build/source details.
