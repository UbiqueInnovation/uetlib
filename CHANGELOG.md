# CHANGELOG

## 1.0.0

- Skip automatic Spotless formatting in CI builds and releases so formatting checks reject unformatted code.

- Verify bundle ZIP/manifest/POM completion, retry transfers and retain the original bundle for recovery.

- Rename uetlib configuration keys and property references to `ch.uetlib.*`, including Spring bindings, `@Value`,
  conditions, scheduling expressions and configuration files. Migrate external deployment configuration as well.

- Move `uetlib-spring-boot-geo` into the geo repository as `uetlib-geo-spring-boot`, with packages under
  `ch.uetlib.geo.spring.boot`; update consumers and migration mappings. This removes the repo-level release-order cycle
  between geo, job and Spring Boot.

- Replace `ch.ubique:inotify` with `ch.uetlib:uetlib-inotify-java:3.0.1` in the Renovate migration preset.

- Add a repository dependency graph without test dependencies or testing repositories.

- Resolve Central bundle upload paths absolutely so Maven handles root and nested POMs correctly.

- Add the uetlib icon, wordmark and prerelease blueprint logo; replace project-page placeholders.

- Regenerate repository dependency graphs from Maven POMs and list inotify, Error Prone and OpenRewrite on the project
  page.

- Move Java packages and class references from `ch.ubique.uetlib` to `ch.uetlib`.

First Public release.

- Keep public coordinate rules in `renovate-migration.json5`, extended by `renovate-base.json5`.

- Simplify Central publication to `setup-java` and an opt-in Maven release profile; use runner-provided Maven and the
  four existing signing/token secret names. Stable releases require a matching CHANGELOG.md entry. Optional
  `native-artifacts` and `system-packages` inputs stage prebuilt native libraries and their runtime packages.

- Add Apache-2.0 licensing, shared contribution/security guidance and Maven publication metadata across the
  repositories.
- Move Java packages to `ch.uetlib`, provide a combined OpenRewrite migration, and document its command in the
  major-release changelogs.

- Add reusable Maven install and Central publishing workflows with Java 25 by default, scoped organization secrets,
  release validation and local staging/signing.

- Prepare the public `ch.uetlib` Maven coordinate migration and target its planned major releases in Renovate
  replacement PRs.
- Add `uetlib-rewrite` to the project catalogue.

