# Stage independently, publish one batch

Each library builds in its own repository. `mvn-install.yml` now runs tests and deploys snapshots/prereleases to Artifactory. For a stable version it runs `mvn -Pcentral-release -Dcentral.publishing.skipUpload=true clean deploy`: the plugin signs and packages the reactor without contacting Central. The workflow uploads the exact bundle contents to Artifactory and stores the completed bundle as a Maven artifact:

```
ch.uetlib.central-bundles:<repository>:<version>:zip
ch.uetlib.central-bundles:<repository>:<version>:json:manifest
```

The descriptor records the Git commit and SHA-256 of the ZIP and every contained file. It becomes available only after the reactor finishes successfully. Existing release files cannot be overwritten with different bytes. Use a new version for a rebuilt release, including changed signatures. Snapshot versions are never candidates for Central. Hyphenated prereleases stay in Artifactory; the numeric starter-parent format remains stable.

## Caller rollout

The implementation is prepared in the entry repo. Publish/release a shared workflow revision, then update callers to that immutable SHA. Their existing `mvn-publish.yml` calls now stage tagged versions through the same install workflow rather than uploading to Central individually. GitHub releases describe staged versions; they do not establish Central availability.

Build callers must pass the Artifactory secrets, and stable builds also need the signing key and passphrase. For callers with an explicitly mapped Sonar token, extend the mapping:

```yaml
secrets:
  SONAR_TOKEN: ${{ secrets.UBIQUE_SONAR_TOKEN }}
  UB_ARTIFACTORY_USER: ${{ secrets.UB_ARTIFACTORY_USER }}
  UB_ARTIFACTORY_PASSWORD: ${{ secrets.UB_ARTIFACTORY_PASSWORD }}
  UB_ARTIFACTORY_URL: ${{ secrets.UB_ARTIFACTORY_URL }}
  UB_ARTIFACTORY_REPO_UBIQUE: ${{ secrets.UB_ARTIFACTORY_REPO_UBIQUE }}
  MAVEN_SIGNING_KEY_ARMOR_ASC: ${{ secrets.MAVEN_SIGNING_KEY_ARMOR_ASC }}
  MAVEN_SIGNING_KEY_PASSPHRASE: ${{ secrets.MAVEN_SIGNING_KEY_PASSPHRASE }}
```

Publish callers using `secrets: inherit` already pass these names. PR events build/test without deploying. Artifactory dependency resolution is enabled for authenticated builds so parents and libraries can be built before Central promotion. `central-release` must exist in the selected parent/POM and use publisher 0.12.0 or later with `central.publishing.skipUpload` configured. Build prerequisites in dependency order. Testapp and coverage modules remain excluded from Central publication; they can still build/deploy according to their ordinary Maven configuration.

The bundle is stored in the same Maven repository specified by `UB_ARTIFACTORY_URL` + `UB_ARTIFACTORY_REPO_UBIQUE`. Ensure this endpoint supports deployment, Maven metadata and immutable release storage; configure Artifactory permissions to prevent release redeployment as well.

## Version selection and Renovate

`central-release.json` selects one exact version per repository, including every artifact from a multi-module reactor. The initial entries are planned versions, not claims that bundles already exist. Remove entries not ready for the first batch; missing bundles fail assembly.

The entry repo's custom Renovate manager reads those versions using the Maven datasource, querying only completed `ch.uetlib.central-bundles` artifacts. All changes are grouped into one PR without automerge. Numeric starter-parent versions are allowed alongside plain release versions; snapshots and other prereleases are excluded. Review dependency compatibility when merging updates.

The configured registry is `https://artifactory.ubique.ch/artifactory/backend`. Adjust it if the staging repository differs. Renovate needs its own read credentials for that registry, supplied via its existing bot/hostRules configuration; Actions secrets do not automatically authenticate Renovate. Do not put credentials in this public preset.

## Assemble and promote

Run **Publish Central batch** manually from the trusted default branch. With `publish=false` (the default), it only downloads and assembles the selected bundles and saves `central-batch` as a workflow artifact. Inspect `batch.json` for versions, source commits and bundle hashes.

With `publish=true`, a second job waits on the `maven-central` environment approval before uploading the exact assembled ZIP in one request. Only this job needs `MAVEN_CENTRAL_USERNAME` and `MAVEN_CENTRAL_PASSWORD`. Configure this environment in the entry repo with required reviewers and default-branch deployment restrictions. The assembly job needs the four Artifactory secrets in the entry repo.

Assembly checks bundle identities/hashes, inventory, signatures being present, path collisions, and existing Central files. A completely identical published bundle is skipped; partially published or differing files fail the batch. Files are never rebuilt, re-signed or renamed during promotion. Signature cryptographic validation remains part of Central validation. Parent/BOM/library dependency compatibility must be reviewed in the manifest PR; assembly does not run a consumer build or resolve effective Maven models.

The workflow records a deployment ID immediately after uploading and waits only for validation. Central finishes publication asynchronously. If upload or validation times out, inspect the recorded deployment in the Portal before running another publish: an upload whose response was lost may already have been accepted. Uploads are not automatically retried. Avoid starting a second batch while a previous deployment is still publishing. File-count and size limits still apply; verify release-event accounting with the first combined deployment.

Already-published files are compared byte-for-byte, including signatures. A rebuilt bundle for an existing version is not interchangeable with the original published one. Remove such entries from the selection rather than attempting to overwrite them.
