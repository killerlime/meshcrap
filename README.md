# Meshcrap

> **Mesh + CRAP — CuriousityReportingAndPossibilties**
>
> **Curiousity. Reporting. And Possibilties.** Explore what your mesh is doing, report what you observe, and investigate what might be possible.

A private Meshtastic receiver console: collect packets into SQLite, see what your radio is hearing, explore nodes and messages, map demonstrated coverage, and compare LNA test periods.

This is a portable extraction of a working personal installation. It starts with an **empty database**, a **loopback-only dashboard**, and **no radio connection**. Set your own receiver, location and regions before collecting. No original node history, messages, credentials, ownership badges or home-network configuration are included.

## Work in progress — contributions welcome

**Experimental software, provided as-is.** Coverage and analysis are observational, not guarantees. Do not rely on Meshcrap for emergency communications or safety-critical decisions. Read the [project notice and operational limits](docs/PROJECT-NOTICE.md) and the applicable [licenses](#licensing).

Meshcrap is a community project in active development. Expect rough edges and help make it better: report bugs, test your device, improve the interface and documentation, or send a pull request. Future measurement-quality ideas are in the [RF roadmap](docs/RF-ROADMAP.md); these are planning items, not enabled features. See [CONTRIBUTING.md](CONTRIBUTING.md) for a safe way to get started and the checks to run. VM appliance images and live ISOs are outside the current release scope.

## What is included

- TCP receiver collector with reconnection handling and local SQLite history.
- Dashboard, node details, messages, charts, coverage regions and survey reports.
- Relative activity, direct/relayed RF statistics, local-transmission filtering and 30-day coverage aging.
- LNA transition records, noise-floor analysis and observational comparisons.
- Separate What-if software simulator and optional on-demand terrain profiles; see [models and limits](docs/MESH-SIMULATOR.md).
- Interactive Tropo forecast map loaded only when viewed; see [sources and privacy](docs/TROPO-SOURCES.md).
- Passive receiver role comparison in Insights, with explicit assumptions and no radio mode changes.
- Expanded recent-node details and one-time phone pairing with optional 30-day browser trust.
- Optional authenticated radio controls through the collector's existing connection.
- Optional Weather Underground display, configured with your own station and key.
- Android Bluetooth survey companion source. Automatic traceroutes start after you explicitly enable surveying, with one outstanding request, 30-second minimum spacing and a 30-second timeout.

The Android companion is a **test build**: compilation and software tests are verified; real-phone Bluetooth/radio testing remains necessary. The dashboard does not claim that a phone GPS point proves RF coverage.

## Supported setup

Use Linux with Python 3.11 or newer, SQLite with JSON support, and a Meshtastic radio reachable over TCP (normally port 4403). A Raspberry Pi, Linux PC or Linux VM is suitable. Python dependencies are in [`requirements.txt`](requirements.txt). Windows can prepare the configuration; running the server/collector requires Linux or WSL2 because some controls use Unix sockets and Linux APIs.

Serial/USB radio transport is not implemented in this release. A USB-attached radio needs a separately configured TCP bridge. Hardware-specific display power controls, the original second-radio relay, automatic PKI polling and host network switching are not included as working integrations. Their dashboard entry points may report unavailable. They do not run automatically. Potato feeding is a separate opt-in integration described below.

## Try it before installing

[Open the interactive demo](https://killerlime.github.io/meshcrap/). Choose a city or coordinates and explore fictional nodes, maps, activity, messages and what-if insights. All data is simulated; this is not a real coverage forecast.

## Quick start

For a guided walkthrough, expected results, and common connection problems, see [First use](docs/FIRST-USE.md).

Prefer to build everything yourself? See the [build-from-source guide](docs/BUILDING.md) for the dashboard, Android APK, demo and Raspberry Pi image recipe, including tests and signing notes. Prebuilt downloads are optional.

```sh
git clone https://github.com/killerlime/meshcrap.git
cd meshcrap
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python meshcrap.py setup
python meshcrap.py serve
```

Prefer JSON? Copy `config.example.json` to `config.json`, edit it, and run `python meshcrap.py init` instead. Both paths use the same validation and configuration format. The wizard backs up an existing configuration before replacing it; it never starts the radio or sends data. Press Enter through the defaults for an empty local dashboard.

Open **http://127.0.0.1:8080** on that computer. This is a real empty installation, not a bundled sample of someone else's mesh.

Edit `config.json`, then stop and restart the application to apply changes. In another terminal, start collection after setting `radio_host` and `receiver_id`:

```sh
. .venv/bin/activate
python meshcrap.py collect
```

The collector verifies that the connected radio has the configured node ID before accepting it. Keep only one collector connection to that radio. Collection does not enable public forwarding or automatic remote administration.

## Configuration

[`config.example.json`](config.example.json) is the complete configuration reference. Your `config.json` is ignored by Git.

| Setting | Meaning |
|---|---|
| `app_title` | App title chosen in the setup wizard or JSON. |
| `radio_host`, `radio_port` | Your receiver's TCP address. An empty host prevents collection. |
| `receiver_id` | Actual `!` plus eight-hex-digit node ID. The placeholder cannot start collection. |
| `data_dir` | Persistent data directory, relative to the configuration file or absolute. Keep it outside shared folders. |
| `bind_host`, `web_port` | Dashboard listener; default `127.0.0.1:8080`. |
| `trusted_hosts`, `allowed_networks` | Explicit host-header and client-network allowlists. Add only addresses you intend to use. |
| `https_host` | Private HTTPS hostname, without scheme or port, for phone pairing. |
| `node_prefix` | Local-node short-name prefix and Android survey source filter. Default `MY`. |
| `home_lat`, `home_lon` | Your map center and distance reference. Defaults are neutral placeholders. |
| `regions` | Coverage regions. Keep the `home` ID; add up to 11 more. Bounds are `[south, north, west, east]`. Each has its own `cell_miles`. |
| `channels` | Display labels keyed by local slot number. These do not change radio settings. |
| `timezone` | IANA timezone for time-of-day LNA comparisons, default `UTC`. |
| `initial_lna_state` | `UNKNOWN`, `OFF` or `ON`. Confirm physical state before starting a comparison. |
| `enable_radio_controls` | Starts the local control bridge and enables dashboard control actions. Default `false`. |
| `radio_idle_timeout` | Seconds without any radio updates before reconnecting. Default `0` disables this check so quiet radios do not reconnect unnecessarily. |
| `enable_weather`, `weather_station` | Optional weather polling, disabled by default. |

Use normal file paths without quotes/newlines. Regions are independently computed; avoid overlapping regions if you want an unambiguous partition. A region is limited to approximately 10,000 cells. Geographical bounds near the poles or across the date line are not supported.

## Private access and radio controls

See [optional Tailscale/private HTTPS setup](docs/REMOTE-ACCESS.md) for prerequisites, user-owned connection details and sharing limits.

This is a private-network tool, not a public hosting service. Read-only pages are available to permitted network clients. Changing data requires the dashboard control key; radio operations also require `enable_radio_controls: true`.

The dashboard generates a fresh control key at `data/.node-control-key` on first start. Read that file locally and enter it in the dashboard's unlock field. Never commit it, put it in a URL, or share it in an issue. Each installation also creates its own session secret and phone credentials.

For phone surveys, provide trusted HTTPS on port 443. A private Tailscale Serve configuration forwarding to the loopback dashboard is one option. Configure `https_host` and add that hostname to `trusted_hosts`. Only a local reverse proxy is trusted to assert HTTPS. Do not disable certificate validation or expose port 8080 to the public Internet. A second machine needs its address/network explicitly allowed if it connects directly.

The control bridge shares the collector's radio connection. Some actions transmit over RF or change the radio configuration; review the destination and channel before using them. Automatic PKI polling is disabled in this distribution.

## Android survey app

The source is in [`android/`](android/), with its own GPL license. Use Java 17, Android SDK 35 and Gradle 8.9:

```sh
cd android
gradle assembleDebug testDebugUnitTest lintDebug
```

Install `app/build/outputs/apk/debug/app-debug.apk` on an Android 8+ phone. Debug APKs and signing keys are intentionally excluded from Git. For a release build, use your own signing key.

1. Open `/survey-companion` on your collector through its private HTTPS hostname.
2. Unlock dashboard controls and generate a phone pairing code. Paste it into the app; it includes your configured local-node prefix.
3. Disconnect Meshtastic's Bluetooth connection to the radio, then connect the survey app to that already-paired radio.
4. Confirm the radio identity. Slot 0 is the default; an explicit channel choice is remembered for that radio.
5. Tap **Start survey** in Android. This starts a roaming survey and automatic nearby-node requests when ready. No area selection or manual traceroute is required. Routes and results are retained outside every configured grid.

Stop releases Bluetooth so Meshtastic can reconnect. Collector authorization expires within 30 seconds of lost connectivity. Results queue locally and upload idempotently when connected; unknown relay IDs remain unknown. The current request hop limit is three.

To host a locally built APK on the setup page, copy it to `<data_dir>/dashboard/survey-downloads/meshcrap-survey-test.apk`. No prebuilt APK is shipped here. Full end-to-end physical-radio verification is still a follow-up item.

## Optional questions assistant

The questions panel stays unavailable until you create `<data_dir>/ask-questions/config.json` with your own `api_key` and optional `model`. When you use it, selected local evidence, including message text, can be sent to the OpenAI API. This is independent of Potato export. No API key or assistant configuration is included.

## Weather

Set `enable_weather` and your `weather_station`. Put your own Weather Underground API key in `<data_dir>/weather-api-key`, readable only by the service account. Weather observations stay separate from radio packet history. This package does not publish them externally.

## Optional Potato feed

Potato feeding is **disabled by default**. There is no bundled server address, API token, ingestor identity, private-channel exception list, position-fuzzing seed or preloaded outbox. The feed uses your configured receiver ID as its ingestor identity.

To enable it deliberately:

1. Set `enable_potato: true`, `potato_url` to your server's HTTPS origin, and `potato_channel_slot` to the intended public MediumFast slot.
2. Set `potato_types` to the data types you intend to publish. The default is broadcast text only (`TEXT_MESSAGE_APP`). Optional types are `NODEINFO_APP`, `POSITION_APP`, `TELEMETRY_APP` and `NEIGHBORINFO_APP`. Position records include actual advertised coordinates; enabling them publishes those coordinates.
3. Write your own token to `<data_dir>/potato-feed/api-token` and restrict the file to the service user (`chmod 600`). Never put it in Git or the shared configuration example.
4. Restart collection. Capture starts only after confirming the selected channel uses the standard public key, an empty/MediumFast name and the MEDIUM_FAST modem preset.
5. Run `python meshcrap.py feed` to submit one bounded batch. It sends only newly captured records under the current policy, not historical collector rows.

Private/direct messages, PKI traffic, MQTT traffic, receiver-local measurements and other channel slots are excluded. There are no per-node exceptions. Original private feed customizations and automatic heartbeat publication are not included. Changing endpoint, receiver, channel or allowed types changes the export policy; queued records under old policies are not sent.

The uploader uses the Potato `/api/messages`, `/api/nodes`, `/api/positions`, `/api/telemetry` and `/api/neighbors` payload conventions. Acceptance requires HTTP 201 with `{"status":"ok"}`. It never follows redirects and makes no automatic HTTP retry. An uncertain response creates `<data_dir>/potato-feed/upload-hold` and pauses capture and uploads. Inspect the destination to determine whether it accepted the batch before removing the hold and restarting collection. Do not blindly retry an uncertain batch. Software tests use a fake destination; no test records are sent to a real Potato server.

## Running as a service

Example units are in [`deploy/`](deploy/). Set their working directory, Python path, configuration path and service user for your installation. Run dashboard and collector as the same unprivileged user so they can share the database and optional control socket. Install the units only after both commands work manually. Do not grant blanket passwordless sudo.

## Data, backups and upgrades

`data_dir` contains the database, configuration-dependent runtime copy, weather/survey data, credentials and backups. Keep all of it private. `source/` contains readable installation templates; `@@NAME@@` values are filled from your local configuration into `data_dir/.runtime/`. Edit source templates, not generated runtime files.

Before upgrading, stop both services and copy the entire data directory and your `config.json` to private storage. Alternatively, use SQLite's backup API for a consistent live database backup; copying only `mesh.db` while WAL writes continue is unsafe. Preserve credentials during a same-installation restore. Generate new credentials when giving the software to someone else.

After pulling a reviewed update, install dependencies, run `python meshcrap.py check`, and restart services. Schema version 1 is supported. The initializer refuses an existing unversioned database; **do not point it at an older live installation**. A migration tool for legacy personal installations is not yet included. `init` preserves an existing version-1 database and LNA history.

## Verification

```sh
python meshcrap.py --config config.example.json check
python tests/smoke.py
python tests/feed_policy.py
python tests/frontend.py  # Requires Node.js
python tests/privacy_check.py
```

The Linux smoke test uses an isolated empty database and checks dashboard, coverage, message, LNA, survey and authentication behavior. It does not connect to a radio. Frontend JavaScript and Android checks are separate. New hardware should receive a manual connection, reception, control and survey test before relying on it.

## Licensing

See also the [security reporting policy](SECURITY.md), [data-use notice](docs/DATA-USE.md), and [project notice](docs/PROJECT-NOTICE.md).

Original project code follows the repository's existing [Unlicense](LICENSE), except where a component supplies its own license. The [Android companion](android/LICENSE) and bundled Meshtastic protocol definitions use GPL-3.0. Vendored Leaflet uses BSD-2-Clause; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Dependencies retain their own licenses; distributing combined builds must comply with those licenses.

## Latest update

The Android companion is version 0.3.0-test with clearer connection, pairing, location and survey status. Install updates over the existing app to retain its encrypted pairing. The setup page can remember a personal browser for 30 days for routine survey controls; changing or revoking a pairing still requires a fresh admin unlock. Generating a replacement pairing invalidates the previous one.

PKI probing has been removed; historical observations remain readable. The Funny Pages section has also been removed. Receiver role comparisons are observational scenarios, not predictions of delivery or a substitute for a controlled field test. Personal region boundaries, themed artwork, hardware overrides, network addresses and feed credentials are intentionally excluded; configure your own installation.

## Portable identity update

The survey companion now uses the application ID `org.meshcrap.survey`. It installs separately from earlier personal builds and needs its own one-time pairing. Browser preferences and trust cookies also use the Meshcrap identity; unlock the new browser session once. Published download filenames use the `meshcrap-survey` prefix. Existing local databases are not modified by this source cleanup.

## Browser efficiency and server runtime

The dashboard uses Waitress with one process and four request threads. Reinstall requirements when updating; the existing `serve` command and service files stay the same. HTTPS forwarding is recognized only by the existing loopback/exact-host middleware, never arbitrary forwarded headers.

Chart.js 4.5.1, Leaflet 1.9.4 and the interface fonts are bundled with licenses and checksums. Only map tiles and explicitly configured integrations need external services. Health checks share a result for at most five seconds per process; the original check timestamp remains visible on hover. Mobile controls, weather and detailed health refresh only while displayed, immediately refreshing when reopened. The radio collector, packet retention and survey request cadence are unchanged.

## iPhone and Raspberry Pi options

On iPhone, open your private HTTPS dashboard in Safari and use Share → Add to Home Screen. The dashboard's Install on iPhone link walks through it. This version provides dashboard and controls; Bluetooth surveys remain Android-only. No Mac or App Store account is needed.

VM appliance builds are not part of this release. You can still install the Linux application inside your own supported Linux VM.

A [native Raspberry Pi image candidate](deploy/pi/README.md) targets Raspberry Pi Imager's **Use custom** option with a persistent `.img.xz` (or extracted `.img`). Native ARM64 build, first-use and filesystem checks pass. Physical Pi boot testing remains outstanding; candidates are experimental, not hardware-verified releases. This replaces the live-ISO plan.

## Thanks, MSPmesh

Thank you to the entire **MSPmesh community** for your help, guidance, support, knowledge, and friendships—and for being good people. This project is better because of you.
## Docker (preview)

Run the dashboard and optional collector in separate containers with persistent
storage. Build from source, configure through the wizard, then start locally:
see [Docker installation](docs/DOCKER.md). The image includes no deployment
credentials or personal data; external feeds and remote access remain optional.

Native iPhone/iPad dashboard-and-controls source is available in [ios/README.md](ios/README.md). This is an unbuilt source preview requiring Mac/Xcode validation and signing; the Safari installation remains the usable option today.
