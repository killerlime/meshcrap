# Security policy

## Reporting a vulnerability

Use GitHub's **Security → Advisories → Report a vulnerability** option if it is available for this repository. If it is unavailable, open an issue asking for a private reporting channel **without describing the vulnerability publicly**. Do not include passwords, channel keys, tokens, production databases, private messages or precise personal locations.

A useful private report includes the affected commit/version, impact and minimal reproduction steps using synthetic data. Test only systems you own or have explicit permission to test. Do not probe other installations, transmit over other people's radios, or access their data. This policy does not authorize testing third-party services or waive third-party rights.

## Maintenance scope

Security fixes target the current development branch. Older releases, personal forks and experimental artifacts do not have a guaranteed backport or support period. The maintainer will review reports in good faith, but no response deadline, fix deadline, bounty or security certification is promised.

## Deployment

Keep the dashboard on a trusted private network, use private HTTPS for credentials and phone pairing, restrict allowed hosts/networks, and leave unused controls and external integrations disabled. Update the operating system and dependencies, protect backups and signing keys, and revoke exposed credentials promptly. A private network or successful scan is not proof that an installation is secure.

See the [data-use notice](docs/DATA-USE.md) and [operational limits](docs/PROJECT-NOTICE.md). This policy supplements documentation; it does not alter component licenses or applicable legal rights.
