# Dashboard refinements

The dashboard now has a compact overview, reorderable sidebar navigation, and per-panel refresh controls. Automatic refresh waits during editing, selection, and map interaction. Pausing a panel keeps its displayed results; manual refresh remains available.

Insights separates measured traffic from modeled improvements. What-if uses three primary choices, one layered traffic map, and collapsed advanced assumptions. Simulation controls never change radio settings. The role comparison covers current and legacy roles with explicit model limits.

The Heard by report card summarizes reports, external nodes, exclusive/shared nodes, diversity per report, and directory freshness. Exclusivity is limited to the fetched sample; diversity is not delivery efficiency or uptime. The portable build retains its existing disabled external-directory policy.

The map appears before coverage totals, uses canvas vectors and quiet markers, and starts without grids or range rings. Select a grid without moving the viewport; use View selected grid to move deliberately. Node responses are reused for 30 seconds and grid responses for 60 seconds, in memory only. Concurrent fetches are shared.

## Optional Windows relay watchdog

Run tools/Install-RelayWatchdog.ps1 in Administrator PowerShell on the relay host, specifying -ListenAddress and -TargetAddress, with optional -Port (4403 by default). It installs a SYSTEM task for startup and every three minutes. The task restores only its configured missing portproxy listener, preserves a changed forwarding target, and does not probe or configure the radio or restart the network service. No private addresses or host names are included. This installer is opt-in; repository installation does not run it.

## Integration validation

Local checks cover frontend syntax, source privacy, phone surveys and survey evidence, role modeling, refresh behavior, map response reuse, ingestor metrics, and telemetry/firmware scenarios. The relay installer is parsed without installing a task. Linux installation checks remain in CI.
