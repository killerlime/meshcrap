# First use: from an empty dashboard to your receiver

Start with the [README quick start](../README.md#quick-start) on Linux with Python
3.11 or newer. The dashboard can run without a radio. There is no bundled private
node history, shared login, or preconfigured external feed.

## 1. Configure locally

Run `python meshcrap.py setup` in the activated virtual environment. Choose:

- **App title:** the name shown by your installation.
- **Data folder:** a persistent folder for your private database and settings.
- **Dashboard port:** accept 8080 unless another service uses it.
- **Radio now or later:** choose later to explore an empty installation safely.
- **Connection:** direct TCP radio or an already working Pi TCP bridge. This
  choice does not install a bridge, configure meshtasticd, or store SSH credentials.
- **Receiver identity:** enter the actual radio ID, including its leading `!`.
  The collector checks this before accepting the connection.
- **Labels:** optional display labels do not change radio channels or keys.
- **Private network access:** leave off for a first local test. If enabled, enter
  the server name used in the browser and the specific trusted client network.
- **RF sniffer:** optional and off by default. Link an independently installed
  sniffer through [its setup guide](RF-SNIFFER.md); the dashboard does not install
  or start an SDR receiver.
- **Second receiver:** optional reception comparison with a different radio.
  Setup saves its connection and display name; collection starts only when you
  explicitly run `collect-secondary`. Its history stays separate.

Review the prompts before saving. Replacing an existing configuration creates a
backup. Canceling keeps it unchanged. JSON users can copy `config.example.json` to
`config.json`, edit it, and run `python meshcrap.py init` instead.

## 2. Verify the empty dashboard

Run `python meshcrap.py check`, then `python meshcrap.py serve`. Open
`http://127.0.0.1:8080` on that same machine. Empty lists and no receiver connection
are expected before collection starts. The simulator uses hypothetical inputs;
it does not configure a radio. Do not confuse its results with observed coverage.

The command occupies its terminal. Keep it open, or use the documented service or
container deployment. A phone's `127.0.0.1` refers to the phone, not this server.

## 3. Start collection explicitly

After setting the receiver hostname, port and ID, restart the application to apply
configuration changes. In a second terminal, activate the same virtual environment
and run `python meshcrap.py collect`. Use one collector connection to the radio;
do not open a competing phone TCP connection to troubleshoot it.

Check collector connection status and the time of the latest saved packet. A
connected socket does not guarantee RF reception. Allow normal network activity
to arrive; setup does not require a broadcast, traceroute, or remote-admin probe.

## 4. Add phone access and optional features

Use [private remote access](REMOTE-ACCESS.md) before pairing phones or enabling
remembered devices. HTTPS is required for those persistent browser credentials.
Do not expose the dashboard directly to the public Internet. Keep control unlocks
and viewing permissions distinct. The Android survey app needs compatible server
support; review its matching version and device-test limitations before an outing.
The [iOS source preview](../ios/README.md) provides dashboard and controls; Bluetooth
surveying currently requires Android.

For a second dedicated radio, run `python meshcrap.py receiver-setup`, restart
the dashboard, and start `python meshcrap.py collect-secondary` in another
terminal. Use **Receiver comparison** to compare shared reception and paired
signal measurements. Startup history is excluded from RF comparisons. Each radio
has one connection owner; secondary controls, when explicitly enabled, reuse
that connection. See [receiver comparison](RECEIVER-COMPARISON.md) for setup,
interpretation and service installation.

Weather, external forwarding, terrain requests and receiver journal access have
separate opt-in configuration. See [terrain and Tropo sources](TROPO-SOURCES.md)
and [receiver diagnostics](RECEIVER-DIAGNOSTICS.md). Never paste keys into public
issues. Maps, regions and advanced connection options remain JSON settings;
the wizard does not yet cover every optional integration.

## If something does not work

For recorded connections, route comparisons and multi-node history, open
**Mesh explorer**. Empty evidence tables are normal on a new installation. The
long-term summary backfill runs in small batches. **Node map → Offline geography**
uses local outlines without external street tiles. See [the explorer guide](MESH-EXPLORER.md)
for interpretation, limits, storage and optional custom map packs.

| Symptom | Check first |
|---|---|
| Page will not open | Server terminal errors, selected port, and whether you are browsing on the server or another device. |
| Phone cannot reach it | Private network access, trusted hostname, allowed client network, HTTPS and network reachability. |
| Receiver identity mismatch | Radio ID from the device; do not disable the identity check. |
| Connection repeatedly drops | Another TCP client, bridge availability, network stability and receiver logs. |
| Connected but no fresh RF | Last packet time, modem/channel compatibility and antenna setup; a map marker alone is not current reception. |
| Action says locked | Unlock the existing dashboard controls; do not remove authentication to make the action work. |
| Empty or stale diagnostics | Source availability and displayed capture time; missing data is not a zero measurement. |

Back up the database consistently before migrations. Keep configuration, database,
pairing material, logs and keys private. Build and performance-test on a disposable
development system rather than the production collector.
