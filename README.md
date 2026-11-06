# Uetlib Project Repo

Create Issues for all uetlib repos here.

See [shared Maven workflows](WORKFLOWS.md) for build/test and explicit Maven Central
publishing, [contribution guidance](CONTRIBUTING.md), [security reporting](SECURITY.md), and
the [public release checklist](RELEASE_CHECKLIST.md).

## Repository dependency graphs

[Without test dependencies](graph-no-tests.dot.svg) · [Full graph](graph.dot.svg) · [Testing graph](graph-test.dot.svg)

Arrows point from a repository to the repository it references. Modules are grouped by repository;
edge labels distinguish direct dependencies, test dependencies, parents, managed dependencies and build tools.
The full graph includes every local uetlib repository, even standalone ones, except the intentionally excluded
`uetlib-rust*` repositories. Dashed boxes show referenced
Maven artifacts whose sources are outside the checkout. These graphs describe POM references, not a runtime classpath.

The non-test graph omits test-scope references and the test libraries/reference application, while retaining parents,
managed versions and build tools.

Regenerate all DOT sources and SVGs from sibling checkouts with Python 3 and Graphviz installed:

```sh
python3 scripts/update_graphs.py
```

Use `--workspace /path/to/uetlib` to select the directory containing the component checkouts.

## Geo integration migration

`ch.uetlib:uetlib-spring-boot-geo` has moved to the geo repository as
`ch.uetlib:uetlib-geo-spring-boot`. Its Java packages move from `ch.uetlib.spring.boot.geo`
to `ch.uetlib.geo.spring.boot`. Update dependencies and imports, or run the OpenRewrite migration;
the Renovate preset also renames the Maven artifact. This removes the repo-level release-order cycle
between geo, job and Spring Boot. The artifact dependency graph remains acyclic.

See [configuration migration](CONFIGURATION_MIGRATION.md) for the new property prefixes and OpenRewrite command.

## Current uetlib repos with their artifacts

### [uetlib-self-bom](https://github.com/UbiqueInnovation/uetlib-self-bom)

- uetlib-self-bom

### [uetlib-bom](https://github.com/UbiqueInnovation/uetlib-bom)

- uetlib-bom

### [uetlib-parent](https://github.com/UbiqueInnovation/uetlib-parent)

- uetlib-parent

### [uetlib-spring-boot-starter-parent](https://github.com/UbiqueInnovation/uetlib-spring-boot-starter-parent)

- uetlib-spring-boot-starter-parent

### [uetlib-test](https://github.com/UbiqueInnovation/uetlib-test)

- uetlib-test

### [uetlib-spring-boot-test](https://github.com/UbiqueInnovation/uetlib-spring-boot-test)

- uetlib-spring-boot-test

### [uetlib-testcontainers](https://github.com/UbiqueInnovation/uetlib-testcontainers)

- uetlib-testcontainers
- uetlib-testcontainers-influxdb
- uetlib-testcontainers-kafka
- uetlib-testcontainers-mariadb
- uetlib-testcontainers-mongodb
- uetlib-testcontainers-mysql
- uetlib-testcontainers-postgresql
- uetlib-testcontainers-redis

### [uetlib-core](https://github.com/UbiqueInnovation/uetlib-core)

- uetlib-core

### [uetlib-db](https://github.com/UbiqueInnovation/uetlib-db)

- uetlib-db

### [uetlib-geo](https://github.com/UbiqueInnovation/uetlib-geo)

- uetlib-geo
- uetlib-geo-db
- uetlib-geo-job
- uetlib-geo-spring-boot: Spring Boot JSON and Springdoc integration (`ch.uetlib.geo.spring.boot`)

### [uetlib-job](https://github.com/UbiqueInnovation/uetlib-job)

- uetlib-job

### [uetlib-monitoring](https://github.com/UbiqueInnovation/uetlib-monitoring)

- uetlib-monitoring

### [uetlib-payment](https://github.com/UbiqueInnovation/uetlib-payment)

- uetlib-payment
- uetlib-payment-datatrans
- uetlib-payment-postfinance

### [uetlib-spring-boot](https://github.com/UbiqueInnovation/uetlib-spring-boot)

- uetlib-spring-boot
- uetlib-spring-boot-security

### [uetlib-spring-cloud](https://github.com/UbiqueInnovation/uetlib-spring-cloud)

- uetlib-spring-cloud
- uetlib-spring-cloud-security

### [uetlib-storage](https://github.com/UbiqueInnovation/uetlib-storage)

- uetlib-storage

### [uetlib-storage-spring-boot](https://github.com/UbiqueInnovation/uetlib-storage-spring-boot)

- uetlib-storage-spring-boot

### [uetlib-webp](https://github.com/UbiqueInnovation/uetlib-webp)

- uetlib-webp

### [uetlib-testapp](https://github.com/UbiqueInnovation/uetlib-testapp)

- uetlib-testapp

### [uetlib-rewrite](https://github.com/UbiqueInnovation/uetlib-rewrite)

- uetlib-rewrite: versioned OpenRewrite migration recipes

### [uetlib-errorprone](https://github.com/UbiqueInnovation/uetlib-errorprone)

- uetlib-errorprone: compile-time checks for uetlib conventions

### [uetlib-inotify-java](https://github.com/UbiqueInnovation/uetlib-inotify-java)

- uetlib-inotify-java: Linux inotify JNI bindings (LGPL-3.0-or-later)

## License

Except where otherwise noted, original uetlib code is licensed under the [Apache License 2.0](LICENSE). Third-party
files retain their original license terms; see [NOTICE](NOTICE) and any third-party notices in this repository.
