# RF quality roadmap — ideas for later

**Planning only. No new radio traffic, collection changes, or RF scoring is enabled by this document.**

Make the observations more trustworthy before adding more conclusions. These are proposed features, not claims about what the dashboard already does.

| Priority | Idea | Data and guardrails | Useful result |
|---|---|---|---|
| 1 | Measurement provenance | Record receiver, transport, actual observation time, firmware/configuration epoch, and field source. Keep imported metadata separate from locally measured RF. | Explain where each number came from and whether two observations can be compared. |
| 1 | Honest link attribution | Separate direct reception from relayed traffic; retain ambiguous relay identities as unknown. Receiver RSSI/SNR belongs to the received radio link, not automatically the originating node. | Avoid assigning a relay's strong signal to a distant sender. |
| 1 | Collection completeness | Track connected observation minutes, gaps and restarts. Normalize counts by observed time; distinguish a disconnected collector from a quiet network. | Traffic-drop explanations with visible uncertainty. |
| 1 | Robust summaries | Show sample count, median, lower/upper percentiles and time coverage. Preserve missing readings as missing, not zero. Keep raw data immutable. | Fewer misleading averages and isolated best-packet claims. |
| 2 | Noise context | Align available receiver noise-floor samples with packets using bounded sample age. Show age, hardware/firmware support and missingness. Do not infer a calibrated noise floor by blindly subtracting packet SNR from RSSI. | Signal changes alongside independent noise observations. |
| 2 | Fair LNA comparisons | Match shared direct senders, time windows, modulation/configuration and receiver uptime; annotate hardware changes and transitions. Report effect size, sample balance and uncertainty, with an inconclusive state. | Evidence about reception under comparable conditions, not a claim that extra packets prove improvement. |
| 2 | Airtime and congestion context | Separate channel utilization from local TX airtime and decoded packet counts. Handle cumulative-counter resets across reboots. Channel utilization alone cannot identify an interferer. | Explain busy-channel periods without pretending to know their cause. |
| 2 | Coverage evidence quality | Track sample age, count, position age/accuracy and direct-versus-relayed support per cell. Distinguish fixed observations from mobile survey observations. No observations means unknown, not no coverage. | Evidence-based coverage with confidence and freshness indicators. |
| 3 | Configuration-aware link margin | Only estimate a margin when spreading factor, bandwidth, coding rate and hardware sensitivity assumptions are known; label assumptions and uncertainty. | An optional engineering estimate, never a universal good/bad RSSI threshold. |
| 3 | Long-term trends | Keep hourly/daily aggregates with counts, collection completeness and configuration epochs; retain enough raw evidence to audit results. | Months of useful trends without mixing incompatible setups or unbounded storage. |

## Implementation order

Start with provenance, completeness and summary statistics. Validate against synthetic fixtures containing missing samples, duplicate packets, counter resets and disconnects. Then compare old and proposed calculations on a read-only copy of collected data. Publish the assumptions and examples before changing defaults. Additional polling or active tests need a separate decision, especially for solar nodes.

## Primary references to revisit when implementing

- [Meshtastic telemetry definitions](https://github.com/meshtastic/protobufs/blob/master/meshtastic/telemetry.proto): noise-floor and local statistics fields; channel utilization and TX airtime have different meanings.
- [Meshtastic packet overview](https://github.com/meshtastic/meshtastic/blob/master/docs/about/overview/index.mdx): received packet metadata and mesh forwarding context.

Firmware support and field presence must be checked against the actual installed versions; an upstream field does not guarantee every radio supplies a valid measurement.
