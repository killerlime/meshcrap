# Mesh what-if lab

Open the **What-if** tab. The simulator itself is a browser-only software model, with no radio API, polling, credentials, location lookup or storage. Inputs stay in the page between tab visits and reset on reload. It can also be opened as a standalone static page.

## Available models

- Preset/frequency migration: one node, local group or coordinated regional change; synthetic compatibility diagram.
- LoRa airtime: SF7–12, explicit header, CRC, editable payload and preamble; automatic low-data-rate optimization assumption at 16 ms symbols.
- Offered airtime: transmissions requested in one shared RF neighborhood, not measured utilization, simulated collision probability or a routing engine.
- Bidirectional link budget: connector power, frequency-dependent coax loss, antenna gain, connectors, filter and other passive losses, remote-end power/sensitivity, distance and assumed excess loss.
- Coordinates: great-circle distance only. No terrain service or location upload.
- Path clearance: antenna heights, editable effective-Earth-radius factor, and optional user-supplied fraction/elevation samples. Shows the direct ray, lower 60% Fresnel boundary and curved ground on 101 samples. Blank terrain is explicitly hypothetical. This does not add a guessed diffraction loss to the link budget.
- One-way warnings: each direction must independently exceed its supplied receiver threshold.
- Receive cascade: passive loss / LNA / passive loss / receiver, using Friis noise factors at 290 K. Separate from the passive link-budget model; no overload prediction.

Hardware selection populates published values where available. Heltec V3 sensitivity is sourced at SF12/125 kHz and adjusted approximately for other presets; the UI labels that extrapolation. Other profiles do not invent missing sensitivity curves. Published maximum output is a simulation input, never an operating recommendation. Station G3's vendor page warns of historical content and has conflicting band/power figures; the profile records that uncertainty.

The supported-device directory is the intended catalog scope, **not a claim that every flashable device already has a verified profile**. Initial profiles cover RAK4631, Heltec V3 and Station G2/G3, with limited component references for Yeti Wurks and Muzi Works. Other devices use explicit custom inputs until sourced. No brand-wide performance inheritance.

## Sources and assumptions

Reviewed October 1, 2026. Original implementation; no vendor code, images or product descriptions are bundled. Names identify products, without endorsement.

- [Semtech AN1200.13](https://meshtastic.org/assets/files/LoRa_Design_Guide-b3f1bb6c4d86b62a065c50d5961bc6b2.pdf): classic packet-airtime equations. Payload means PHY bytes, not chat characters.
- [Meshtastic preset table](https://meshtastic.org/docs/overview/radio-settings/): SF, bandwidth and coding-rate combinations. The margin comparison uses approximate 2.5 dB/SF and thermal-noise bandwidth scaling; coding receives no invented gain bonus.
- [ITU-R P.525](https://www.itu.int/rec/R-REC-P.525/en): free-space baseline. Terrain, weather, interference and antenna mismatch are not inferred from coordinates.
- [ITU radio-relay handbook](https://www.itu.int/dms_pub/itu-r/opb/hdb/R-HDB-24-1996-PDF-E.pdf): effective-Earth and Fresnel geometry. The default k=4/3 is an assumed reference, not current atmospheric evidence.
- [Analog Devices receiver noise analysis](https://www.analog.com/en/resources/technical-articles/system-noisefigure-analysis-for-modern-radio-receivers.html): cascade noise principles. The builder models matched stages and thermal noise; interference and overload need separate evidence.
- [Times Microwave LMR-400](https://timesmicrowave.com/wp-content/uploads/2022/06/lmr-400-datasheet.pdf) and [LMR-240](https://timesmicrowave.com/wp-content/uploads/2022/06/lmr-240-datasheet.pdf): standard cable attenuation formulas in dB/100 ft, converted to metres. Not interchangeable with UF, clones, damaged cable or other variants.
- Hardware profile source URLs and caveats are kept with each record in `radio-hardware.js` and displayed in the builder.

## Validation and remaining work

Run `node tests/mesh-simulator.cjs`. Fixtures cover known airtimes, identity and mismatch cases, doubling-frequency loss, asymmetric power, passive losses, cable units, coordinate distances and noise cascades. Frontend compilation and privacy checks run separately.

Next: verified per-revision device catalog, antenna pattern interpolation, terrain-backed path profiles, calibrated sensitivity curves, configurable receive-chain stages, and a discrete-event collision/relay model. Current diagrams are educational scenarios, not forecasts of observed mesh performance. No range or regulatory compliance guarantee is produced.

The separate **Real terrain profile** panel is an optional external HeyWhatsThat
integration with explicit coordinate submission, local usage accounting and a
cache. See [terrain setup and limitations](TROPO-SOURCES.md#enabling-experimental-terrain-profiles).
