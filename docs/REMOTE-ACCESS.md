# Optional private remote access

Tailscale is optional. Local dashboard viewing works without it. Phone pairing and remembered browser controls require trusted HTTPS; Tailscale Serve is one way to provide it. The public Android companion accepts a configured HTTPS hostname rather than requiring a particular tailnet.

## Bring your own Tailscale setup

Install Tailscale from its official distribution on the dashboard host and clients that need access. Sign in to your own account and configure access for those devices. Meshcrap neither creates a tailnet nor bundles enrollment credentials. You do not need to provide a Tailscale API token to Meshcrap.

Keep the dashboard bound to loopback. On the dashboard host, after checking existing Serve configuration, a typical private HTTPS proxy is:

```sh
tailscale serve status
tailscale serve --bg --https=443 http://127.0.0.1:8080
```

Use your configured dashboard port if it differs. Follow any Tailscale HTTPS-enablement prompts yourself. Put the resulting hostname, without scheme or path, in your private `config.json` as `https_host` and add it to `trusted_hosts`; retain the loopback entries. Restart the dashboard. Do not copy anybody else's hostname, device address, access policy or keys.

The current application trusts HTTPS forwarding only from a local proxy with the configured hostname. Do not solve a connection problem by disabling TLS verification, allowing every client network or exposing the dashboard publicly. Tailscale **Funnel** is not the private Serve setup described here.

Access to a tailnet is not automatically authorization for every service. Review your own Tailscale access policy and any device shares; grant intended users only the dashboard access they need. Dashboard write controls still require the app's control credentials. Serving the site does not enable Tailscale SSH or grant radio-administration privileges.

For live ISO sessions, authenticate your own Tailscale installation only if you choose to add it. This initial ISO recipe does not include or auto-enroll Tailscale. Never distribute an image containing `/var/lib/tailscale`, saved auth/API keys, account state, device identities or certificates from a real deployment. Ephemeral RAM sessions may require fresh enrollment; manage and remove stale devices in your own account.

HTTPS certificate issuance can reveal the certificate hostname in public certificate-transparency records. Choose a hostname that does not disclose information you want private. See the provider's current documentation for prerequisites, account limits and exact behavior:

- [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)
- [Enabling HTTPS and certificate-name visibility](https://tailscale.com/docs/how-to/set-up-https-certificates)
- [Device sharing](https://tailscale.com/kb/1084/sharing)
- [Inviting users versus sharing devices](https://tailscale.com/docs/reference/inviting-vs-sharing)

Other private HTTPS proxies are possible, but their certificates and access controls must be configured by the operator. No Tailscale subscription, service availability or security guarantee is supplied by this project.
