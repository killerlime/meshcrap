# Meshcrap Survey — private Android test build

**CRAP = CuriousityReportingAndPossibilties**

The survey companion brings that curiosity into the field: collect observations, report survey results, and explore your mesh.

Connects directly to a paired configured Meshtastic radio over Bluetooth during a coverage survey. Disconnect the Meshtastic app first. Android 8 or later is required.

Open your collector's `/survey-companion` page over private HTTPS for the APK and pairing instructions. Start a survey on the website, connect the radio, verify its identity and channel, then send one manually selected test traceroute. Automatic requests require that test to succeed.

One request is outstanding at a time, with at least two minutes between starts and a five-minute timeout. Nearby destinations require recent observations and a valid position. Automatic requests pause when Bluetooth or collector connectivity is lost; collector authorization expires within 30 seconds. Stop releases Bluetooth. The app uses a three-hop request limit. No radio configuration is written.

Results queue in private storage and upload with a revocable survey-only credential. Phone routes and traceroutes remain separate from HQ RF measurements; a phone GPS point is not proof of RF coverage. Unknown relay IDs are retained. Each destination is attempted once per survey; changing channels requires another successful test.

This is a debug-signed first test build. Build, unit tests and Android lint pass. Real-phone Bluetooth and radio-response testing remains necessary. Do not assume a successful software build establishes hardware compatibility.

## Build

Use Java 17, Android SDK 35 and Gradle 8.9. Set `ANDROID_HOME`, then run `gradle assembleDebug testDebugUnitTest lintDebug` in this directory. The APK appears in `app/build/outputs/apk/debug/`. Dependencies download from the configured official repositories.

Source is GPL-3.0; see LICENSE. Meshtastic protocol definitions under `app/src/main/proto` come from the Meshtastic protobufs project. No private pairing tokens or radio keys are included.
