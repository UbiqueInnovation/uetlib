# CHANGELOG

## 1.0.0

First Public release.

- Keep public coordinate rules in `renovate-migration.json5`, extended by `renovate-base.json5`.

- Simplify Central publication to `setup-java` and an opt-in Maven release profile; use runner-provided Maven and the
  four existing signing/token secret names. Stable releases require a matching CHANGELOG.md entry. Optional
  `native-artifacts` and `system-packages` inputs stage prebuilt native libraries and their runtime packages.

- Add Apache-2.0 licensing, shared contribution/security guidance and Maven publication metadata across the
  repositories.
- Move Java packages to `ch.ubique.uetlib`, provide a combined OpenRewrite migration, and document its command in the
  major-release changelogs.

- Add reusable Maven install and Central publishing workflows with Java 25 by default, scoped organization secrets,
  release validation and local staging/signing.
- Add workflow tests and CI for the required `Build Project` check.

- Prepare the public `ch.ubique.uetlib` Maven coordinate migration and target its planned major releases in Renovate
  replacement PRs.
- Add `uetlib-rewrite` to the project catalogue.

