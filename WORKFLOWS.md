# Shared Maven workflows

The reusable workflows live in this repository. Publishing uses the opt-in `central-release` Maven profile; normal
builds and consumers do not activate it.

Both accept `pom` (default `pom.xml`) and `java-version` (default `25`) and use Maven already installed on the GitHub
runner. Java 17 projects such as uetlib-rewrite must override `java-version`.

## Build and test

```yaml
name: Build
on:
  push:
    branches: [ '**' ]
  pull_request:
permissions:
  contents: read
jobs:
  build:
    uses: UbiqueInnovation/uetlib/.github/workflows/mvn-install.yml@<full-commit-sha> # v1.2.3
```

The workflow checks out the caller, sets up Java/Maven and caching, and runs `mvn clean install`, including verification
and tests. SonarCloud is optional. Add the following to the calling job:

```yaml
    with:
      sonar: true
    secrets:
      SONAR_TOKEN: ${{ secrets.UBIQUE_SONAR_TOKEN }}
```

Analysis runs after install in the same workspace, using the existing test and coverage results without rerunning tests.
Builds with Sonar disabled need no secrets. A reusable workflow changes the displayed check name; check branch rules
against the resulting job name before replacing existing CI.

## Publish a library

```yaml
name: Publish
on:
  push:
    tags: [ 'v*' ]
permissions:
  contents: read
jobs:
  publish:
    permissions:
      contents: write
    uses: UbiqueInnovation/uetlib/.github/workflows/mvn-publish.yml@<full-commit-sha> # v1.2.3
    secrets: inherit
```

Replace the placeholder SHA and example tag comment with an actual released workflow revision. Callers can override
`java-version`, `pom`, `environment` (default `maven-central`) and `create-github-release` (default `true`). They cannot
supply arbitrary Maven arguments or a different upload endpoint.

## Native libraries

Both workflows accept two optional inputs for libraries that package native code:

- `native-artifacts`: space-separated names of artifacts uploaded by earlier jobs in the same caller run. Every listed
  artifact must exist and be non-empty; its contents are merged into `src/main/resources/native/` before Maven runs. The
  calling job must `need` the jobs that produce them.
- `system-packages`: space-separated Ubuntu package names installed before Maven, e.g. runtime libraries loaded by
  native tests.

uetlib-webp builds each platform library in its own caller matrix job, uploads it as `native-<classifier>` containing
`<classifier>/libuetlib_webp_native.*`, and passes all three names, so neither its build nor a release can produce a JAR
without a platform library. uetlib-inotify-java is Linux-only and builds its JNI library inside the Maven lifecycle, so
it needs neither input. Its release remains LGPL-3.0-or-later.

Publishing accepts release tags such as `v3.0.0`, `v3.0.0-alpha.1` and `v4.1.1-2026.11.0`, and rejects snapshots.
`actions/github-script` validates the tag and supplies the published version. Stable releases require a non-empty
section in the checked-out `CHANGELOG.md` with an exact version heading (for example `## 3.0.0`, `## [3.0.0]` or
`## v3.0.0`); prereleases do not. Calendar versions and numeric starter-parent suffixes such as `4.1.1-2026.11.0` count
as stable. The same classification controls the GitHub release prerelease flag. Repository names, Maven coordinates and
branch ancestry are not restricted by the workflow; Maven and Central validate the artifacts and metadata. Coverage and
application exclusions are configured in their POMs.

The release job waits for its GitHub environment approval, uses `actions/setup-java` to configure the `central` Maven
server and import the signing key, sets reactor versions from the release tag, then runs:

```sh
mvn --batch-mode --no-transfer-progress -Pcentral-release clean deploy
```

