# Companion and dashboard logic review — 0.6.0-test

Scope: survey request lifecycle, restart behavior, candidate selection, uploads, positioning, trip summaries, setup instructions, authentication boundaries, and existing dashboard regression checks. This is a focused source/regression review, not a claim of exhaustive hardware or security certification.

## Changes

- Failed traceroutes: three total attempts, not three additional retries. Only timeout/routing outcomes reopen the budget. At least 30 seconds after failure, one outstanding request, existing 30-second global send spacing. A success/late success or third failure closes the budget for eight hours. Manual tests share it. Stored reservations protect against duplicate uncertain sends after process interruption.
- Cooldown persists per destination on a phone across survey/channel/radio changes. Separate phones do not share that state. Retry selection remains subject to GPS/radius/channel eligibility; movement does not force a test outside those bounds.
- Travelling fixes remain acceptable for 24 hours, candidate GPS for 12 hours, fixed/manual positions for 24 hours. Last-heard time does not filter or rank candidates. Approximate fixes are never relabelled as precise map evidence.
- Cached candidate calculations avoid repeating formatting, distance calculations and sorting within one second. New radio packets, phone positions and radius changes invalidate the cache.
- Queue backlog drains at 2.5-second HTTPS intervals rather than fifteen; batches stay bounded at ten records. Normal idle polling and radio cadence are unchanged.
- Setup instructions now match the APK, including start/resume/end/disconnect differences, retry budget and offline-recording limitations.

## Validation

Android APK build and lint, 25 Java tests including retry limits, successful/late-result suppression, cooldown boundaries, clock rollback and migration. Python survey integration/evidence, diagnostics, terrain adapter, environmental evidence/cache, feed privacy policy, role comparison, setup labels and tropo checks passed locally. Frontend JavaScript syntax, simulator calculations and visibility-aware polling checks passed. Privacy checks cover source; APK signing identity/alignment is checked before hosting the download.

Windows cannot run the Linux-only full startup and production-server efficiency scripts (fcntl/Linux platform requirements). No workaround disables those platform requirements. No heavy production tests, dependency installations on the Pi, radio-setting changes, or test transmissions were performed. Phone Bluetooth, background operation, actual retry observations and scrolling still need field validation.

## iOS

Native dashboard-and-controls source, project generation recipe, URL/origin tests and privacy manifest are under `ios/`. Project YAML and plist were parsed locally. Swift compilation, XCTest, simulator/device behavior and signing have NOT been verified: this environment has no Mac/Xcode. There is no signed IPA or App Store release. Safari Add to Home Screen remains available today. Bluetooth surveys are outside the first iOS scope.

## Remaining limits

Coverage results describe observations, not guaranteed service. Timeouts can reflect routing/congestion as well as poor reachability. Last-hop RSSI/SNR is not whole-route RF quality. Older apps do not supply passive reception records. Phone-owned outings record offline; older collector-started outings use a bounded 24-hour authorization. Network uploads still require a valid pairing token. Installing the matching update is required for its retry behavior; a server update cannot change an already-installed older APK.

Offline update: Android build, lint and 28 unit tests pass. Fifteen synthetic server tests cover separate offline trip import, replay deduplication, atomic rollback on conflicting outing metadata, late delivery after a remotely ended session and revoked credentials. Real-device airplane-mode/background/restart and notification-color checks remain necessary. The matching collector update is required for offline-created trip uploads.
