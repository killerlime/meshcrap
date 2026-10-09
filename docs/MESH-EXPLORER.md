# Mesh explorer

Open **Mesh explorer** in the sidebar. These views use retained collector records;
they never connect to a radio, send requests or change radio settings. Choose a
view, time window and node, then use **Refresh** when needed. Leaving the page
stops view requests. All existing dashboard workflows remain available.

| View | What it shows | Important limit |
|---|---|---|
| Connections | A clickable graph and sortable evidence table | Direct receptions and recorded traceroutes establish links. A relay byte alone cannot identify a node. |
| Route changes | Outbound/return paths, current counts and previous counts | Equal adjacent time windows; missing replies do not prove a node is unreachable. |
| Compare nodes | Up to six nodes' RF, battery, voltage or environmental readings | Select nodes with the checkboxes; use search to find more. Empty buckets remain gaps. |
| Long-term history | Daily distinct nodes, RF observations and direct observations | UTC days; reception copies count as observations. Initial backfill is gradual. |
| Message delivery | Recent dashboard submissions and matching recorded ACK/error evidence | Submission is not delivery. An ACK is not a human read receipt or confirmation for every broadcast recipient. |
| Performance | Dashboard memory and endpoint timing/response-size samples | The last 128 requests per endpoint in this process; server construction time excludes network transfer. |

Click a graph node to recenter; use **Node details** to open the existing drawer.
Graph steps describe recorded connections, not a packet's hop count. Blue edges
mean direct reception at the collector; gold edges mean a recorded traceroute.
Unidentified relay tags have their own candidate table. Unknown traceroute hops
stay unknown; the graph never bridges across them or guesses positions from RSSI.

RF comparisons describe the **last received radio hop**, not necessarily the
origin-to-receiver path. Zero is retained when measured; missing data is not zero.
MQTT and snapshot records do not become RF evidence. Telemetry points are bucket
means with observed minimum/maximum values in the table. They are not smoothed
predictions or measurements taken simultaneously by every node.

## Bounds and storage

Interactive requests have a 30-second cache and conditional responses. They read
at most 12,000 recent packet rows for connections, 1,000 traceroute rows for route
comparison and 6,000 rows per selected telemetry node. Limits are shown when
reached. Traceroutes use the collector's decoded records, including an available
return path; replies that were never recorded cannot be reconstructed.

The dashboard indexes 2,000 source rows at a time, at 30-second intervals, into
`<data_dir>/mesh-explorer-history.sqlite3`. The worker reads the collector database
without modifying it. Summaries retain per-node hourly reception counts and SNR
totals; daily distinct counts use a union of node IDs rather than adding hourly
counts. Daily views support up to ten years; hourly response detail is capped at
30 days. There is no automatic summary expiry. Raw-record retention is unchanged.

Back up this separate database with SQLite's backup API alongside the collector
database. It contains private node identities. **Purge node from DB** includes its
summary rows and backs them up; a subsequently observed node may appear again.
If you delete the summary database manually, stop the dashboard first. It will
rebuild only from remaining raw history, so summaries older than retained raw
records cannot be recovered. Retaining summaries does not retain full messages,
routes or raw telemetry forever.

Read queries have short deadlines. Busy/oversized history returns an error instead
of an unlimited scan. Performance measurements keep endpoint names and numbers;
they exclude query strings, credentials, message bodies and packet contents.

## Offline geography

On **Node map**, set **Base map → Offline geography**. The choice is remembered in
that browser. This removes external street tiles and displays a locally served
Natural Earth country-outline layer. Nodes and map controls remain usable; it is
coarse geography, not street-level navigation. The collector must still be
reachable for fresh node data. This is not an offline copy of the entire app.

For more detail, supply your own licensed UTF-8 GeoJSON FeatureCollection at
`<data_dir>/offline-map.geojson` and its attribution at
`<data_dir>/offline-map-attribution.txt`. Only geometry is displayed; properties,
remote icons and HTML are not used. Limits: 5 MiB, 10,000 features, WGS84
longitude/latitude coordinates. Point, line and polygon geometries are supported.
Use geographic coordinates, not projected meters. Keep any required license and
source notices with your pack. Restart the dashboard or allow the cache to expire
after replacing it. No map-pack builder, automatic tile download or tile prefetch
is included; comply with the source's distribution and offline-use terms.

## Provenance

Meshyface's functional ideas helped identify these workflows:
https://github.com/jaronmcd/meshyface. Its GPL-3.0 source and assets are not copied,
bundled or imported. This implementation is independently written for Meshcrap's
existing collector and browser libraries. There is no Meshyface dependency.

Bundled coarse geography comes from Natural Earth, whose data is public domain:
https://www.naturalearthdata.com/about/terms-of-use/. Source and transformation
details are recorded in `THIRD_PARTY_NOTICES.md`. Existing library licenses still
apply; this feature does not change their terms.
