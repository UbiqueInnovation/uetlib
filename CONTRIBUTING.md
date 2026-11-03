# Contributing to uetlib

Use the [central issue tracker](https://github.com/UbiqueInnovation/uetlib/issues) for bugs, feature requests and
questions across the uetlib repositories. Include the affected module, version, Java/Spring versions, expected behavior
and a small reproducer. Follow [SECURITY.md](SECURITY.md) for vulnerabilities instead of opening a public issue.

## Development

Fork the affected library repository and work on a feature branch. Read its README for the Java version and any Docker,
database or native build prerequisites. Most libraries use Java 25; uetlib-rewrite uses Java 17.

Run the affected tests and the normal Maven verification from the repository root:

```sh
mvn clean verify
```

Format changed Java code with the project's Spotless configuration using google-java-format AOSP style. Where Spotless
is configured:

```sh
mvn spotless:apply
mvn spotless:check
```

For a large reactor, start with the affected module and its dependencies (`mvn -pl <module> -am verify`), then run the
checks required by CI. If a check cannot run, explain why in the PR. During the coordinate migration, prerequisite
uetlib parents/BOMs/libraries may need to be installed locally until their public releases are available; do not add
private repositories to public POMs to work around this.

## Pull requests

Open a PR in the repository containing the change and link the central issue. Keep changes focused, explain the
resulting behavior, add tests for changed behavior, and update documentation and the changelog where appropriate. The
CODEOWNERS file identifies the reviewers.

Treat public types, packages, configuration keys and serialized class names as compatibility contracts. Document
breaking changes and supply migration guidance or an OpenRewrite recipe when useful. Keep Java package migrations
separate from changes to Spring configuration keys unless those key changes are intentional.

Do not include credentials, personal data, production dumps or machine-specific IDE files. Preserve existing third-party
copyright notices and licenses, and identify the source and license of newly copied material. By submitting a
contribution, you offer your original contribution under Apache-2.0, subject to any existing license applicable to the
files you change.

## Commit signing and DCO

Every contribution must use cryptographically signed commits and include a DCO sign-off. By adding your sign-off, you
certify the [Developer Certificate of Origin 1.1](https://developercertificate.org/). Use your own name and an email
address matching the commit author:

```sh
git commit -S -s -m "Describe the change"
```

`-S` signs the commit with your configured signing key; `-s` adds the `Signed-off-by` trailer.
Configure [GitHub commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification)
so your signature is verified. The [DCO GitHub App](https://github.com/apps/dco) checks PR commit sign-offs. Both checks
are required on the default and release branches, including for organization members. Do not add a sign-off on another
author's behalf.

## Releases

Maintainers publish through the shared uetlib release workflow; contributors do not need signing or registry
credentials. Most libraries use SemVer. The dependency BOM and shared build parent use calendar versions, and
starter-parent combines the Spring Boot version with a calendar suffix. Follow the affected repository's existing
scheme.
