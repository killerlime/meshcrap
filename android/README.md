# Meshcrap Survey — private Android test build

**CRAP = CuriousityReportingAndPossibilties**

The survey companion brings that curiosity into the field: collect observations, report survey results, and explore your mesh.

Connects directly to a paired configured Meshtastic radio over Bluetooth during a coverage survey. Disconnect the Meshtastic app first. Android 8 or later is required.

Open your collector's `/survey-companion` page over private HTTPS for the APK and pairing instructions. Connect the radio, verify its identity and channel, then tap **Start survey** in Android. No area selection is required; recording follows you outside all configured grids. A manual test traceroute is optional; GPS eligibility does not prove reachability.

One request is outstanding at a time, with at least 30 seconds between starts and a 30-second timeout. Nearby destinations require a valid position within the configured age limit. Bluetooth loss pauses requests. Collector connectivity is optional for phone-owned outings; records upload automatically on reconnection. Stop releases Bluetooth. The app uses a three-hop request limit. No radio configuration is written.

Results queue in private storage and upload with a revocable survey-only credential (uploads and survey start/end; no radio administration). Phone routes and traceroutes remain separate from HQ RF measurements; a phone GPS point is not proof of RF coverage. Unknown relay IDs are retained. Timeouts/routing failures permit up to three total attempts, including manual tests; success or the third failure starts an eight-hour cooldown; changing channels pauses requests until you explicitly resume.

This is a debug-signed test build. Build, unit tests and Android lint pass. Real-phone Bluetooth and radio-response testing remains necessary. Do not assume a successful software build establishes hardware compatibility.

## Build

Use Java 17, Android SDK 35 and Gradle 8.9. Set `ANDROID_HOME`, then run `gradle assembleDebug testDebugUnitTest lintDebug` in this directory. The APK appears in `app/build/outputs/apk/debug/`. Dependencies download from the configured official repositories.

Source is GPL-3.0; see LICENSE. Meshtastic protocol definitions under `app/src/main/proto` come from the Meshtastic protobufs project. No private pairing tokens or radio keys are included.

## Everyday use

1. Keep the saved pairing. Disconnect Meshtastic from the travelling radio. Network access is optional until uploading.
2. Open the companion and connect the radio. Slot 0 is used unless you explicitly chose another slot for that radio. An unavailable slot is never silently replaced.
3. With a current travelling fix, tap **Start survey**. The phone saves a unique outing ID and begins eligible requests, even offline. Manual tests are optional.
4. **Pause** stops new traceroutes. **End survey** ends a phone outing locally, even offline, while keeping Bluetooth connected for uploads. **Disconnect** releases Bluetooth; it does not delete saved results or end the outing.

Requests start at least 30 seconds apart and time out after 30 seconds. Late responses remain associated with their original request and position, without immediately retrying the destination. Position samples are saved every 15 seconds while the outing and radio are active, including offline. These are separate timings.

## Location quality

The travelling fix may be up to 24 hours old. Phone fixes must report accuracy within half a mile (804.672 metres). The app also checks the last-known GPS fix when connecting, applying the same limits; cached timestamps are never rewritten to look current. Older/approximate fixes are explicitly labelled. The fallback is the travelling radio's internal GPS, never its manual/installed position. The actual GPS solution timestamp is preferred when present. A radio fix still has unknown horizontal accuracy in the displayed record.

Last-heard time does not filter or order candidates. Their GPS or unknown-source coordinates must be at most 12 hours old; explicitly manual/fixed advertisements may be up to 24 hours old and are labelled accordingly. Future timestamps are rejected for selection. Automatic selection requires a known source and at least 20 advertised precision bits; missing/coarse precision remains available only for manual tests. Precision describes coordinate resolution, not guaranteed real-world GPS accuracy. No request is sent to refresh a candidate's coordinates.

Each trace retains the travelling fix and the destination's advertised coordinates, source, timestamp, last-heard time and precision at request time. MQTT-delivered packets do not qualify as RF test replies or candidates. A relayed reply does not prove a direct link or coverage along the full phone route.

## Connection and recovery

