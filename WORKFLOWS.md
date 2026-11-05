# Shared Maven workflows

Library repositories build and stage independently in Artifactory. The entry repo promotes selected stable versions to
Central as one deployment. See [batch publishing](CENTRAL_BATCH.md) for the manifest, Renovate, approval and promotion
process.

## Build, test and stage

```yaml
jobs:
  build:
    uses: UbiqueInnovation/uetlib/.github/workflows/mvn-install.yml@<full-commit-sha>
    secrets: inherit
```

The workflow uses runner Maven and Temurin Java 25 by default. Override `java-version` for Java 17 projects such as
rewrite; `pom` defaults to `pom.xml`. Every authenticated build deploys its Maven artifacts to Artifactory using the normal Maven deploy plugin. Stable versions
add `central-release` with `central.publishing.skipUpload=true`: an additional deploy-phase execution creates a bundle
from the same signed artifacts. The workflow then uploads only that extra ZIP and its versioned descriptor to Artifactory. No individual repo uploads to Central. PR events run
`clean install` without publishing credentials.

Artifactory secrets are `UB_ARTIFACTORY_USER`, `UB_ARTIFACTORY_PASSWORD`, `UB_ARTIFACTORY_URL` and
`UB_ARTIFACTORY_REPO_UBIQUE`. The pinned s4u Maven settings action configures
`ubique-artifactory-virtual` for dependency resolution with its server credentials. Build plugins use Maven's default plugin repositories.
Stable versions also require `SYSTEMS_UBIQUE_SIGNING_KEY_ARMOR_ASC` and
`SYSTEMS_UBIQUE_SIGNING_KEY_PASSPHRASE`. No signing key ID is needed. These must be available in the calling repository;
an
environment on the entry repo does not provide secrets to other repositories.

Optional `sonar: true` runs analysis in the same job after tests. Map `SONAR_TOKEN` from the caller's
`UBIQUE_SONAR_TOKEN`. If you use an explicit secrets mapping for Sonar, also map the Artifactory and signing secrets as
shown in [CENTRAL_BATCH.md](CENTRAL_BATCH.md#caller-rollout).

## Tagged versions

```yaml
jobs:
  publish:
    permissions:
      contents: write
    uses: UbiqueInnovation/uetlib/.github/workflows/mvn-publish.yml@<full-commit-sha>
    secrets: inherit
```

The tag workflow validates `v*` versions, rejects snapshots, sets reactor versions and calls the shared install
workflow. Stable tags require a non-empty exact-version heading in `CHANGELOG.md`. Numeric starter-parent versions such
as `4.1.1-2026.11.0` are stable; other hyphenated versions are prereleases. Optional GitHub release creation happens
after staging in Artifactory, before Central promotion. Disable it with `create-github-release: false` if desired.

## Native builds

Both workflows accept `native-artifacts` (space-separated required artifact names from earlier jobs) and
`system-packages` (Ubuntu packages). Callers must depend on the native-producing jobs. Artifact contents are merged into
`src/main/resources/native` before Maven; missing/empty artifacts fail the build. WebP requires all three platform
artifacts. Inotify builds Linux JNI in Maven and retains LGPL-3.0-or-later licensing.

## Central promotion

Only **Publish Central batch** uses `UETLIB_MAVEN_CENTRAL_USERNAME` and `UETLIB_MAVEN_CENTRAL_PASSWORD`. Configure its
`maven-central`
environment with approval and default-branch restrictions. Start with its default assembly-only mode, inspect the batch
artifact, then enable publication on a subsequent manual run. Publication waits for validation; Central completes
asynchronously.

Release prerequisite parents/BOMs/libraries to Artifactory in dependency order. Configure Renovate's registry
credentials separately. Shared workflow changes take effect in callers only after committing/releasing this revision and
updating their immutable pins and secret mappings.

## Validate changes

```sh
actionlint
shellcheck enable-gh-settings.sh
```
