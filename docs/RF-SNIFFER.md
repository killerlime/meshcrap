# Optional RF sniffer

Meshcrap's **RF sniffer** menu embeds a separately operated passive SDR receiver. It is off by default. The collector and mobile companion work without it. Closing the view unloads the embedded page, so its live stream does not stay active in the background.

## Quick setup

1. Install and operate your receiver separately. [alphafox02/meshtastic-sniffer installation instructions](https://github.com/alphafox02/meshtastic-sniffer#install) describe building from source, supported SDRs, IQ replay and its native web dashboard. Start with an appropriate region/preset for your own installation; no private channel settings or keys are supplied here. Building and receiving are separate tasks; Meshcrap does neither automatically.
2. Serve the sniffer dashboard on **its own private HTTPS origin**, for example `https://sniffer.example.com/`. This supports the native upstream dashboard without rewriting its internal API paths. Alternatively, serve a **prefix-aware** companion web page at `/sniffer/` on the same protected origin as Meshcrap; named paths such as `/sniffer-lab/` also work. Keep native ports private, and apply authentication/network policy to the whole sniffer site. Dashboard access restrictions do not automatically protect a different proxy target.
3. From the Meshcrap source folder, run:

   ```sh
   python meshcrap.py sniffer-setup
   # If you use a custom configuration file:
   python meshcrap.py --config /path/to/config.json sniffer-setup
   ```

   Answer **yes** and enter the private HTTPS URL or same-origin path. Only choose a site you operate and trust. The short wizard preserves your other settings, validates the new configuration, saves a private backup and replaces the file atomically. Restart only the dashboard service using your installation's normal process. Collection and the separate receiver do not need restarting.
4. Open **RF sniffer → Quick setup**. **Check connection** checks a same-origin page with a read-only request. For a different HTTPS origin, browser privacy prevents a reliable check, so inspect the embedded view or **Open separately** instead. A responding HTML page does not prove live RF reception; confirm the receiver's own status and stream. If that site blocks framing, keep using the separate link or adjust the site's frame policy deliberately.

First-use `python meshcrap.py setup` offers the same optional connection. You can also edit ignored `config.json` directly:

```json
{
  "rf_sniffer_enabled": true,
  "rf_sniffer_url": "https://sniffer.example.com/"
}
```

These are additions to your existing configuration; replace the example with your own private address, or use `/sniffer/` for a prefix-aware site. Plain HTTP, protocol-relative URLs, query strings, credentials, encoded paths and traversal segments are rejected. An enabled view requires a URL/path; disabled default configuration has an empty URL. Use **no** in the quick wizard to remove the embedded view without touching captures or the receiver process.

## Proxy and security requirements

The native upstream dashboard currently uses root-relative `/events` and `/api/...` requests. A dedicated HTTPS origin avoids path rewriting. **A simple prefix proxy alone is insufficient.** For the same-origin path option, use an independently maintained prefix-aware companion frontend, or carefully rewrite and verify the upstream page's root-relative requests in your reverse proxy. Never route its root `/api` into Meshcrap's `/api`. Check event streams and every intended endpoint after upstream updates. This release configures an existing web interface; it does not install or generate a secure native-sniffer proxy.

Upstream's native web listener currently binds all interfaces. Put it behind a host firewall, container/network namespace with loopback-only published port, or equivalent access restriction. Do not assume `--web` is loopback-only. Its documented bearer-token option protects control writes; do not assume it protects captured data or the live stream. Verify the exact upstream version's behavior before exposing any port. Private network access, HTTPS and authorization are installation responsibilities for this separate component.

Meshcrap has no server-side fetcher/proxy for sniffer URLs, reads no IQ files, captures, keys or credentials, and never forwards SDR measurements into the collector database. Only your browser loads the configured page. Its frame policy permits only this dashboard and the exact configured HTTPS origin. Treat the companion frontend as trusted code: an iframe with same-origin scripts is **not** a security boundary from the rest of the dashboard; a different origin is separated by the browser's same-origin policy. Only embed a page you operate and trust. The frame denies top navigation, popups and camera/microphone/location/USB/Bluetooth delegation; its controls remain owned by the separate application.

Keep receiver keys, tokens, channel-share URLs, precise positions, captures and operator identities outside the repository. The display wizard requires none of these. Disable multicast, external forwarding and shared capture sinks unless you explicitly need and secure them. A passive sniffer can still have network-output features; this integration never enables them.

## Build dependencies, license and source

The integration is independently written Meshcrap code; no upstream sniffer code or executable is bundled, downloaded or installed. The optional external project is licensed **GPL-3.0-or-later**, copyright CEMAXECUTER LLC; see its [LICENSE](https://github.com/alphafox02/meshtastic-sniffer/blob/main/LICENSE). Its CMake build uses a C toolchain, FFTW3 and OpenSSL, plus libraries for selected SDR backends; optional output sinks and companion programs have additional dependencies. Follow the exact checked-out revision's documentation rather than installing every backend.

Record the upstream commit and build options in your deployment records. If you redistribute a sniffer binary, modifications or an image/container containing it, retain applicable license notices and provide corresponding source and build/install materials under its license. Linking to a moving main branch is not an exact source bundle. This repository's root license does not relicense the sniffer or its dependencies. Upstream source/API details above were reviewed on 2026-10-08; recheck them when upgrading.

## Verification and limits

Automated checks cover disabled defaults, backwards-compatible configuration, rejected unsafe URLs/paths, exact-origin framing policy, non-writing display endpoints, preserving configuration/backup behavior and canceled setup. Browser verification covers the guided steps and loading/unloading a synthetic independent page. Actual SDR drivers, capture performance, RF reception and the deployment's proxy/authentication must be validated on the user's hardware. This integration does not certify third-party sniffer controls or every upstream version.
