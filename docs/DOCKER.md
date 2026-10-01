# Docker installation (preview)

Build from this repository with Docker Engine and Compose v2 on Linux, or Docker
Desktop using Linux containers on Windows/macOS. No registry image is published
yet. The recipe uses Python 3.12 on Debian Bookworm. Native ARM64 builds are
intended for 64-bit Raspberry Pi installations; only platforms listed in the
build results are tested. No privileged container, USB passthrough, host network,
Docker socket mount, or SSH credentials are needed for a TCP radio connection.

```sh
docker compose build
docker compose run --rm dashboard setup
docker compose up -d dashboard
```

Open **http://localhost:8080**. In the wizard, keep `/data/state` and port `8080`.
The app title, radio or Pi bridge address, receiver ID and labels are your choices.
You can skip the radio and start with an empty dashboard. Nothing transmits or
forwards to an external feed by default.

The setup adapter allows loopback and the current private Docker bridge gateway
only. Compose publishes the web port on host loopback, so this is **local-machine
access**, not remote access. Keep this binding unless you have deliberately
configured network access. Docker forwarding can hide the original client IP;
the gateway allowlist is not a substitute for a host firewall or authentication.
If recreating the Docker network changes its gateway, update `allowed_networks`
in the stored configuration or rerun setup (which backs up the old configuration).

Once your radio settings are correct, enable collection separately:

```sh
docker compose --profile radio up -d
docker compose logs --tail 100 dashboard collector
docker compose run --rm dashboard check
```

Use a reachable TCP radio or an existing Pi bridge. `localhost` in a container
means that container, not the host or radio. Avoid concurrent clients connecting
directly to a single-client radio. The dashboard and collector share one named
volume but run as separate processes. Keep only one collector for a receiver.

## Stored configuration and backups

The `meshcrap-data` named volume stores `/data/config.json`, database, security
state and generated runtime. It survives container replacement and ordinary
`docker compose down`. **Do not use `down -v` unless you intend to erase it.**
To edit JSON without installing an editor inside the image:

```sh
docker compose cp dashboard:/data/config.json ./config.local.json
# Edit config.local.json locally. Keep it private; it can contain connection details.
docker compose stop dashboard collector
docker compose cp ./config.local.json dashboard:/data/config.json
docker compose run --rm dashboard check
docker compose up -d dashboard
# Start the radio profile again only if configured.
```

Configuration remains owned by UID/GID `10001:10001`; if your Docker version
changes ownership during copying, restore that specific file's owner with a
one-time container running as root. Do not make the volume world-writable.
For a consistent full-volume backup, stop both services, back up the named volume
with your normal Docker volume backup tool, then restart them. Protect backups
like the live data. Never add them to Git or a Docker build context.

## Private HTTPS and optional integrations

Remote access, Tailscale enrollment, weather accounts and external feeds are
operator-configured and absent from the image. Do not pass secrets as Docker
build arguments or commit them to Compose. Configure integrations in the private
volume using the existing application documentation.

Remembered browser devices and phone pairing require HTTPS. The application
trusts HTTPS proxy headers only from loopback for the configured hostname.
A host-side proxy forwarding over Docker's bridge does **not** meet that rule.
This initial Compose recipe is for local HTTP use; use the native Linux HTTPS
deployment for phone pairing, or independently configure a proxy sharing the
dashboard's network namespace. Do not broaden proxy trust to arbitrary clients.

## Updates, limits and licensing

Back up first, then rebuild from a reviewed Git revision and recreate services.
This is not yet an automatic database-migration or unattended-upgrade system.
The root filesystem is read-only, Linux capabilities are dropped, and application
processes run as a non-root user. `/tmp` is temporary and logs rotate.

Dependency ranges and the Python base tag can change between builds. The image
records installed Python versions in `/opt/meshcrap/BUILD-DEPENDENCIES.txt`;
record the image digest too. CI builds and tests Linux AMD64 without publishing
the image. ARM64 and Docker Desktop networking require separate validation.
Application notices and license files are included. Debian/Python dependencies
retain their licenses; consult [third-party notices](../THIRD_PARTY_NOTICES.md)
before redistributing images, including corresponding-source obligations.
