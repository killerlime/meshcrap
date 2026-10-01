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


## Research notebook: 915 MHz ISM, LoRa, and Meshtastic

Research checked October 1, 2026. This section records principles, implementation ideas and open validation work. It does not change the collector, radio settings, request cadence or existing historical data. Sources are primary documentation and engineering literature; examples below are calculated illustrations, not measurements of a user's installation.

### 1. The band is shared, and “915 MHz” is a label

For the US context, the relevant span is 902–928 MHz, not one fixed 915 MHz channel. Applicable operating conditions depend on the equipment and authorization. A preset's power limit is not a blanket legal approval for any amplifier, antenna or modulation configuration. In particular, the conditions in §15.247 differ for hopping and digitally modulated systems; do not turn its one-watt provisions into a universal Meshtastic recommendation. Part 15 operation must accept interference and may not cause harmful interference. Other countries need their own region rules. [FCC §15.247](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-C/section-15.247), [FCC §15.5](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-A/section-15.5).

**Backlog:** RF-01 — Store configured region and effective frequency with an observation epoch. Show configured power separately from measured output and calculated radiated power. Never auto-increase power or label a setup compliant from telemetry alone. Acceptance: missing antenna/certification information remains unknown.

### 2. LoRa is the radio modulation; LoRaWAN is a different network layer

