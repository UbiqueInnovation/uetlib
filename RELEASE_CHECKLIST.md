# Public release prerequisites

The opensourcing branches contain development versions and migration recipes; they are not a published release set yet.

## Known dependency blockers

`uetlib-job` requires `ch.ubique:inotify:2.0`. This artifact is not available from Maven Central, OSGeo or Unidata.
Publish an appropriately licensed public artifact or replace the dependency before releasing the job library and
consumers that require it. An existing developer-local cached copy can validate compilation but does not solve public
consumption.

The former private Datatrans model and service modules are included directly in `uetlib-payment-datatrans`; publishing
the separate client repository is no longer required.

GeoTools and netCDF are intentionally resolved from their official public OSGeo and Unidata release repositories. They
are not hosted on Maven Central. The dependency BOM and shared parents list those public upstreams explicitly; Ubique
Artifactory is not declared in the public POMs.

## When merging the opensourcing PRs

- [ ] TODO: Install the [DCO GitHub App](https://github.com/apps/dco) for every uetlib repository, then rerun
  `enable-gh-settings.sh` to require the app-bound `DCO` check on default/release branches without bypass actors.
  Signed-commit enforcement is temporarily disabled to allow GitHub rebase merges; rerunning the script when ready to
  merge re-enables it. Verify both protections and confirm that a PR missing sign-offs is blocked. Install the app
  before enabling its required check so PRs do not wait for a check that cannot run.

## Before publication

- Finish the separate source/history leak review and review third-party attribution, especially the geo schemas, legacy
  Logback SQL resources and WebP test images/native dependencies.
- Configure Central namespace access, scoped organization signing/publishing secrets and the protected `maven-central`
  environment.
- Release the shared workflows, then replace library CI/release callers with the pinned workflow SHA and matching
  release-tag comment.
- Publish the prerequisite BOMs, parents and libraries in dependency order, using the planned release versions
  documented in their changelogs.
- Publish `uetlib-rewrite:0.1.0` before recommending the changelog migration command to consumers.
- Confirm a consumer can build with an empty local Maven repository and no Ubique credentials, including source/Javadoc
  lookup and service/auto-configuration discovery.
- Enable private vulnerability reporting on the entry repository when it becomes public, and finish Pages/custom-domain
  setup and contributor-facing documentation.
