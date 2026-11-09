# Stage independently, publish one batch

Each library builds in its own repository. `mvn-install.yml` builds/tests branch pushes and pull requests with
`clean install`.
Only tag refs deploy to Artifactory using normal Maven deployment for JARs/POMs and attached artifacts.
Stable versions additionally activate `central-release` with `central.publishing.skipUpload=true`: an explicit
deploy-phase execution creates the Central bundle from those same signed artifacts without replacing the normal
Maven deploy binding or contacting Central. The workflow stores the additional completed bundle as a Maven artifact:

```
ch.uetlib.central-bundles:<repository>:<version>:zip
ch.uetlib.central-bundles:<repository>:<version>:json:manifest
```

The descriptor records the Git commit and SHA-256 of the ZIP and every contained file. It is generated only after
the reactor finishes successfully. A network failure can leave a descriptor/POM without a ZIP; neither the descriptor
nor Maven metadata alone establishes a complete deployment. The upload step verifies all three files and the ZIP hash.
Existing release files cannot be overwritten with different bytes. Use a new version
for a rebuilt release, including changed signatures. Snapshot versions are never candidates for Central. Hyphenated
prereleases stay in Artifactory; the numeric starter-parent format remains stable.

## Caller rollout

The implementation is prepared in the entry repo. Publish/release a shared workflow revision, then update callers to
that immutable SHA. Their existing `mvn-publish.yml` calls now stage tagged versions through the same install workflow
rather than uploading to Central individually. GitHub releases describe staged versions; they do not establish Central
availability.

Build callers must pass the Artifactory secrets, and stable tag builds also need the signing key and passphrase. For
callers
with an explicitly mapped Sonar token, extend the mapping:

```yaml
secrets:
  SONAR_TOKEN: ${{ secrets.UBIQUE_SONAR_TOKEN }}
  UB_ARTIFACTORY_USER: ${{ secrets.UB_ARTIFACTORY_USER }}
  UB_ARTIFACTORY_PASSWORD: ${{ secrets.UB_ARTIFACTORY_PASSWORD }}
  UB_ARTIFACTORY_URL: ${{ secrets.UB_ARTIFACTORY_URL }}
  UB_ARTIFACTORY_REPO_UBIQUE: ${{ secrets.UB_ARTIFACTORY_REPO_UBIQUE }}
  SYSTEMS_UBIQUE_SIGNING_KEY_ARMOR_ASC: ${{ secrets.SYSTEMS_UBIQUE_SIGNING_KEY_ARMOR_ASC }}
  SYSTEMS_UBIQUE_SIGNING_KEY_PASSPHRASE: ${{ secrets.SYSTEMS_UBIQUE_SIGNING_KEY_PASSPHRASE }}
```

Publish callers using `secrets: inherit` already pass these names. PR events build/test without deploying. Artifactory
dependency resolution is enabled for authenticated builds so parents and libraries can be built before Central
promotion. `central-release` must exist in the selected parent/POM and use publisher 0.12.0 or later with
`central.publishing.skipUpload` configured. Build prerequisites in dependency order. Testapp and coverage modules remain
excluded from Central publication; they can still build/deploy according to their ordinary Maven configuration.

The bundle is stored in the same Maven repository specified by `UB_ARTIFACTORY_URL` + `UB_ARTIFACTORY_REPO_UBIQUE`.
Ensure this endpoint supports deployment, Maven metadata and immutable release storage; configure Artifactory
permissions to prevent release redeployment as well.

## Version selection and Renovate

`central-release.json` selects one exact version per repository, including every artifact from a multi-module reactor.
The initial entries are planned versions, not claims that bundles already exist. Remove entries not ready for the first
batch; missing bundles fail assembly.

The entry repo's custom Renovate manager reads those versions using the Maven datasource, querying version metadata for
`ch.uetlib.central-bundles` artifacts. Batch assembly verifies that each selected bundle is complete. All changes are
grouped into one PR without automerge. Numeric starter-parent
versions are allowed alongside plain release versions; snapshots and other prereleases are excluded. Review dependency
compatibility when merging updates.

The configured registry is `https://artifactory.ubique.ch/artifactory/ubique`. Adjust it if the staging repository
differs. Renovate needs its own read credentials for that registry, supplied via its existing bot/hostRules
configuration; Actions secrets do not automatically authenticate Renovate. Do not put credentials in this public preset.

## Assemble and promote

Run **Publish Central batch** manually from the trusted default branch. With `publish=false` (the default), it only
downloads and assembles the selected bundles and saves `central-batch` as a workflow artifact. Inspect `batch.json` for
versions, source commits and bundle hashes.

With `publish=true`, a second job waits on the `maven-central` environment approval before uploading the exact assembled
ZIP in one request. Only this job needs `UETLIB_MAVEN_CENTRAL_USERNAME` and `UETLIB_MAVEN_CENTRAL_PASSWORD`. Configure
this environment in the entry repo with required reviewers and default-branch deployment restrictions. The assembly job
needs the four Artifactory secrets in the entry repo.

Assembly checks bundle identities/hashes, inventory, signatures being present, path collisions, and existing Central
files. A completely identical published bundle is skipped; partially published or differing files fail the batch. Files
are never rebuilt, re-signed or renamed during promotion. Signature cryptographic validation remains part of Central
validation. Parent/BOM/library dependency compatibility must be reviewed in the manifest PR; assembly does not run a
consumer build or resolve effective Maven models.

The workflow records a deployment ID immediately after uploading and waits only for validation. Central finishes
publication asynchronously. If upload or validation times out, inspect the recorded deployment in the Portal before
running another publish: an upload whose response was lost may already have been accepted. Uploads are not automatically
retried. Avoid starting a second batch while a previous deployment is still publishing. File-count and size limits still
apply; verify release-event accounting with the first combined deployment.

Already-published files are compared byte-for-byte, including signatures. A rebuilt bundle for an existing version is
not interchangeable with the original published one. Remove such entries from the selection rather than attempting to
overwrite them.

## Recover a failed bundle upload

A connection reset during `deploy-file` can leave the manifest and Maven POM uploaded while the ZIP is missing.
The workflow now retries deployment three times and only succeeds once the uploaded ZIP hash matches its manifest
and all three files exist. It also saves the original files as `central-bundle-<run-attempt>` in the workflow artifacts,
even when the upload fails. Maven's `pom.xml not found in central-bundle.zip` message is informational for this
generic ZIP artifact; the generated Maven POM is separate.

Retry deployment with those saved files, rather than rebuilding or re-signing the release. This preserves the manifest
and the exact signed artifacts. Existing matching files may be uploaded again according to Artifactory's redeployment
permissions; different manifests or ZIP contents for a completed coordinate are rejected. If the original ZIP was not
retained by an older workflow, use a new release version. A persistent connection reset needs investigation in the
Artifactory/reverse-proxy logs; the client log alone cannot identify its cause.
