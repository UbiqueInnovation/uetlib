# Shared Maven workflows

The reusable workflows live in this repository. Neither workflow adds Maven Central plugins or publishing configuration to the shared parent POMs.

Both accept `pom` (default `pom.xml`), `java-version` (default `25`) and `maven-version` (default `3.9.11`). Maven is downloaded from Central and its SHA-512 checksum is checked. Java 17 projects such as uetlib-rewrite must override `java-version`.

## Build and test

```yaml
name: Build
on:
  push:
    branches: ['**']
  pull_request:
permissions:
  contents: read
jobs:
  build:
    uses: UbiqueInnovation/uetlib/.github/workflows/mvn-install.yml@<full-commit-sha> # v1.2.3
```

The workflow checks out the caller, sets up Java/Maven and caching, and runs `mvn clean install`, including verification and tests. It takes no secrets or private registry settings. A reusable workflow changes the displayed check name; check branch rules against the resulting job name before replacing existing CI.

## Publish a library

```yaml
name: Publish
on:
  push:
    tags: ['v*']
permissions:
  contents: read
jobs:
  publish:
    permissions:
      contents: write
    uses: UbiqueInnovation/uetlib/.github/workflows/mvn-publish.yml@<full-commit-sha> # v1.2.3
    secrets: inherit
```

Replace the placeholder SHA and example tag comment with an actual released workflow revision. Callers can override `java-version`, `pom`, `maven-version`, `environment` (default `maven-central`) and `create-github-release` (default `true`). They cannot supply arbitrary Maven arguments or a different upload endpoint.

Publishing accepts release tags such as `v3.0.0`, `v3.0.0-alpha.1` and `v4.1.1-2026.11.0`. The commit must be on the default branch or a `release/` branch. Only `UbiqueInnovation/uetlib-*` library repositories with `ch.ubique.uetlib` Maven coordinates are accepted; the test application and coverage artifacts are excluded.

The release job waits for its GitHub environment approval, sets reactor versions from the tag, builds/tests, attaches sources and Javadoc, and stages artifacts in a local `central-staging` directory. The stage uses a file repository override, so inherited Artifactory deployment settings do not send anything to Artifactory. No Central publishing plugin is installed in the POM or inherited by private consumers.

Before upload, the workflow validates coordinates, Maven paths and required JARs, signs each POM/JAR, verifies each signature, and generates checksums. Parent/BOM POM artifacts need no source or Javadoc JAR. Resource-only OpenRewrite recipe JARs get a documentation JAR pointing to their source and usage, and recipe sources if the source plugin did not attach them. Ordinary Java libraries fail if source or Javadoc JARs are missing.

The bundle is uploaded through the Central Publisher API with automatic publication. The workflow waits for `PUBLISHED` and only then creates the GitHub release. Signing material is kept in a temporary GnuPG home and removed after signing. The staging repository and ZIP are removed even when a later step fails. After a publication timeout, inspect the deployment ID in the job summary before retrying: Maven Central versions cannot be overwritten.

## Credentials and approvals

Create one set of organization secrets with **Selected repositories** access, restricted to the libraries that publish:

- `CENTRAL_USERNAME`: Central Portal user-token username.
- `CENTRAL_PASSWORD`: Central Portal user-token password.
- `MAVEN_SIGNING_KEY`: ASCII-armored private signing key; publish its public key separately.
- `MAVEN_SIGNING_PASSPHRASE`: signing-key passphrase; empty is allowed for an unencrypted key.

Callers use `secrets: inherit`. The shared workflow reads only these four secrets. An explicit four-secret mapping is also supported if a caller should not inherit other secrets.

In each calling repository, configure the `maven-central` environment with the existing admin team as required reviewer, prevent self-review, and restrict deployment to `v*` tags. The environment gates this workflow's release job. Organization secrets remain available to other workflows in an allowed repository; if credentials themselves must be approval-gated, use environment secrets instead. These environment secrets take precedence over passed secrets with the same names.

The Maven build step receives no signing or Central credentials. Only the signing step receives the key/passphrase, and only the upload step receives the Central token. The workflow does not grant Central access to applications that merely inherit uetlib-parent or starter-parent.

## Release prerequisites

Publish prerequisite parents/BOMs/libraries first. Prepare the required POM metadata (name, description, URL, SCM, license and developers), Apache license/third-party notices, working source and Javadoc generation, the verified Central namespace and signing public key. The workflow does not manufacture metadata or publish missing dependencies. Enable immutable GitHub releases in the caller repository.

## Validate changes

```sh
python3 -m venv /tmp/uetlib-workflow-tests
/tmp/uetlib-workflow-tests/bin/pip install -r tests/requirements.txt
/tmp/uetlib-workflow-tests/bin/python -m unittest discover -s tests -v
actionlint
shellcheck enable-gh-settings.sh
```

Tests execute the embedded validation and bundling code directly. They cover Maven parent and JAR artifacts, checksums, excluded modules, resource-only recipes, invalid coordinates, missing documentation and tag/repository restrictions. Public CI runs these tests and workflow linting under the required `Build Project` check.
