# Release security checks

Review the exact commit's tests, privacy scan, dependency notices and code-scanning results before merging. Passing checks reduce risk; they do not certify the absence of vulnerabilities or private data.

## CodeQL application analysis

The advanced workflow scans GitHub Actions, Android Java, Swift, Python and JavaScript. Use advanced CodeQL setup for this workflow; GitHub default setup must be disabled first because GitHub rejects advanced SARIF uploads while default setup is active. Repository settings are changed separately from source changes.

Portable Python files contain `@@SETTING@@` placeholders that are replaced during installation. Scanning these templates directly causes parse errors. `python tools/prepare_codeql.py` validates only the published `config.example.json` and renders **every** application module and dashboard asset into the ignored `codeql-generated/runtime` folder. It compiles/parses the Python modules and refuses incomplete coverage. It creates no database and starts no collector, feed, radio connection or service. Installation scripts, tests and tools are analyzed alongside this rendered application.

JavaScript analysis uses rendered templates and assets, so inline settings are valid JavaScript. Bundled third-party browser libraries are excluded from this authored-code scan; their identities, versions and checksums remain in the vendor manifest and third-party notices.

Findings in `codeql-generated/runtime/<path>` correspond to `source/<path>`. The generated `source-map.json` records each source path and checksum. Fix the source template, then regenerate and rerun analysis. Do not commit the generated directory or use an installation's private runtime/configuration for scanning.

Swift analysis generates the Xcode project and performs an unsigned simulator build explicitly; an absent generated project prevents reliable automatic builds. The separate iOS workflow runs XCTest. Android's separate workflow compiles the generic companion and runs unit tests/lint. No pairing data or signing credentials are supplied to these jobs.

Reference: [GitHub CodeQL workflow configuration](https://docs.github.com/en/code-security/reference/code-scanning/workflow-configuration-options).
