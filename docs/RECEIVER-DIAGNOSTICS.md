# Receiver log diagnostics

Optional passive journal integration. It does not connect to the Meshtastic API,
request telemetry, transmit packets, restart the receiver, or change radio settings.

## UI

- Debug Logs: receiver radio service in the existing selector; existing unlock,
  time windows, search, and levels remain. Load older pages using journal cursors.
  Warnings are classified from meshtasticd's embedded severity as well as journal priority.
  Long entries are explicitly marked truncated; credentials are redacted.
- RF analysis: retained 48-hour CRC/decode/eviction/disconnect counts and hourly table.
  Counts are not packet-loss percentages. Empty/unavailable logs do not become zero.
- Nodes: last capacity observed at an eviction, with an explanation distinguishing
  the receiver node list from the collector's historical database.
- System: recorded collector failures and latest connection event, explicitly historical.

## Private deployment prerequisites

The dashboard host needs read-only SSH access to the receiver journal. Reuse an
existing appropriately restricted connection if available. Otherwise provision a
separate key restricted to this reader; do not reuse an unrestricted admin key.

Install source/receiver_log_reader.py on the receiver at a fixed absolute path.
In authorized_keys, use a forced command invoking that Python script, with the
OpenSSH restrict option (no port forwarding, agent forwarding, PTY or user rc).
The receiver account must already be permitted to read meshtasticd's journal.
The reader accepts only validated log queries and a fixed summary query.
Do not enable a new HTTP endpoint or radio listener on the receiver.

Privately create DATA_DIR/receiver-log-access.json, readable only by the dashboard
account, with string fields: host, user, identity (absolute private-key path), and
known_hosts (absolute pinned host-key file path). Never commit this file, keys,
trust material, captured logs or station-specific configuration. Verify the
receiver host-key fingerprint out of band; never use accept-new or disable checking.

Use a literal hostname/IP and username, plus existing absolute key/trust paths
without spaces, control characters or OpenSSH percent expansions. This integration
does not load the user's SSH configuration or accept connection options in these
fields; its pinned connection options and remote journal command remain fixed.

Back up current dashboard files and compare them with the fetched baseline before
installing changed files. Register receiver_diagnostics in app.py and load its JS
as provided in source. Preserve existing dashboard access controls. Reload only
the dashboard after reviewing the final diff; do not restart the collector or receiver.
Verify unlocked and locked log requests, pagination, unavailable/stale states,
and collector continuity on the deployed Linux app.

## Resource bounds and missing data

Receiver logs load on demand, at most 500 scanned records per page. The warning
filter can return an empty page that still has an older cursor. A summary scans at
most 100,000 retained entries over 48 hours and is cached for five minutes while
viewed. Partial scans, earliest retained record and capture time are displayed.
Raw messages stay out of summary responses. SSH failures retain any earlier
summary with a stale label; they never display new zero counts. No new scheduler
or periodic radio requests are introduced.

## Validation

Run tests/receiver_diagnostics_test.py with Flask available, tests/privacy_check.py,
and tests/frontend.py. The full app smoke test requires Linux (fcntl).
Use synthetic data for UI previews; never include real logs in public fixtures.
