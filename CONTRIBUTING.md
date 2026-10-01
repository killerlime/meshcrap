# Contributing to Meshcrap

**CRAP = CuriousityReportingAndPossibilties**

This is a work in progress, and contributions of all sizes are welcome. Help with bugs, mobile usability, accessibility, documentation, radio compatibility, and VM testing is especially useful.

## Get involved

Open an issue describing what you expected, what happened, and your browser, OS, app revision, and radio firmware when relevant. For VM reports, include the image checksum, hypervisor version, boot mode, and disk/network adapter choices. Distinguish an image booting from a working setup and dashboard.

Fork the repository, make a focused branch, and open a pull request explaining the change and how you checked it. Screenshots help with interface changes. Use generic nodes and synthetic data for examples.

## Protect your installation

Work with a fresh test configuration and database. Never commit radio/channel keys, private channel names, API tokens, pairing secrets, collected messages, precise personal locations, database files, or production configuration. Redact logs and screenshots before posting. Keep external forwarding disabled and avoid radio transmissions during automated tests. Please report suspected secret exposure privately through GitHub's security reporting feature if available; do not paste secrets into a public issue.

## Checks

On Linux, install requirements into a virtual environment, then run:

```sh
python -m pip check
python tests/smoke.py
python tests/feed_policy.py
python tests/role_comparison.py
python tests/efficiency.py
node tests/visible-poll.cjs
python tests/frontend.py
python tests/privacy_check.py
```

Node.js is needed for the JavaScript checks. For the preview, run `python tools/build_demo.py` and serve `dist/demo` with a local static server. Check narrow mobile screens, keyboard navigation, node details, and clearly labeled simulated data.

VM builds use `bash deploy/vm/build.sh` on Linux with QEMU and libguestfs, or the Build VM appliances workflow. A QEMU result does not establish native Hyper-V, VMware, VirtualBox, or Proxmox compatibility. Reports from those hosts are welcome.

Follow the existing licenses and retain third-party notices. Thank you to the entire MSPmesh community for helping this project grow.
