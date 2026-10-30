# Security policy

## Report privately

Please report suspected vulnerabilities through [GitHub private vulnerability reporting for uetlib](https://github.com/UbiqueInnovation/uetlib/security/advisories/new), when enabled. Identify the affected library repository so reports can be routed to its maintainers. Do not publish exploit details in public issues, discussions or pull requests.

If the private reporting form is unavailable, contact [info@ubique.ch](mailto:info@ubique.ch) to request a private security contact. Initially include only the affected library/version and a non-sensitive summary. This is [Ubique's published general contact address](https://www.ubique.ch/kontakt), not a dedicated security mailbox.

A useful private report includes:

- Affected Maven coordinates, versions and Java/Spring versions.
- The vulnerable behavior, prerequisites and potential impact.
- Minimal reproduction steps or a proof of concept using synthetic data.
- Any workaround and whether the issue reproduces on the latest stable release.

Do not include real credentials, personal data or production data. Coordinate public disclosure with the maintainers so affected users can receive a fix or mitigation.

## Versions and fixes

Report relevant vulnerabilities even if found in an older version. Maintainers assess supported release lines and backports case by case; this policy does not promise an acknowledgment deadline, patch schedule, long-term-support window or bounty. Snapshots and prereleases are development versions.

Security fixes and affected/fixed versions will be described in the relevant library's releases, changelog and, where appropriate, a GitHub security advisory.