The `central-release` profile is defined in `uetlib-parent` and the standalone BOM, self-bom, starter-parent, rewrite
and errorprone POMs. It uses `maven-gpg-plugin` to sign POMs and artifacts, Maven source/Javadoc plugins for
attachments, and Sonatype's official `central-publishing-maven-plugin` to stage, checksum, bundle, upload and wait until
validation succeeds. Central then finishes publication asynchronously; the workflow creates the optional GitHub release
after validation, so artifacts may not yet be available for download. There is no custom signing, ZIP manipulation, HTTP
client or polling loop.

The profile includes repository license/notice files as ordinary Maven resources under `META-INF/uetlib`. Coverage
modules and the test application set `central.publishing.skip=true` and are excluded from signing and publication. The
profile is never activated automatically; private consumers retain their ordinary deployment behavior.

For a local rehearsal with a disposable signing key, add `-Dcentral.publishing.skipUpload=true`. This produces the
signed Central bundle without uploading it. After a publication timeout, inspect the Central deployment before retrying
because release versions cannot be overwritten.

## Credentials and approvals

Create one set of organization secrets with **Selected repositories** access, restricted to the libraries that publish:

- `MAVEN_CENTRAL_USERNAME`: Central Portal user-token username.
- `MAVEN_CENTRAL_PASSWORD`: Central Portal user-token password.
- `MAVEN_SIGNING_KEY_ARMOR_ASC`: ASCII-armored private signing key; publish its public key separately.
- `MAVEN_SIGNING_KEY_PASSPHRASE`: signing-key passphrase; empty is allowed for an unencrypted key.

Callers use `secrets: inherit`. The shared workflow reads only these four secrets. An explicit four-secret mapping is
also supported if a caller should not inherit other secrets.

In each calling repository, configure the `maven-central` environment with the existing admin team as required reviewer,
prevent self-review, and restrict deployment to `v*` tags. The environment gates this workflow's release job.
Organization secrets remain available to other workflows in an allowed repository; if credentials themselves must be
approval-gated, use environment secrets instead. These environment secrets take precedence over passed secrets with the
same names.

The publish step exposes the token credentials and `MAVEN_GPG_PASSPHRASE` only inside the environment-gated release job.
`setup-java` manages the imported signing key. No `MAVEN_SIGNING_KEY_ID` secret is needed when one signing key is
imported.

## Release prerequisites

Publish prerequisite parents/BOMs/libraries first. Prepare the required POM metadata (name, description, URL, SCM,
license and developers), repository license and third-party notices (Apache-2.0; LGPL-3.0-or-later for
uetlib-inotify-java), working source and Javadoc generation, the verified Central namespace and signing public key. The
workflow does not manufacture metadata or publish missing dependencies. Enable immutable GitHub releases in the caller
repository.

## Validate changes

```sh
python3 -m venv /tmp/uetlib-workflow-tests
/tmp/uetlib-workflow-tests/bin/pip install -r tests/requirements.txt
/tmp/uetlib-workflow-tests/bin/python -m unittest discover -s tests -v
actionlint
shellcheck enable-gh-settings.sh
```

Tests execute the release validation and native staging/package scripts directly and check the secret contract,
environment gate, action pins, shell syntax and publication/release ordering. Public CI runs these tests and workflow
linting under the required `Build Project` check.

## Prerelease publishing

Tags classified as prereleases (for example `v2026.11.0-alpha.1`) deploy to Ubique Artifactory without activating
`central-release`. Tags with a hyphen suffix use Artifactory, except numeric starter-parent versions such as
`v4.1.1-2026.11.0`, which publish to Central as stable releases. Both routes create the corresponding GitHub release
when enabled.

Prereleases use the existing `UB_ARTIFACTORY_USER`, `UB_ARTIFACTORY_PASSWORD`, `UB_ARTIFACTORY_URL` and
`UB_ARTIFACTORY_REPO_UBIQUE` secrets from the calling repository. Callers using `secrets: inherit` already pass them.
The URL and repository values are concatenated as in the previous Artifactory workflows. Central signing credentials are
only needed for stable releases.
