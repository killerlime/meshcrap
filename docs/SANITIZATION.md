# Before publishing

Run `python tests/privacy_check.py` and review the exact outgoing changes and
history. Inspect ZIP/APK contents with `tools/audit_artifact.py` too. The shared
checks cover common credentials, private addresses, runtime/capture files and
approved asset checksums; they do not establish that every possible private
value has been detected. Use generic examples and keep installation data out of
source, build artifacts, logs and screenshots.

## Optional private identifiers

Public defaults deliberately contain no installation-specific identifier list,
including hashes. Unsalted hashes of names or short IDs are guessable and are
not anonymization. Keep project-specific policy private.

If needed, create a protected JSON file **outside the repository** with this
shape: `{"fingerprints": []}`. Add lowercase SHA-256 values of the private
identifiers you want to reject, using the same lowercase/token treatment as
`private_label` in `tests/privacy_check.py`. Never publish this file or its
contents. The optional policy supplements the generic checks; it does not
replace review of the actual files and artifacts.

Set `MESHCRAP_PRIVATE_PRIVACY_POLICY` to its absolute path before running either
audit command. Without that variable, the generic public checks still run. If
an explicitly requested policy is missing, malformed, too large or inside the
repository, the audit fails rather than silently skipping it. Findings report
file names and issue categories, without printing the matched private values.

Keep private policy values and credentials out of CI configuration, artifacts
and logs. A private CI secret may supply a policy in the runner's temporary
directory; do not expose secrets to untrusted pull-request code. Removing an
identifier from the latest source does not remove it from previously published
Git objects, forks, downloads or other retained copies.