LoRa uses chirp spread spectrum. LoRaWAN adds its own network architecture and procedures; Meshtastic implements its own mesh behavior over LoRa. LoRaWAN regional channel plans, adaptive-data-rate procedures and gateway assumptions should not be copied into Meshtastic analytics as though they were the same protocol. [Semtech LoRa overview](https://www.semtech.com/lora/what-is-lora), [Meshtastic overview](https://github.com/meshtastic/meshtastic/blob/master/docs/about/overview/index.mdx).

**Backlog:** RF-02 — Add a short glossary distinguishing radio frequency, modem preset, logical channel, mesh role, and internet transport. Acceptance: the UI never uses “channel” ambiguously when diagnosing a mismatch.

### 3. The chirp: what travels over the air

A chirp sweeps instantaneous frequency over the occupied bandwidth. LoRa symbols use cyclic shifts of this sweep, wrapping at a band edge. With spreading factor SF there are 2^SF symbol choices, and ideal symbol duration is T = 2^SF / bandwidth. A conceptual receiver multiplies by an opposite reference chirp and finds a frequency-bin peak to identify the symbol. Preamble synchronization and frequency/timing offsets matter. Longer symbols support sensitivity at the cost of airtime; they are not magic immunity to collisions. This explanation concerns the PHY, not encryption. [Maleki et al., CSS tutorial](https://arxiv.org/html/2310.10503v1).

Calculated example: at 250 kHz bandwidth, SF7 gives 0.512 ms per symbol, SF9 gives 2.048 ms, and SF11 gives 8.192 ms. These are symbol durations, not whole-packet transmission times. SF is not simply the count of chirps in a packet.

**Backlog:** RF-03 — An optional “See the chirp” explainer with synthetic frequency-versus-time animation, symbol shift, dechirped peak, and SF/BW controls. Clearly label it synthetic: the collector does not provide raw IQ samples or a captured RF waveform. Respect reduced-motion settings; sound, if ever added, is an illustrative frequency translation, not audible 915 MHz. Acceptance: duration calculations match fixtures, and the animation never masquerades as a live spectrum display.

### 4. Sensitivity, coding, bandwidth and airtime

Spreading factor and coding rate both involve airtime tradeoffs, but are not interchangeable. More spreading can improve sensitivity; added coding redundancy can improve resilience to some corruption. Narrower bandwidth changes sensitivity and oscillator requirements. Avoid a single universal RSSI cutoff for every modem and board. [Semtech modulation FAQ](https://www.semtech.com/design-support/faq/faq-lora).

**Backlog:** RF-04 — Versioned packet-airtime estimator using effective SF, bandwidth, coding rate, preamble, payload length, header/CRC choices and low-data-rate optimization. Include protocol overhead and retransmissions when available; do not substitute message character count for transmitted bytes. Label estimated values. Acceptance: compare with firmware/vendor formula fixtures over several payload sizes and settings, and refuse a precise estimate when required fields are missing.

### 5. Why negative SNR can still decode

LoRa reception can work at negative packet SNR because spread-spectrum processing distinguishes the wanted signal even when its in-band power is below noise. This does not mean arbitrary negative values are usable or that RSSI, packet SNR and idle noise-floor readings are interchangeable. [Semtech long-range explanation](https://blog.semtech.com/long-range-with-lora).

**Backlog:** RF-05 — Replace generic Wi-Fi-like quality thresholds with modem-aware explanations. Show lower-tail SNR, count and sample age alongside the median. Successful packets are a biased sample: the receiver cannot report the SNR of every packet it failed to decode. Acceptance: no calculated delivery-success percentage without a trustworthy sent-packet denominator.

### 6. Frequency slot is not logical channel slot

Meshtastic's frequency slot chooses the RF center frequency within the region/preset. Automatic selection can depend on the primary channel's name; rearranging which channel is primary can therefore change RF tuning when frequency is automatic. A logical channel's name/key relates to message decoding, not a second simultaneous radio frequency. Compare effective frequency and modem settings separately from logical channel compatibility. [LoRa configuration](https://meshtastic.org/docs/configuration/radio/lora/), [channel configuration](https://meshtastic.org/docs/configuration/radio/channels/).

**Backlog:** RF-06 — Configuration-change timeline and read-only mismatch explainer. Track effective frequency, SF, bandwidth, coding rate, primary index and manual/automatic selection. Redact private channel names and never log keys. Do not claim the remote side matches when its configuration is unknown. Acceptance: a synthetic primary-channel reorder explains a possible RF change without automatically blaming it for a traffic drop.

### 7. Propagation is more than a circle on a map

Free-space loss is an ideal unobstructed baseline, not a coverage prediction. Using L = 32.44 + 20 log10(f_MHz) + 20 log10(d_km), calculated 915 MHz loss is about 91.7 dB at 1 km and 111.7 dB at 10 km. Terrain and obstacles can add diffraction loss; a visibly clear straight line does not establish adequate Fresnel clearance. [ITU-R P.525](https://www.itu.int/rec/R-REC-P.525-5-202411-I/en), [ITU discussion of diffraction and Fresnel clearance](https://www.itu.int/dms_pub/itu-r/opb/rep/R-REP-RA.2259-2012-PDF-E.pdf).

**Backlog:** RF-07 — Optional terrain/profile work after provenance is solid. Record antenna height above ground separately from elevation above sea level; distinguish modeled paths from observed links. Missing or stale mobile positions must not create precise paths. Terrain data alone omits buildings and vegetation. Acceptance: measured coverage and modeled feasibility use distinct layers and legends.

### 8. Antennas, feedline and installation context

A useful future link-budget record needs antenna gain/pattern, polarization, feedline loss, mounting height and orientation; a claimed antenna gain alone is insufficient. The upstream site planner already exposes several such inputs and is a useful reference for scope rather than something to duplicate wholesale. [Meshtastic Site Planner](https://site.meshtastic.org/).

**Backlog:** RF-08 — Optional installation notes with timestamps, cable/connector changes and known versus assumed values. Compare like configurations; do not infer antenna performance from a single distant reception. Acceptance: configuration changes split comparisons instead of silently mixing data.

### 9. LNA, filter and overload are a system problem

An external LNA changes gain and cascaded noise figure; more indicated RSSI alone does not establish better reception. Front-end filtering can suppress blockers before they create amplifier intermodulation, but passive loss ahead of amplification can worsen sensitivity. Which placement helps depends on the chain and interference environment. [Analog Devices external-LNA tradeoffs](https://www.analog.com/en/resources/technical-articles/improving-receiver-sensitivity-with-external-lna.html), [receiver selectivity](https://www.analog.com/en/resources/technical-articles/use-selectivity-to-improve-receiver-intercept-point.html), [noise-figure analysis](https://www.analog.com/en/resources/technical-articles/system-noisefigure-analysis-for-modern-radio-receivers.html).

**Backlog:** RF-09 — Record filter order, insertion loss if known, LNA state and transitions; compare shared direct senders over balanced windows. Use alternating test periods only in a separately approved experiment. Show noise and lower-tail reception together. Acceptance: label an apparent overload/interference pattern a hypothesis, never a confirmed diagnosis without appropriate measurements.

### 10. A mesh route is not a permanent wire

Broadcast managed flooding, duplicate suppression and acknowledgements affect how many packets a collector sees. Direct-message routing has firmware-dependent behavior. Hearing a rebroadcast or local acknowledgement does not establish that every distant recipient received the message. [Meshtastic mesh algorithm](https://meshtastic.org/docs/overview/mesh-algo/).

**Backlog:** RF-10 — Keep raw receptions distinct from unique origin packets; preserve duplicates as observations while avoiding inflation of message counts. Key deduplication by sender, packet ID and bounded time rather than packet ID forever. Separate local submission, radio acceptance, mesh acknowledgement and destination acknowledgement in the UI. Acceptance: replayed packets, restarts and identifier reuse do not create false delivery claims.

### 11. Traceroute is a diagnostic snapshot

Traceroute can miss intermediate identities when a node cannot decrypt the channel or firmware support differs. The unknown sentinel does not identify one particular physical repeater. A trace describes an observed traversal, not every possible route; forward and return observations can differ. Requests consume airtime and should not become an aggressive monitoring loop. [Meshtastic traceroute documentation](https://meshtastic.org/docs/configuration/module/traceroute/).

**Backlog:** RF-11 — Show direction, observation time, channel context and missing-hop uncertainty. Never merge all unknown hops into one map node. Keep active surveys opt-in and conservative. Acceptance: unavailable identities remain unknown and route changes do not imply a radio went down.

### 12. Internet data is not local RF evidence

MQTT can bridge mesh data through the internet. A node record or message arriving through an internet integration is not proof that the local receiver heard it over LoRa. [Meshtastic MQTT configuration](https://meshtastic.org/docs/configuration/module/mqtt/).

**Backlog:** RF-12 — Preserve transport provenance through exports, summaries and map cells. Let users inspect remote information without mixing it into local RF totals. Acceptance: external-only metadata cannot advance local RF last-heard, packet counts or demonstrated coverage.

### 13. Noise, utilization and solar cost

Telemetry definitions distinguish channel utilization, TX airtime, relay counters and noise floor. Field availability is firmware/hardware dependent, and a default scalar value need not mean a valid measurement. [Meshtastic telemetry schema](https://github.com/meshtastic/protobufs/blob/master/meshtastic/telemetry.proto).

**Backlog:** RF-13 — Capture capabilities and field presence, use passive telemetry first, and handle reboot/reset epochs before calculating counter rates. Estimate diagnostic airtime before offering active requests; show battery trend with solar/time-of-day context. No extra PKI probing, no automatic higher polling cadence, and no claim that a software utilization metric is a calibrated spectrum analyzer.

### 14. Interference research needs separate evidence

Receiver performance depends on blocking, desensitization and nonlinearity as well as sensitivity. An unexpected noise rise does not identify a transmitter or prove deliberate interference. [NTIA/MITRE interference-resilient receiver guidance](https://www.ntia.gov/sites/default/files/2025-08/best-practices-for-designing-interference-resilient-rf-receiving-systems.pdf).

**Backlog:** RF-14 — Later, allow an optional separately captured spectrum observation with instrument settings, bandwidth and timestamps. Keep it separate from decoded-packet statistics. Correlate conservatively, and require matched observation periods before attributing changes. Raw IQ processing and automated interference identification are out of scope for the first pass.

## Questions parked for a later session

- Which hardware/firmware actually supplies meaningful noise-floor and counter fields?
- Which measurements should be retained raw, and what is the disk budget for months of history?
- Are antenna/filter changes recorded accurately enough for matched comparisons?
- Is a passive explanation sufficient, or is a controlled on-air experiment worth its airtime and solar cost?
- Should the chirp explainer be a standalone learning panel or part of metric help?

No answers are required tonight. Prioritize RF-01, RF-05, RF-06 and collection completeness first; the visual chirp explainer and terrain/spectrum integrations can follow after the measurements are trustworthy.


## RF-15 — Regional ducting and environmental correlations

**Deferred research and implementation.** Add a location/region-based time-slider map that places atmospheric conditions beside actual RF observations. Separate three layers: forecast potential, observed atmospheric profiles, and observed radio changes. A favorable forecast is not proof that a particular 915 MHz path ducted.

### Atmospheric data and a defensible ducting indicator

Vertical temperature and moisture structure can produce anomalous refraction; a surface thermometer and humidity sensor cannot establish that vertical structure. NWS describes superrefraction and ducting associated with temperature inversions and sharp moisture gradients. Weather-radar anomalous propagation is supporting context, not proof of a Meshtastic link enhancement at another frequency and antenna height. [NWS radar propagation guidance](https://www.weather.gov/mlb/Doppler_Dual_Pol_Weather_Radar).

Evaluate observed radiosonde profiles and a regional numerical model such as HRRR. Soundings measure upper-air conditions; models supply gridded estimates with their own horizontal and vertical resolution limits. Store whether a record is an observation, analysis or forecast, plus initialization time, valid time, lead time, altitude coordinate, units, resolution and quality flags. [NWS upper-air observations](https://www.weather.gov/hnx/upperair), [NOAA HRRR](https://rapidrefresh.noaa.gov/hrrr/), [NCEP HRRR products](https://www.nco.ncep.noaa.gov/pmb/products/hrrr/).

Use ITU-R P.453 as the reference for refractivity calculations and investigate vertical modified-refractivity gradients and layer height/thickness. Do not declare ducting from surface humidity, pressure or an inversion alone. Thin layers may be unresolved; matching a forecast layer to a specific path needs antenna heights and frequency-dependent propagation analysis. [ITU-R P.453](https://www.itu.int/rec/R-REC-P.453-14-201908-I/en).

### Regional map and history

- Start with one configured region; fetch bounded geographic subsets and cache by valid time. Avoid downloading full model archives for every dashboard refresh.
- Show a separate potential/uncertainty overlay, atmospheric profile locations and heights, and measured direct-link observations. Use gaps or hatching for unavailable data, not zero potential.
- Preserve forecast issue time for honest retrospective tests. Do not use later analyses as though they were forecasts available before an event.
- Keep regional weather coordinates coarse where possible; never upload private node positions or histories merely to fetch weather.
- Compare corridors between known direct endpoints, not only weather above the receiver. For relayed traffic, do not treat sender-to-receiver distance as a direct RF path.
- Retain event summaries and source identifiers for months; choose storage limits and archive availability before promising historical replay. Respect source attribution, access limits and licensing. Evaluate third-party ducting forecasts later, without assuming scraping or redistribution rights.

### Correlation method

Predefine outcomes: shared direct-sender SNR/RSSI distributions, number of direct senders per connected receiver-hour, and reliably located direct-distance percentiles. Longest reception alone is too fragile. Match configuration epochs, hour of day, season, source population and collector completeness; exclude imported/MQTT-only observations. A new relay, mobile trip or channel change is an alternative explanation.

Use matched non-event periods and fixed lag windows; report sample counts, effect sizes, uncertainty and failed/neutral comparisons. Account for serial correlation with day/event blocks rather than treating every packet as independent. Searching many weather variables, regions and lags creates false positives: keep exploratory results labeled, use multiple-comparison controls and test promising findings on held-out later events. A receiver cannot prove improved delivery rate without a sent-packet denominator.

Example future wording: “Direct receptions increased during modeled favorable conditions; the evidence is limited by sparse upper-air observations.” Never “Ducting caused this” from coincidence alone.

### Other weather/environmental candidates

| Candidate | Hypothesis to test later | Guardrail |
|---|---|---|
| Temperature inversions, moisture gradients, boundary-layer changes and fronts | Association with unusual direct-link ranges or signal distributions | Require vertical-profile context; surface readings alone are insufficient. |
| Dew point, fog, rain, snow, ice and wet vegetation | Association with changes in a particular installed path or antenna system | Distinguish propagation, wet obstructions, antenna effects and hardware faults; do not assume rain attenuation is the explanation. |
| Wind and gusts | Antenna movement, changing foliage paths or intermittent connections | Treat as competing installation hypotheses, not a remotely confirmed fault. |
| Sunshine, cloud cover and day length | Solar-node availability or battery changes alter who transmits | Separate energy/traffic effects from propagation effects. |
| Ambient and device temperature | Temperature-associated drift or receiver/host behavior | Use actual device temperature when available; ambient temperature is a proxy. |
| Storms and lightning | Correlation with noise bursts or outages | Missing packets alone do not identify lightning interference. |
| Seasonal foliage and ground conditions | Slow path changes | Require long records and matched hardware configurations. |

The ITU rain-attenuation model P.838 specifies a frequency range beginning at 1 GHz; do not silently extrapolate it to 915 MHz or import microwave assumptions unchanged. [ITU-R P.838](https://www.itu.int/rec/r-rec-p.838-3-200503-i/en). Each candidate above is a hypothesis requiring validation, not a claimed effect in the existing data.

### Deliverable order and acceptance

1. A small offline study using a read-only RF export and archived weather, with no new radio requests.
2. A reproducible regional map/event timeline showing data provenance and missing periods.
3. A correlation report with matched baselines, uncertainty, confounders and inconclusive outcomes.
4. Only after useful validation, an optional dashboard feature; no automated channel/power changes or weather-triggered probing.

Questions about geographic scope, data providers, storage and display can wait for the next planning session.


## RF-16 — Optional local ADS-B / PiAware comparison

**Backlog only, alongside RF-15.** Explore a read-only connection to a user-configured LAN receiver running PiAware/dump1090-fa. Prefer its local data over a FlightAware website scrape or cloud API. No receiver discovery scan, account connection, decoder changes or additional upload is enabled by this plan; identify the installed software and endpoint later.

FlightAware's dump1090 documentation describes `receiver.json`, `aircraft.json` and `stats.json`; exposure through HTTP depends on the local webserver. Available fields include source time, recent aircraft positions, position age, message counters, signal values and indicators for MLAT/TIS-B-derived fields. Its RSSI is expressed in dBFS, not Meshtastic's dBm. Fields can be absent and counters reset. [FlightAware JSON format reference](https://github.com/flightaware/dump1090/blob/master/README-json.md), [PiAware project](https://github.com/flightaware/piaware).

### Proposed adapter

- Explicit local base URL in private configuration; disabled by default. Read receiver metadata once, then use a modest, configurable cadence for current observations and statistics. Respect source update intervals and back off on failure. Do not repeatedly reread the same snapshot as new evidence.
- Retain observation time, decoder/version, local-versus-network source, gain/configuration epoch and collection health. Do not publish receiver location, LAN endpoints, credentials or aircraft histories in the repository or public demo.
- Keep 1090 MHz and any separately available 978 MHz UAT data distinct. Establish installed capabilities instead of assuming a PiAware setup has both receivers.
- Separate local direct aircraft reports from MLAT, TIS-B, ADS-R and network-fed positions. A remote-derived position is not evidence of a direct aircraft-to-receiver RF path.
- Summarize hourly rather than retaining unlimited detailed tracks. Preserve altitude datum and units: barometric and geometric altitude are not interchangeable.

### Correlation study

Compare directional range percentiles, fresh directly received aircraft counts and message rate per connected receiver-minute with regional weather and Meshtastic direct-link changes. Stratify by aircraft altitude, bearing, distance, hour of day and receiver configuration. Aircraft schedules, changing routes, receiver gain, antenna obstruction and downtime can all change the sample without any ducting event. A high-altitude aircraft naturally has a different radio horizon from a ground-level mesh node.

Use within-receiver normalized anomalies, not a raw subtraction of dBFS from dBm. Similar timing across the two systems would be supporting evidence for further investigation, not proof of a common cause: frequencies, modulation, antenna patterns, heights and paths differ. A faraway aircraft is not automatically a ducting detection, and decoded message counts are not packet-delivery rates without a transmitted denominator.

### Later UI and acceptance

Offer an optional regional panel with three synchronized timelines: Meshtastic, local ADS-B reception and atmospheric conditions. Display direction/altitude bins and source gaps. Keep “possible shared environmental effect” distinct from “ordinary traffic change” and “insufficient evidence.”

Acceptance fixtures must cover stale snapshots, counter resets, absent RSSI, gain changes, duplicate polling, remote-derived positions, receiver outages and an aircraft moving closer with no RF change. First deliverable is an offline matched-window study; no unattended probing or live collector changes tonight. Local address and access questions stay parked until implementation planning.


### RF-16 extension — graphs1090 historical metrics

Include an optional graphs1090 adapter in the same future study. Its graph categories can cover message rates, aircraft/tracks, range, signal and system health; actual availability depends on the decoder and installation. The inspected interface uses generated PNGs. A readable graph is not a numeric time-series API, so correlation should use read-only exports of the underlying collectd/RRD data where available, not values guessed from pixels. [graphs1090 project and storage behavior](https://github.com/wiedehopf/graphs1090).

Before implementation, inventory the installed data sources, units, time step, consolidation functions and retention tiers. Preserve unknown values, distinguish counter rates from gauges, and avoid comparing a downsampled historical maximum with a fine-grained recent average. Gain/adaptive-gain changes and host CPU/temperature/drop counters can help distinguish receiver performance changes from propagation; expose only metrics actually present.

A future export must be narrowly scoped and read-only, with bounded time windows and caching. Do not expose the entire RRD directory or add an unauthenticated shell-command endpoint. Keep graph rendering and decoder operation unchanged. Backups and memory-to-disk flushing can affect the amount of recoverable history after power loss; inspect the local configuration rather than assuming unlimited history.

Acceptance: export known test intervals, reconcile numeric results against the existing graph at the same resolution, and reproduce missing periods and consolidation correctly. Longer term, place graphs1090 trends beside the RF/weather timelines without treating an ADS-B signal metric as an absolute calibration for Meshtastic.

For band context, the FAA distinguishes 1090 MHz and 978 MHz ADS-B links; this project must preserve that distinction. [FAA ADS-B capabilities](https://www.faa.gov/air_traffic/technology/equipadsb/capabilities/benefits).
