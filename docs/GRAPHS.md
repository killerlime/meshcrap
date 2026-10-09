# Graphs

Open **Graphs** in the left menu and choose the shared time window. Click a
chart legend to hide or show a series. Hover for an exact local timestamp.
The existing reception chart remains available in LNA test.

Use **Device mode** to filter originating nodes by their latest reported role.
**Nodes** offers all nodes, local only or exclude local. Local nodes have a
long or short name starting with the prefix configured during setup. These
filters combine and are saved in this browser. Unknown roles have their own
option. The metadata describes latest known roles and names, not the mode at
the time of an old packet. Observation time and HQ-wide channel-health readings
are preserved when filtering node evidence.

The charts reuse the collector's hourly RF-health and recorded LNA experiment
data. They show eligible observations within the selected window; they do not
invent missing hours or expand the experiment's available history. Excluded
and incomplete hours stay blank. Expand **Hourly data & exclusions** to inspect
the underlying values and exclusion reasons.

- **Unique nodes heard each hour:** distinct originating nodes heard in each
  hour and the subset heard directly, with packets per node per observed hour
  on a separate axis. The latter divides observed-hour packet rate by that
  hour's distinct-node count. Missing data or zero nodes produces no ratio.
  Hourly node counts overlap: adding them does not yield distinct nodes across
  the entire selected window. A node heard directly may also be heard relayed.
- **Reception:** packets and direct packets per observed hour, plus unique
  nodes on a separate right axis. Rates account for recorded observation time;
  node counts are counts, not rates.
- **Signal:** median and lower-decile (P10) SNR of received packets. This is
  reception at the collector, not necessarily signal from the originating node
  on a relayed path.
- **Channel activity & bad packets:** channel utilization, reported RX bad
  share and transmit airtime utilization. Missing measurements remain missing.

Recorded LNA changes appear as markers and shaded periods. The page makes no
radio requests or configuration changes.

## Relationships to explore

The table calculates Pearson correlation from completed eligible hours,
separately for LNA ON and OFF. Each comparison requires at least 12 finite
paired values. Missing or constant data produces no coefficient. The paired
hour count is shown so a small sample is visible.

A coefficient describes how two hourly measurements moved together. It does
not establish a cause, statistical significance, independent samples, or
successful bidirectional communication. Time series can be autocorrelated;
traffic, time of day, relay paths and weather can affect both measurements.
Unique-node counts and packet rates share the same traffic, so a strong
association between them is expected.

The unique-node versus signal comparison can help identify hours where more
nodes coincided with different received signal levels. A different mix of
nodes or last-hop relays can change that signal distribution, so this is a
starting point for investigation rather than a coverage measurement.

This is evidence of what the collector received. Unreceived transmissions,
other receivers and failed routes are not fully visible here. A high reception
rate is not proof that a travelling node can communicate with the mesh.

## Efficiency and future comparisons

The page uses existing passive APIs, performs the small correlation calculations
in the browser and reuses chart instances. Automatic refresh runs every two
minutes while the view is visible, subject to the dashboard's shared refresh
controls. No new background RF collection is added.

Future comparisons could align weather, noise-floor, propagation and survey
route evidence to the same observed hours. Those would need explicit source
coverage, freshness and receiver checks; they are not part of this first view.

Charts use the project's existing Chart.js dependency and LNA overlay. No new
third-party dependency or external data service is required.
