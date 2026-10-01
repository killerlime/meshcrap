# Data use and deployment privacy

This describes the source distribution and its configurable integrations, not a universal privacy policy for every installation. An operator who hosts the app for others must review the actual configuration and explain its data handling to those users. Installing source code does not automatically establish compliance with privacy laws.

## Data an installation can hold

The collector can store node identifiers and names, messages, radio statistics, locations, timestamps, survey routes, configuration events and user notes. Phone surveys retain queued observations on the phone until accepted by the configured collector. Pairing credentials and browser sessions control access. Device identifiers and location histories can identify people even when names are absent.

The installation operator controls its server, storage, backups and access. Do not assume clearing a page, purging a node, or uninstalling a client also removes backups, exports, previously forwarded records or copies held by others. Choose retention and deletion procedures appropriate to the deployment.

## Network requests and external services

- Viewing online maps contacts the tile provider. Requests reveal the requesting network address and requested map tiles; tile coordinates can disclose the area being viewed.
- Optional place searches send the entered search text to the selected geocoding provider. Avoid entering confidential addresses into public search services.
- Configured weather and other external integrations contact their providers and may send station identifiers or credentials needed by those services. Their terms, limits and privacy practices apply separately.
- Optional public forwarding sends the enabled categories of data to the configured destination. Review the destination and categories before enabling it; a destination may retain or redistribute received information.
- GitHub-hosted demos, downloads and repository interactions are also subject to GitHub's service practices. A synthetic demo is not a promise that the hosting or map services receive no request metadata.

The project documentation does not grant rights to third-party data or permission to disclose another person's information. Do not upload private configuration, collected data or unredacted screenshots with bug reports. Use synthetic examples whenever possible.

## Before sharing an installation

Explain who operates it, who can view its data, what is collected, where external forwarding goes, and how users can raise privacy concerns. Limit collection and access to what is needed. Verify notices against actual behavior when enabling integrations or changing retention. These are operational recommendations, not a claim of certification or a substitute for legal advice about a particular deployment.
