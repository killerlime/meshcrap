# Third-party components

- **Leaflet 1.9.4**: `source/dashboard/static/lcd-leaflet.js` and `lcd-leaflet.css`. Copyright 2010–2023 Volodymyr Agafonkin; copyright 2010–2011 CloudMade. BSD-2-Clause; see `licenses/Leaflet-LICENSE`.
- **Meshtastic protocol definitions**: `android/app/src/main/proto/`, from the Meshtastic protobufs project. GPL-3.0, preserved in `android/LICENSE`. Android companion source is distributed under that license as stated in its own README.
- **Meshtastic Python, Flask, protobuf, Pypubsub, tzdata**, Gradle/Android build tooling and other installed dependencies are not relicensed by this repository. See their upstream distributions for licenses.
- **Chart.js, Leaflet and OpenStreetMap** are also referenced by dashboard pages. Online map tiles require network access and retain visible OpenStreetMap attribution. This is not an offline map package.

No API credentials, radio keys, private map screenshots, node-owner assignments, messages or collected database rows are intended to be distributed.

Browser assets are bundled under `source/dashboard/static/vendor`: Chart.js 4.5.1 (MIT), Leaflet 1.9.4 (BSD-2-Clause), Inter and JetBrains Mono fonts (SIL OFL). Their license files and source/checksum manifest are included in that directory. Map tiles still come from the configured tile provider.

Android runtime dependency: **Protocol Buffers Java Lite 4.29.3**, copyright Google Inc., BSD-3-Clause. Its upstream license, GPL-3.0 and a source notice are bundled in `android/app/src/main/assets/licenses/` and viewable through **Licenses and source**. Android builds use Java 17, Gradle 8.9, Android Gradle Plugin 8.7.3, protobuf Gradle plugin 0.9.4 and SDK 35; these tools retain their upstream terms. JUnit 4.13.2 is a test dependency, not application code.

When distributing an APK, provide the corresponding source for that exact build, including its build scripts and protocol definitions, alongside it. Do not rely on a moving main-branch link as the only record of the source used to build a binary. Retain each component's notices in redistributed source and binary packages.

VM/live images additionally contain Debian and installed packages. Preserve `/usr/share/doc/*/copyright`, Python distribution license metadata, resolved package inventories and source availability required by those licenses. An appliance image is not entirely covered by the root Unlicense. Images must receive a distribution/license review before a public binary release.

## Native iOS source preview