- **Start survey unavailable:** wait for Bluetooth configuration, a local-prefix radio and an eligible travelling fix. First-time pairing needs HTTPS collector access; each outing does not. Install the matching collector update before uploading these outings.
- **Collector unavailable:** check phone Internet/private-network access, Tailscale and the configured HTTPS hostname. Pairing remains saved; do not generate a new code just because the network is down.
- **No automatic candidates:** wait for fresh position advertisements or review the optional manual candidate list. Wider radius cannot make stale coordinates accurate.
- **Bluetooth lost:** disconnect/reconnect explicitly. Automatic requests remain paused; uncertain sends are not retried automatically. Test real-device reconnection and background behavior before relying on field collection.
- **Offline:** start, continue and end phone outings without the collector. GPS, receptions and traceroutes queue persistently. Upload resumes automatically when available. Reconnecting after a service/radio restart restores the outing but leaves automatic requests paused until you explicitly resume. Radio and foreground service must remain running to record.
- **Start/end response lost:** the app refreshes status and does not blindly resend the command. The server deduplicates command IDs and will not let an old end command close a newer session.
- **Queue rejected:** records are retained. Invalid or conflicting queued records can block later uploads; no automatic deletion or quarantine is implemented in this pass.

Existing pairing stays encrypted with Android Keystore, app backups remain disabled, and revocation blocks uploads immediately. An offline phone learns about revocation only on reconnection; stopping it remotely cannot guarantee immediate radio silence. The collector permits only survey uploads and start/end operations with this credential. App updates must use the same signing identity to preserve installed data; uninstalling clears app data.

The iPhone option remains the HTTPS dashboard added to the Home Screen. Bluetooth surveys are not supported; native dashboard/control source is also available under `ios/`, pending Mac/Xcode validation. The web app does not queue offline control commands.

## Live verification

The Live activity panel keeps the latest 100 timestamped events in memory, including connection/configuration, collector confirmation, saved request IDs, completed Bluetooth writes, replies/timeouts and upload acknowledgments. A Bluetooth write is explicitly labelled as not yet confirming an RF reply. Scroll back without forced auto-scrolling; Show latest activity returns to the newest entry. Pairing codes, keys, raw packets and exact coordinates are never added to this log. It survives a disconnect while the app process remains alive; it is not exported or a replacement for permanent survey history.

## Packaging review: 0.4.1-test

Version code 5 keeps the existing application ID. Start/end transitions block new requests until collector status is refreshed; Pause during startup cancels automatic resume. The collector lease is measured from the beginning of a sync, so a slow reply cannot extend authorization. Upload acknowledgments can remove only records submitted in that batch. Bluetooth permission loss and foreground-service startup failures are handled without blaming every failure on the pairing code. The phone GPS source now uses the GPS provider only; network-derived positions are not labelled as GPS. Backup is explicitly disabled on both older and newer Android versions.

Local checks passed: 15 Java unit tests, 9 synthetic collector integration tests, APK signature verification and alignment. Android lint has zero errors and 15 English-string localization warnings. The APK is debug-signed for field evaluation, not a production release. Match the signing certificate before updating an existing installation; never uninstall with pending survey results just to resolve a signing mismatch.

## Pairing compatibility: 0.4.2-test

Older collector codes containing only `url` and `token` are supported. The app asks once for the local radio-name prefix instead of rejecting the code. Enter the prefix configured on your collector; it is not a password. Newer codes already carry this field and need no extra step. The same code is stored encrypted; authentication, HTTPS checks and revocation are unchanged.

Use **Save collector pairing** to save the code before connecting Bluetooth. This confirms local validation and secure storage, not successful server authorization. Then select the radio and connect to verify the collector. Incomplete pasted text, invalid addresses/secrets, secure-storage failures and Bluetooth-start failures now have separate messages. Do not generate a replacement code merely to upgrade the app; doing so revokes the previous pairing. Phone Start/End still requires a collector that supports those controls.

Version 0.4.3-test relaxes only the travelling-position limits. Candidate-node freshness, 30-second traceroute cadence, and collector authorization timing are unchanged. Collector validation must also be updated to accept the expanded limits; older collectors reject fixes over 100 metres or five minutes old.

## Field measurements and calmer UI: 0.5.0-test

The default discovery radius is 25 miles, with 5/10/25/50/100-mile choices saved on the phone. This changes candidate selection, not RF power. Automatic repeats use the rules above; the eight-hour cooldown is persisted per destination across outings, channels and travelling radios on this phone. One outstanding request and the existing 30-second global spacing remain enforced.

New collectors advertise support for passive RF reception metadata. The companion uploads sender/packet/channel, reception time and last-hop RSSI/SNR, plus the available travelling position. No message contents or keys are uploaded. Internet-delivered packets and the radio's own packets are excluded. Older collectors keep the previous position/traceroute protocol. Old trips cannot acquire missing passive observations retroactively.

