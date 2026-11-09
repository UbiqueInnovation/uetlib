# Configuration migration

The public uetlib configuration namespaces now use `ch.uetlib`. Apply the new names together with the corresponding
library releases. Spring Boot's updated bindings are in `4.0.1`; storage Spring Boot's are in `3.0.1`.
Other libraries keep their existing planned release lines. Values, defaults and credentials are unchanged.

| Old prefix                            | New prefix                           |
|---------------------------------------|--------------------------------------|
| `ch.ubique.backend.spring.boot`       | `ch.uetlib.spring.boot`              |
| `ch.ubique.backend.spring.validation` | `ch.uetlib.spring.boot.validation`   |
| `ch.ubique.backend.job`               | `ch.uetlib.job`                      |
| `ch.ubique.backend.job.testapp`       | `ch.uetlib.testapp`                  |
| `ch.ubique.backend.monitoring`        | `ch.uetlib.monitoring`               |
| `ch.ubique.backend.storage`           | `ch.uetlib.storage`                  |
| `ch.ubique.backend.payment`           | `ch.uetlib.payment`                  |
| `ch.ubique.datatrans`                 | `ch.uetlib.payment.datatrans.client` |

Equivalent intermediate prefixes under `ch.ubique.uetlib` are supported too. Longest-prefix matching keeps testapp
settings separate from job settings. Unknown namespaces are unchanged. Existing `uetlib.webp.*` native loader settings
are outside these legacy Ubique namespaces and remain unchanged.

The Datatrans adapter uses `ch.uetlib.payment.datatrans.*`. Its Feign bridge maps credentials to the separate
`ch.uetlib.payment.datatrans.client.*` prefix for the standalone client.

## Run the migration

Use JDK 25 and a recipe release containing this migration:

```sh
mvn -U org.openrewrite.maven:rewrite-maven-plugin:6.46.1:dryRun \
  -Drewrite.recipeArtifactCoordinates=ch.uetlib:uetlib-rewrite:RELEASE \
  -Drewrite.activeRecipes=ch.uetlib.MigrateToPublicUetlib
```

Review `target/rewrite/rewrite.patch`; replace `dryRun` with `run` to apply it. The combined recipe migrates Maven
coordinates/versions, packages and configuration. To migrate only configuration, select
`ch.uetlib.rewrite.MigrateConfigurationProperties`. The package-only recipe still preserves configuration keys.
These local recipe changes must be published before `RELEASE` can select them.

The configuration recipe covers:

- Flat `.properties` keys and flat/nested YAML keys, including custom property files.
- Java string literals in bindings, `@Value`, conditions, scheduling expressions, test properties and property lookups.
- Placeholders with defaults, including nested fallback placeholders.
- XML configuration placeholders and Spring configuration metadata.
- Environment-variable prefixes in scanned YAML/properties/XML/JSON configuration, for example
  `CH_UBIQUE_BACKEND_JOB_INTERFACE_SECRET` becomes `CH_UETLIB_JOB_INTERFACE_SECRET`.

Class-name strings and package scans belong to the package recipe. Review Kotlin, dynamically constructed keys,
command-line flags, shell scripts and deployment configuration outside the scanned project separately. Update external
secrets/configuration stores and environment-variable names before deploying the new bindings. No old-key alias is
provided by the libraries.
