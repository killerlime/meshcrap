# Build from source

Review the [project notice and operational limits](PROJECT-NOTICE.md) before deploying or distributing a build.

Building from source is optional. You can inspect, modify and run the source without downloading a prebuilt app or VM. No developer account or project-specific credentials are required for a local dashboard or Android debug build.

## Dashboard and collector

Use Linux (including WSL2), Python 3.11 or newer, Git, and SQLite with JSON support. Node.js is needed for frontend tests, not to serve the dashboard.

```sh
git clone https://github.com/killerlime/meshcrap.git
cd meshcrap
git rev-parse HEAD
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python meshcrap.py setup
python meshcrap.py check
python meshcrap.py serve
```

Open `http://127.0.0.1:8080`. The wizard also supports choosing your app title. JSON configuration is an alternative: copy `config.example.json` to `config.json`, edit it, and run `python meshcrap.py init`. Collection is separate: after configuring your own radio, run `python meshcrap.py collect` in another activated terminal. Setup and build steps do not send radio requests.

Run the checks in [CONTRIBUTING.md](../CONTRIBUTING.md) using a fresh test installation. Keep production databases, tokens, channel settings and location history outside the checkout. Save `git rev-parse HEAD` and `python -m pip freeze` privately with your build records: dependency ranges mean two builds on different dates are not guaranteed to resolve identically.

### Raspberry Pi connections

The setup wizard offers a direct TCP radio or an existing Raspberry Pi TCP bridge. Enter your own hostname/IP, listening port and receiver node ID. No personal Pi address, SSH account, host key or login is supplied. These values stay in your ignored local configuration. A bridge must already be installed and reachable; this option does not install one or open firewall ports. If the dashboard runs on the same Pi as the bridge, use its loopback address when the bridge supports that. SSH administration is separate and is not required by the collector.

## Android companion

Install Java 17, Android SDK Platform 35 and Gradle 8.9. Accept the Android SDK licenses through its normal installation process and set `ANDROID_HOME` to your SDK directory. From the repository root:

```sh
cd android
gradle --no-daemon testDebugUnitTest lintDebug assembleDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. This repository uses an installed Gradle; it does not currently include a Gradle wrapper. Android Studio can also open the `android` project. A debug APK uses your machine's debug signing key, so it may not update an APK signed by somebody else. Uninstalling can remove saved pairing and queued survey results; upload results first. For distribution, configure your own release signing outside version control and retain that key for future updates. Never publish signing keys or passwords.

Software tests do not replace Bluetooth and background-operation testing on an actual phone. Android sources and protocol definitions have their own [GPL license](../android/LICENSE).

## Browser demo and iPhone

```sh
python tools/build_demo.py
python -m http.server 8765 --bind 127.0.0.1 --directory dist/demo
```

Open `http://127.0.0.1:8765`. Demo data is synthetic. Map tiles and optional location search still use external services.

The current iPhone option is the dashboard's installable web app over private HTTPS. It is not a native iOS binary; there is no Xcode project or Bluetooth survey support to build for iPhone in this release.

## VM images — experimental

Use a disposable Linux build host with Git, Python 3, curl, gzip, libguestfs tools, QEMU utilities/system emulator and a usable Linux kernel for libguestfs. On Ubuntu, the build workflow installs `libguestfs-tools qemu-utils qemu-system-x86 linux-image-generic`. Consult the [workflow](../.github/workflows/vm.yml) for its exact environment and [VM guide](../deploy/vm/README.md) for platform settings.

```sh
sudo bash deploy/vm/build.sh
```

The builder packages **committed HEAD**, not uncommitted edits. Commit your intended source changes locally before building. It downloads Debian and package dependencies and writes images under `dist/vm`. Do not distribute outputs from an incomplete or failed build. VM builds are still being debugged; a build command here is not a claim of passing native Hyper-V, VMware or VirtualBox tests. Review the actual run results before use.

Successful builds include source/base-image identification and checksums. Record dependency versions too; the current builder is not byte-for-byte reproducible. Review [third-party notices](../THIRD_PARTY_NOTICES.md), bundled licenses and Debian package copyright files before redistributing an appliance. The project's license does not replace dependency licenses or data-provider terms.