Trip totals include all retained records, with duplicate fixes and results combined. Pending requests do not count as unanswered completed tests. Map evidence distinguishes replies (possibly relayed), received packets and inconclusive timeouts. Precise map evidence requires recent phone GPS with reported accuracy within 100 m; old or coarse fixes remain in storage. Tracked distance excludes gaps, implausible jumps and movement within GPS uncertainty, so it is an estimate, not an odometer.

Status refreshes preserve the visible section and leave unchanged text alone. The activity log no longer requests focus or automatically scrolls; use **Show latest activity** intentionally. Saved pairing setup and detailed connection diagnostics are collapsible. The main action guides connection, starting and pausing.

Validation includes synthetic complete-history, duplicate/late-result, GPS-quality and ingestion tests, Java cadence tests, APK build and lint. Scroll, keyboard, accessibility focus and Bluetooth behavior still require a real-phone check.

## Eligibility update: 0.5.1-test

Travelling fixes: up to 24 hours. Candidate GPS fixes: up to 12 hours (fixed/manual positions retain their 24-hour limit). Last heard is informational only. An eight-hour per-destination cooldown applies across sessions, radios and channels on the same phone; 0.5.2 allows up to three attempts for timeout/routing failures before that cooldown. Previously stored attempt times migrate on update. Separate phones do not share cooldowns. The collector accepts these older observation timestamps without relabelling them as precise coverage evidence.

## Retry and review update: 0.5.2-test

Three total attempts (initial plus two retries), one outstanding request at a time. Confirmed timeout/routing failures permit another attempt after 30 seconds, subject to eligibility and the global cadence. Success, late success or the third failure starts eight hours of cooldown. Persisted reservations keep interrupted/uncertain sends on cooldown across restarts. Pause stops automatic retries; manual attempts share the same budget. The scheduler continues considering other eligible nodes while a retry waits.

Nearby calculations are cached for at most one second; radius changes invalidate immediately. Uploads remain capped at ten records per batch; a backlog uses five-second syncs instead of fifteen seconds. This changes HTTPS upload throughput, not radio cadence.

## Offline outings and status — 0.6.0-test

Phone outings use persistent UUIDs and original observation times. They import as separate recorded trips, including while another collector survey is active. Repeated uploads acknowledge existing identical records; a conflicting UUID is rejected and retained on the phone. Start/end markers are queued too. Unfinished uploaded trips show “upload in progress” with their latest uploaded observation as the displayed end time; this does not mean the phone stopped. Ending a phone outing never ends an unrelated collector outing.

The queue holds 100,000 records and reserves space for results by stopping passive receptions near capacity. Full storage pauses new requests instead of deleting older data. Idle sync is every 15 seconds, backlog batches of ten every 2.5 seconds; failures back off to 60 seconds. Pairing and active outing state are encrypted with Android Keystore. Observation records are in the app-private SQLite database, excluded from backup. Uninstalling or clearing app storage deletes unsent records. Keep the phone clock correct; rebooting does not fabricate missed samples or automatically resume RF requests. App/radio shutdown creates a recording gap.

The notification uses green/check = connected and healthy, yellow/arrows = connecting, red/warning = offline or attention needed. Offline text explicitly says records are saved locally. Android renders small status-bar icons monochrome; notification color presentation depends on the device. No sound or repeated alerts are requested. Device background restrictions can still stop recording; verify operation with the screen off on your phone.

An older collector-started session can continue under a server-issued, radio-scoped authorization for up to 24 hours. Late delivery is accepted based on observation time. These records retain their original session even if it was ended remotely while the phone was offline. New phone-owned outings do not need this authorization or a network start command.

## Live data flow — 0.6.1-test

The outing card shows Radio ↔ Phone → Collector. Green pulses follow actual incoming radio packets and acknowledged collector uploads; blue pulses follow completed Bluetooth traceroute writes, which do not establish successful RF delivery. Pulses display recent activity for four seconds, not packet travel speed or throughput. The phone shows its queued-record count and a logarithmic buffer fill indicator. Offline links stay still while the phone retains the queue; idle connections do not simulate traffic. Upload attempts without acknowledgment are labelled “Sending” rather than successful transfer.

Animation is display-only: no polling requests, RF traffic or new dependencies. It stops off-screen or when the activity is paused, respects Android's animator setting, and has a saved motion toggle. Text and accessibility descriptions explain direction/status without relying on motion or color. Large system fonts switch the diagram to a vertical layout. Physical-device visual/background validation remains required.
