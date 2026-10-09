# Optional receiver comparison

Compare two independently located Meshtastic receivers on a shared mesh. This is
optional and off on a new installation. It adds no external service dependency,
PKI polling, scheduled radio requests or external-feed uploads.

## Quick setup

1. Dedicate a second network-accessible radio to this collector. Close other
   network clients using that radio; Meshtastic connections should have one owner.
   The primary and secondary must be different physical radios, even if you use
   different DNS names or relay ports for them.
2. Run `python meshcrap.py receiver-setup`. Enter your own host, TCP port, expected
   node ID and display label. Keep secondary controls off unless you want them.
   The wizard preserves unrelated settings and asks before saving. It never
   contacts either radio or starts services.
3. Run `python meshcrap.py collect-secondary` separately from the primary
   collector. For a background Linux installation, review the optional
   [secondary service](../deploy/meshcrap-secondary.service), set its paths/user to
   match your installation, and enable it explicitly. Restart the dashboard to
   apply the saved configuration. Configuration alone does not start collection.
4. Open **Receiver comparison** in the dashboard. Start with a short window and
   allow shared history to accumulate. Longer windows become useful as both
   collectors stay online. The page also works at `/receiver-comparison`.

The ordinary configuration JSON is another option:

```json
{
  "secondary_enabled": true,
  "secondary_radio_host": "receiver.example.test",
  "secondary_radio_port": 4403,
  "secondary_receiver_id": "!23456789",
  "secondary_label": "Secondary",
  "secondary_enable_controls": false
}
```

These are documentation examples, not real receiver settings. Configuration and
runtime data belong outside the published source. A known nonzero node ID is
required. An identity mismatch closes the connection and exits with status 78;
fix the configuration before starting it again. Ordinary transport failures
reconnect with a delay. A quiet RF period does not cause a reconnect.

## What the comparison means

**Both**, **primary only** and **secondary only** count packet episodes with the
same sender, packet ID, destination, port and payload identity within two minutes.
Repeated copies of that episode count once. A packet without usable identity is
reported separately. Channel slot numbers are local to each receiver and are not
treated as a shared channel identity.

The signal table reports median **secondary minus primary** SNR and RSSI on paired
packets. Zero readings are valid. Direct-at-both packets provide the clearest
comparison. Relayed readings describe each receiver's last hop, which can differ.
Antenna, cable, placement and receiver calibration also affect these differences.

The activity chart uses only whole time bins during continuous simultaneous
collection. Missing collection periods are excluded instead of filled with zero.
A correlation coefficient requires at least 12 complete bins with varying counts.
It describes shared changes in activity, not their cause. One receiver not
observing a packet does not establish failed reception or transmitter reachability.

Current cached modem profiles provide context. The alignment notice does not
compare channel keys, prove shared decryption, or validate all historical settings.
Packet matching still requires the same payload. Avoid mixing intentional modem
or antenna changes into one comparison window without noting that context.

## Startup data and history

The secondary stores its history in `data_dir/secondary/mesh.db`. It does not write
its receptions into the primary database. A cached startup node snapshot supplies
names and metadata; it creates no RF observations. Collection callbacks are
accepted only after identity verification and the completed startup snapshot,
from the collector's active verified interface.

Each saved packet has provenance:

| Value | Meaning | Included in RF comparison? |
|---|---|---|
| `LIVE` | Valid receiver time within the collection session | Yes, with the other RF checks |
| `BUFFERED` | Receiver time precedes the session by more than five seconds | No |
| `CLOCK_SKEW` | Receiver time is more than one minute after arrival | No |
| `UNDATED` | Receiver time is missing, invalid or nonpositive | No |

Excluded packets remain auditable in local history. Own-node traffic, MQTT,
internal transport, wrong receiver identities and packets outside simultaneous
collection periods are also excluded. Fresh RF NodeInfo packets do count;
metadata snapshots are different from live NodeInfo traffic. Local telemetry is
shown separately as context and is never counted as external RF reception.

Each collector writes a private heartbeat. Open collection intervals stop at the
last known heartbeat, including after an abrupt exit. Historic rows without a
receiver time cannot establish a comparison. No migration invents live RF data.

## Controls, privacy and efficiency

Controls use the secondary collector's existing connection through a private
Unix socket. They require both `enable_radio_controls` and
`secondary_enable_controls`, along with the dashboard's existing unlock, Origin
and private-network protections. Routine requests occur only when you explicitly
use dashboard controls. Automatic refresh reads local stored data only.

Secondary submitted messages stay in its own `web_sent_messages` table, separate
from received RF packets. Settings backups stay in its own private directory.
Secondary actions do not invoke primary external-feed capture or pause hooks.
Channel keys and full security configuration are excluded from comparison
profiles. The read-only comparison API returns summaries, never raw payloads.

Queries stream at most 10,000 candidate observations per receiver per window;
results explicitly indicate when partial. Raw payloads are replaced by digest
identities in memory, and nearest-time pairing avoids a quadratic duplicate
search. Correlation is withheld for truncated packet windows. Recent collection
events/sessions, telemetry and node labels are bounded too. Four windows are
cached for 15 seconds; refresh runs only while the view is visible and respects
pause/editing controls. These limits bound work rather than deleting saved data.

## Troubleshooting

- **No menu item:** enable the secondary receiver locally and restart the
  dashboard. RF sniffer integration is a different optional feature.
- **Offline:** check the secondary service and private host/port. A stale
  heartbeat does not erase previously observed overlapping history.
- **Identity mismatch:** correct the expected node ID or endpoint. The collector
  stops without repeatedly opening the wrong radio.
- **No overlap:** both collectors need verified sessions during the selected
  window. Old cached nodes are not evidence of simultaneous reception.
- **No correlation yet:** collect more complete bins. Fixed counts, gaps and
  truncated windows cannot support the displayed coefficient.
- **Settings differ:** compare region, frequency, preset or custom modulation on
  both radios. Channel keys remain private; this screen does not verify them.
- **Controls unavailable:** enable both control switches, unlock the dashboard,
  and confirm the secondary collector owns its radio. Do not open another client
  to try to repair the control path.

## Source and validation

This is Meshcrap's own generic implementation, distributed under this repository's
license. It uses the existing Meshtastic Python SDK, protobuf, PyPubSub, Flask and
SQLite dependencies; no third-party receiver comparison project is bundled.
See [building and dependencies](BUILDING.md) and [third-party notices](../THIRD_PARTY_NOTICES.md).
The focused test suite uses synthetic receivers and packets, including cached
bootstrap exclusion, identity mismatch, separate history, control authorization
and no-feed behavior. Hardware placement, clock accuracy and real RF correlations
must still be validated on the operator's deployment with sufficient shared data.
