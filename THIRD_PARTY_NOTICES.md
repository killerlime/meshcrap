# Third-party components

- **Leaflet 1.9.4**: `source/dashboard/static/lcd-leaflet.js` and `lcd-leaflet.css`. Copyright 2010–2023 Vladimir Agafonkin; copyright 2010–2011 CloudMade. BSD-2-Clause; see `licenses/Leaflet-LICENSE`.
- **Meshtastic protocol definitions**: `android/app/src/main/proto/`, from the Meshtastic protobufs project. GPL-3.0, preserved in `android/LICENSE`. Android companion source is distributed under that license as stated in its own README.
- **Meshtastic Python, Flask, protobuf, Pypubsub, tzdata**, Gradle/Android build tooling and other installed dependencies are not relicensed by this repository. See their upstream distributions for licenses.
- **Chart.js, Leaflet and OpenStreetMap** are also referenced by dashboard pages. Online map tiles require network access and retain visible OpenStreetMap attribution. This is not an offline map package.

No API credentials, radio keys, private map screenshots, node-owner assignments, messages or collected database rows are intended to be distributed.

Browser assets are bundled under `source/dashboard/static/vendor`: Chart.js 4.5.1 (MIT), Leaflet 1.9.4 (BSD-2-Clause), Inter and JetBrains Mono fonts (SIL OFL). Their license files and source/checksum manifest are included in that directory. Map tiles still come from the configured tile provider.

Android runtime dependency: **Protocol Buffers Java Lite 4.29.3**, copyright Google Inc., BSD-3-Clause. Its upstream license, GPL-3.0 and a source notice are bundled in `android/app/src/main/assets/licenses/` and viewable through **Licenses and source**. Android builds use Java 17, Gradle 8.9, Android Gradle Plugin 8.7.3, protobuf Gradle plugin 0.9.4 and SDK 35; these tools retain their upstream terms. JUnit 4.13.2 is a test dependency, not application code.

When distributing an APK, provide the corresponding source for that exact build, including its build scripts and protocol definitions, alongside it. Do not rely on a moving main-branch link as the only record of the source used to build a binary. Retain each component's notices in redistributed source and binary packages.

VM/live images additionally contain Debian and installed packages. Preserve `/usr/share/doc/*/copyright`, Python distribution license metadata, resolved package inventories and source availability required by those licenses. An appliance image is not entirely covered by the root Unlicense. Images must receive a distribution/license review before a public binary release.
