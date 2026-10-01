# Portable live ISO — experimental

This additional x86-64 PC option is designed to boot a Debian desktop from USB or a VM virtual CD and copy the live filesystem into RAM. It does not replace the installed app, Android build or VM disk images. It is not a Raspberry Pi boot image.

The recipe uses `toram nopersistence noswap`, has no installer, disables desktop volume automounting, and keeps SSH disabled. Open **Start Meshcrap** on the desktop to run the setup wizard and browser. Some desktops ask you to mark a launcher executable/trusted first. Only do so for your own verified build.

Settings, credentials and collected records live in the temporary session and disappear on shutdown. Export wanted information to storage you deliberately choose. This first version has no persistence wizard. Do not use it for unattended long-term collection. It is not a forensic or secure-erasure environment: booting reads the boot medium, and an operator can explicitly mount/write other disks.

Allow at least 8 GiB RAM for initial testing; the final requirement depends on ISO size, browser use and collected data. RAM collection can fill memory. Wired networking is the initial target; proprietary Wi-Fi firmware and Secure Boot compatibility are not established.

## Build from committed source

Use a disposable Debian/Ubuntu x86-64 build host with `live-build`, `debootstrap`, `squashfs-tools`, `xorriso`, `isolinux`, `syslinux-common`, Git and Python 3 installed. Run `sudo bash deploy/live/build.sh` from a clean checkout. Packages download from Debian/Python repositories. The recipe packages committed HEAD and writes the ISO, checksum and build identification under `dist/live/`.

Build success alone is not boot verification. Before distribution, test BIOS/UEFI startup, RAM-backed writes, disk mounts, network access, setup, dashboard and shutdown data loss in a disposable VM. No passing live-ISO boot test is claimed yet. Verify the checksum before use. Writing an ISO to USB overwrites that USB: identify and back up the intended device yourself.

Based on [Debian Live](https://live-team.pages.debian.net/live-manual/html/live-manual.en.html). Preserve the project's licenses and notices and Debian package copyright information when redistributing. Debian, Python dependencies and desktop packages have their own licenses; this project does not relicense them. See the [source-build guide](../../docs/BUILDING.md) and [project notice](../../docs/PROJECT-NOTICE.md).
