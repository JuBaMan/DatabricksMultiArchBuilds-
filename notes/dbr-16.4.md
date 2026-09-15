# Databricks Runtime 16.4 LTS

Release notes: <https://docs.databricks.com/aws/en/release-notes/runtime/16.4lts>

## Values

| Variable                      | Value                          | Source                                                                                           |
| ----------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------ |
| Ubuntu tag                    | `noble-20250404`               | "Ubuntu 24.04.2 LTS"; first noble tag after 24.04.2 (2025-02-20), before 24.04.3 (2025-08-07)   |
| `PYTHON_VERSION`              | `3.12`                         | "Python: 3.12.3"                                                                                 |
| `PIP_VER`                     | `24.2.0`                       | `pip==24.2` in the library table                                                                 |
| `SETUPTOOLS_PIN`              | `74.0.0`                       | `setuptools==74.0.0` in the library table                                                        |
| `PANDAS_VER`                  | `1.5.3`                        | `pandas==1.5.3` in the library table                                                             |
| `CLUSTER_JDK_MAJOR`           | `17`                           | "Java: Zulu17.54+21-CA"                                                                          |
| `CLUSTER_ZULU_ID`             | `zulu17.54.21-ca-jdk17.0.13`   | Azul tarball for Zulu 17.54.21 / JDK 17.0.13                                                     |
| `CLUSTER_ZULU_ARM64_EMBEDDED` | `false`                        | aarch64 tarball exists under `cdn.azul.com/zulu/bin`                                             |
| `SPARK_JDK_MAJOR`             | `17`                           | same as the cluster JDK, so the local stage downloads no second JDK                              |
| `SPARK_ZULU_ID`               | `zulu17.54.21-ca-jdk17.0.13`   | unused at build time (JDK 17 already present), kept for completeness                             |
| `SPARK_VER`                   | `3.5.2`                        | "powered by Apache Spark 3.5.2"                                                                  |
| `HADOOP_VER`                  | `3.3.6`                        | Spark 3.5.2 POM says `<hadoop.version>3.3.4`; the repo uses 3.3.6 for all Spark 3.5.x            |
| `HADOOP_ARM64_SUFFIX`         | `-aarch64`                     | `hadoop-3.3.6-aarch64.tar.gz` exists on downloads.apache.org                                     |
| `DELTA_VER`                   | `3.3.1`                        | "Delta Lake: 3.3.1"                                                                              |
| `SCALA_BIN`                   | `2.12`                         | Spark 3.5.x delta-spark artifact                                                                 |

## Relation to 16.3

The `16.3` entry on `main` was in practice built from the 16.4 LTS library
table: `diff <(sort -f requirements/dbs-16.3.txt) <(sort -f requirements/dbs-16.4.txt)`
is empty. 16.4 LTS differs only in:

- Ubuntu point release 24.04.2 (`noble-20250404` instead of `noble-20241015`)
- Delta Lake 3.3.1 (16.3 used 3.3.0)
- the cluster image carries **Java 17, not Java 8**. The custom-container
  docs say to "match the JDK to the default Java version of your target
  Databricks Runtime", and 16.4's default is Zulu 17. Consequently the
  local stage finds `/opt/java17` already present and skips its JDK
  download; `JAVA_HOME=/opt/java` -> `/opt/java17`.

`delta-spark==3.3.1` requires `pyspark>=3.5.3` while the runtime ships
Spark 3.5.2; the local stage installs it with `--no-deps` next to the jars,
so this is not a problem. `delta-spark` is not in the requirements file.

## Verification (2026-09-15, no Docker daemon; HTTP HEAD + static checks)

| Check                                                                                  | Result |
| -------------------------------------------------------------------------------------- | ------ |
| `ubuntu:noble-20250404` amd64 layer `etc/os-release`                                   | `VERSION="24.04.2 LTS (Noble Numbat)"` |
| `zulu17.54.21-ca-jdk17.0.13-linux_x64.tar.gz` / `-linux_aarch64.tar.gz`                | 200 / 200 |
| `spark-3.5.2-bin-without-hadoop.tgz` and `.sha512` (archive.apache.org)                | 200 / 200; GNU `hash  file` format, `sha512sum --check` OK |
| `hadoop-3.3.6.tar.gz`, `hadoop-3.3.6-aarch64.tar.gz` and their `.sha512`               | 200 x4; BSD `SHA512 (hadoop-3.3.6-RC1.tar.gz) = ...` format, filename rewritten by the Hadoop step's `sed`, `sha512sum --check` OK for both |
| `delta-spark_2.12-3.3.1.jar`, `delta-storage-3.3.1.jar` (Maven Central)                | 200 / 200 |
| `https://pypi.org/pypi/delta-spark/3.3.1/json`                                         | 200 |
| every `name==version` in `requirements/dbs-16.4.txt` on PyPI                           | 167/167 found |
| `python scripts/check_dockerfile.py Dockerfile.builder.new Dockerfile.runtime.new`     | pass; 16.4 in the FROM router and all three case blocks |

## Packages compiled from source in the builder

No cp312 wheel on PyPI (built with `build-essential`; no Rust needed):

- `pandas==1.5.3` (step 5, under the `Cython<3` constraint)
- `kiwisolver==1.4.4` (C++, `cppy` build dep)
- `psutil==5.9.0`
- `psycopg2==2.9.3` (needs `libpq-dev`, present)
- `wrapt==1.14.1`

sdist only:

- `dbus-python==1.3.2` (needs `libdbus-1-dev`, `libdbus-glib-1-dev`, `patchelf`, present)
- `PyGObject==3.48.2` (needs `libgirepository1.0-dev`, `libcairo2-dev`, `gobject-introspection`, present; `pycairo` is in the table)
- `lazr.uri==1.0.6`, `ssh-import-id==5.11`, `wadllib==1.3.6` (pure Python)

`cryptography==42.0.5` and `tornado==6.4.1` ship `abi3` wheels for both
x86_64 and aarch64, so nothing in the table needs Rust/cargo.

This is the same set the 16.3 builder already compiles.

## Build

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.builder.new --build-arg DATABRICKS_RUNTIME=16.4 \
  -t lcccguy/databricks16.4-wheels:latest --push .

docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.runtime.new --target cluster --build-arg DATABRICKS_RUNTIME=16.4 \
  -t lcccguy/databricks16.4:cluster --push .

docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.runtime.new --target local --build-arg DATABRICKS_RUNTIME=16.4 \
  -t lcccguy/databricks16.4:latest --push .
```