The original `ios/` source uses the repository license. It imports Apple SwiftUI, UIKit, Foundation and WebKit frameworks from the Apple SDK; these frameworks are not vendored here. XcodeGen (MIT, https://github.com/yonaskolb/XcodeGen) is an optional build-time project generator and is not bundled. No third-party runtime SDK is included. See `ios/README.md` for source references, privacy declaration and unverified build status.

## PotatoMesh integration credit

[PotatoMesh](https://github.com/l5yth/potato-mesh) is developed by l5yth and the PotatoMesh contributors. Credit this upstream project for the Potato ecosystem and API used by the optional feed, ingestor directory and heard-by integrations. Upstream publishes its code under [Apache-2.0](https://github.com/l5yth/potato-mesh/blob/main/LICENSE). Meshcrap’s demo measurements and report-card calculations are illustrative Meshcrap examples, not upstream measurements.

When incorporating or redistributing upstream code or assets, retain their applicable license, copyright and notices, identify modifications, and record the source revision. Link to PotatoMesh in relevant integration documentation and user-facing views; do not imply upstream authorship or endorsement of Meshcrap-specific features.

## Optional independent RF sniffer

[meshtastic-sniffer](https://github.com/alphafox02/meshtastic-sniffer) is an optional external application, copyright CEMAXECUTER LLC, licensed [GPL-3.0-or-later](https://github.com/alphafox02/meshtastic-sniffer/blob/main/LICENSE). No upstream code or binary is bundled here. Meshcrap's independently written iframe integration displays an operator-configured page; the receiver remains a separate process with its own configuration and data. If redistributing that application or its dependencies, preserve their notices and fulfill their corresponding-source obligations for the actual build. See [RF sniffer setup](docs/RF-SNIFFER.md).

## Source and license index

The root Unlicense applies to original Meshcrap material only. Third-party files keep their own licenses. The Android companion is GPL-3.0. The Python application imports GPL-3.0-only Meshtastic; distributing a combined runtime requires reviewing GPL obligations for that combination, not labeling the entire artifact Unlicense.

| Component | Source | License / retained material |
|---|---|---|
| Meshtastic Python | https://github.com/meshtastic/python | GPL-3.0-only; installed distribution metadata and license |
| Meshtastic protocol definitions | https://github.com/meshtastic/protobufs | GPL-3.0; android/LICENSE and bundled APK GPL text |
| Flask | https://github.com/pallets/flask | BSD-3-Clause |
| Protocol Buffers (Python, Java Lite, protoc) | https://github.com/protocolbuffers/protobuf | BSD-3-Clause; APK Protobuf-LICENSE.txt |
| PyPubSub | https://github.com/schollii/pypubsub | BSD-2-Clause |
| tzdata | https://github.com/python/tzdata | Apache-2.0 package; retain bundled IANA data notices too |
| Waitress 3.0.2 | https://github.com/Pylons/waitress | ZPL-2.1 |
| Chart.js 4.5.1 | https://github.com/chartjs/Chart.js/tree/v4.5.1 | MIT; vendor/Chart-LICENSE.md |
| Leaflet 1.9.4 (including marker/layer images) | https://github.com/Leaflet/Leaflet/tree/v1.9.4 | BSD-2-Clause; vendor/Leaflet-LICENSE and licenses/Leaflet-LICENSE |
| Inter fonts | https://github.com/rsms/inter | SIL OFL-1.1; vendor/Inter-OFL.txt |
| JetBrains Mono fonts | https://github.com/JetBrains/JetBrainsMono | SIL OFL-1.1; vendor/JetBrainsMono-OFL.txt |
| PotatoMesh integration | https://github.com/l5yth/potato-mesh | Apache-2.0 upstream; see integration credit above |
| Gradle | https://github.com/gradle/gradle | Apache-2.0 build tool, with its own dependency notices |
| Android Gradle Plugin / Android SDK | https://source.android.com/ | Build tooling and platform terms; preserve notices for anything redistributed |
| protobuf Gradle plugin | https://github.com/google/protobuf-gradle-plugin | BSD-3-Clause build plugin |
| JUnit 4.13.2 / Hamcrest | https://github.com/junit-team/junit4 / https://github.com/hamcrest/JavaHamcrest | EPL-1.0 / BSD-3-Clause; test dependencies, not APK runtime |
| OpenJDK | https://openjdk.org/legal/ | GPLv2 with Classpath Exception where applicable; build JDK |
| Python / Debian / Raspberry Pi OS | https://www.python.org/ / https://www.debian.org/legal/licenses/ / https://www.raspberrypi.com/software/ | Mixed component licenses; retain distribution notices and exact package inventories |
| XcodeGen | https://github.com/yonaskolb/XcodeGen | MIT build tool; Apple SDK frameworks retain Apple terms |

Version ranges in requirements.txt can resolve differently between builds. Run tools/license_inventory.py inside the actual build environment to record every installed Python distribution, including transitive packages, versions, metadata, and copies of available license/NOTICE files. An UNKNOWN entry or missing text needs review; a metadata report is not a license-compliance certificate. Browser source URLs and checksums are in source/dashboard/static/vendor/manifest.json.

## External services and reference material

- Natural Earth country geometry: public domain, https://www.naturalearthdata.com/about/terms-of-use/.
  `source/dashboard/static/offline-geography.json` is derived from the 110m country FeatureCollection at
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson
  (retrieved 2026-10-08; original SHA-256 `6866c877d39cba9c357620878839b336d569f8c662d3cfab4cb1dbe2d39c977f`).
  Transformation: retain all 177 feature geometries; remove properties. Coarse boundaries do not provide street detail or imply endorsement of disputed boundaries.
- Meshyface (https://github.com/jaronmcd/meshyface, GPL-3.0) was reviewed for functional workflow ideas. No Meshyface code, assets or runtime dependency is included in Mesh explorer; its implementation is independently written.

- OpenStreetMap contributors supply map data under ODbL: https://www.openstreetmap.org/copyright. Preserve visible attribution and the license link. Tile and geocoding services also have usage policies: https://operations.osmfoundation.org/policies/tiles/ and https://operations.osmfoundation.org/policies/nominatim/.
- Weather Underground / The Weather Company observations: https://www.wunderground.com/ and https://www.weathercompany.com/. Retain displayed provider attribution; data and service access are governed by provider terms, not the root license.
- HeyWhatsThat terrain profiles: https://www.heywhatsthat.com/. Optional external service; do not infer redistribution rights for its data from this repository's license.
- OpenAI API: https://openai.com/policies/services-agreement/. Optional service, not bundled model software.
- Radio hardware facts retain per-model manufacturer/documentation URLs in source/dashboard/static/radio-hardware.js. Those references are sources of facts, not a license grant for vendor artwork, firmware, or branding.
- GitHub Actions and container/build tooling retain their upstream licenses. Workflow references do not relicense those projects or make their code part of the application source.

## Release requirements and audit limits

For each release, retain exact application source, build scripts, dependency inventories, license texts and notices. MIT/BSD notices must accompany redistributed copies; Apache components require their license and applicable NOTICE material, with changes identified; OFL fonts retain their OFL and copyright notices. Apply the actual component texts rather than this summary when distributing.

For GPL-containing binaries, provide the corresponding source for the exact components/build under an applicable GPL distribution method, including required build/install materials. A link to a moving upstream branch or a Meshcrap-only source archive is not by itself a complete corresponding-source bundle for all bundled dependencies. OS image source obligations extend to the included OS packages.

Audit status (2026-10-09): bundled browser notices and Android license texts are present. The ten copied Meshtastic proto files are byte-for-byte copies from revision `ad0bf31e82886d794334dcc62abb80da862a8ec7`; immutable source URLs and SHA-256 checksums are recorded in `android/proto-sources.json`. Earlier published binary/container releases have not been certified as complete corresponding-source distributions by this audit; retain them for review and supplement their source materials as needed. New inventories do not retroactively change existing artifacts. Do not describe this project as universally cleared or entirely Unlicense.
