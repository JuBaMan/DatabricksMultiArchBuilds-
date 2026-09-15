# Databricks Runtime 17.3 LTS

Release notes: https://docs.databricks.com/aws/en/release-notes/runtime/17.3lts

First Spark 4 runtime on this repo. Everything below was checked without a
Docker daemon: static checks (`scripts/check_dockerfile.py`), HTTP HEAD
requests, and reading artifacts (tarball listings, checksum files, PyPI JSON).

## Values

| Variable                      | Value                              | Source                                                                                     |
| ----------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------ |
| Base image                    | `ubuntu:noble-20250910`            | "Ubuntu 24.04.3 LTS"; first noble tag after 24.04.3 (2025-08-07). Layer's `etc/os-release`: `VERSION="24.04.3 LTS (Noble Numbat)"` |
| `PYTHON_VERSION`              | `3.12`                             | "Python: 3.12.3" (noble's native `python3.12` is 3.12.3)                                   |
| `PIP_VER`                     | `25.0.1`                           | `pip` pin in "Installed Python libraries"                                                  |
| `SETUPTOOLS_PIN`              | `74.0.0`                           | `setuptools` pin                                                                           |
| `PANDAS_VER`                  | `2.2.3`                            | `pandas` pin                                                                               |
| `CLUSTER_JDK_MAJOR`           | `17`                               | "Java: Zulu17.58+21-CA" (JDK 17.0.15); custom-container spec says match the runtime's Java |
| `CLUSTER_ZULU_ID`             | `zulu17.58.21-ca-jdk17.0.15`       | Azul CDN tarball id for 17.0.15                                                            |
| `CLUSTER_ZULU_ARM64_EMBEDDED` | `false`                            | JDK 17 aarch64 lives under `cdn.azul.com/zulu/bin`                                         |
| `SPARK_JDK_MAJOR`             | `17`                               | Spark 4.0.0 requires Java 17+; `/opt/java17` already exists from the cluster stage, so nothing is downloaded |
| `SPARK_ZULU_ID`               | `zulu17.58.21-ca-jdk17.0.15`       | Same id (only used if the cluster JDK were missing)                                       |
| `SPARK_VER`                   | `4.0.0`                            | "powered by Apache Spark 4.0.0"                                                            |
| `HADOOP_VER`                  | `3.4.1`                            | `<hadoop.version>3.4.1` in `spark-parent_2.13-4.0.0.pom` on Maven Central                  |
| `HADOOP_ARM64_SUFFIX`         | (empty)                            | `downloads.apache.org/hadoop/common/hadoop-3.4.1/` has no `-aarch64` tarball (HEAD 404)    |
| `DELTA_VER`                   | `4.0.0`                            | "Delta Lake: 4.0.0"                                                                        |
| `SCALA_BIN`                   | `2.13`                             | Spark 4.0.0 is Scala 2.13 only (`jars/scala-library-2.13.16.jar`)                          |

Other pins from the notes that the Dockerfiles rely on: numpy 2.1.3,
pyarrow 19.0.1, Cython 3.0.12, grpcio 1.67.0, protobuf 5.29.4, virtualenv
20.29.3, scikit-learn 1.6.1, azure-identity 1.20.0, wheel 0.45.1.

## Verification results

| Check                                                                                     | Result |
| ----------------------------------------------------------------------------------------- | ------ |
| `zulu17.58.21-ca-jdk17.0.15-linux_x64.tar.gz` / `-linux_aarch64.tar.gz` on cdn.azul.com   | 200 / 200 |
| `spark-4.0.0-bin-without-hadoop.tgz` + `.sha512` on archive.apache.org                    | 200 / 200; tarball downloaded (450 MB), `sha512sum --check` OK. GNU style `hash  filename`, same as 3.x |
| `hadoop-3.4.1.tar.gz` + `.sha512` on downloads.apache.org                                 | 200 / 200; `.sha512` is BSD style `SHA512 (hadoop-3.4.1.tar.gz) = ...`; the `-RC` sed is a no-op and `sha512sum --check` parses it for `hadoop-3.4.1.tar.gz` |
| `hadoop-3.4.1-aarch64.tar.gz`                                                             | 404 (expected; suffix left empty) |
| `delta-spark_2.13-4.0.0.jar`, `delta-storage-4.0.0.jar` on Maven Central                  | 200 / 200 |
| `delta-spark==4.0.0` on PyPI                                                              | 200; `py3-none-any` wheel; requires `pyspark>=4.0.0`, `importlib-metadata>=1.0.0` (installed `--no-deps` after PySpark) |
| `spark-parent_2.13-4.0.0.pom`                                                             | `java.version=17`, `scala.binary.version=2.13`, `hadoop.version=3.4.1` |
| `scripts/check_dockerfile.py` on both Dockerfiles                                         | passes; 17.3 in the FROM router and all three case blocks, no CRLF |
| Every `name==version` in `requirements/dbs-17.3.txt` (231 pins)                           | exists on PyPI |

## PySpark packaging in Spark 4 (shared-step change)

Spark 4.0.0's binary distribution has **no `python/setup.py`**. The tarball
listing shows only `python/packaging/{classic,connect,client}/setup.py`, and
`dev/make-distribution.sh` runs `python3 packaging/classic/setup.py sdist`
from `python/`. Run that way the script finds `../RELEASE` and the single
`spark*core*.jar`, copies itself to `python/setup.py`, builds the symlink
farm, writes `dist/pyspark-4.0.0.tar.gz` under `python/` and removes the
copies again. It uses plain `setuptools.setup` (no `setup_requires`, no
`pyproject.toml`), so setuptools 74.0.0 handles `sdist` fine.
`install_requires` is `py4j==0.10.9.9`; the optional extras want
`pandas>=2.0.0`, `pyarrow>=11.0.0`, `numpy>=1.21`, `grpcio>=1.67.0`,
`grpcio-status>=1.67.0`, `googleapis-common-protos>=1.65.0`; the 17.3 pins
satisfy all of them. `python_requires>=3.9`.

The PySpark step therefore uses `setup.py` when it exists (Spark 3.x) and
`packaging/classic/setup.py` otherwise. That is the only shared step that
changed for 17.3.

## Hadoop 3.4.1 on arm64

Apache ships `hadoop-3.4.1-aarch64.tar.gz` for neither 3.4.1 nor 3.4.2 (3.4.0
and 3.4.3 have one). With `HADOOP_ARM64_SUFFIX` empty the Hadoop step computes
`FILE=hadoop-3.4.1.tar.gz` on arm64, verifies the same checksum as on amd64,
and then runs `rm -rf hadoop-3.4.1/lib/native`. Consequence: the arm64 local
image has no native Hadoop library, so Spark logs
`WARN NativeCodeLoader: Unable to load native-hadoop library for your
platform... using builtin-java classes where applicable` once at start-up.
Everything else is pure Java; there is no functional loss for local
development (native compression codecs fall back to Java implementations).
amd64 is unaffected.

## Spark 4 / Scala 2.13 / Java 17

- Spark 4.0.0 ships only Scala 2.13 builds; Delta must be the `_2.13`
  artifact (`delta-spark_2.13-4.0.0.jar`). The Scala version is irrelevant to
  the Python API but matters for the jar name.
- Spark 4 requires Java 17+. The cluster stage already installs JDK 17 (the
  runtime's own Java), so the local stage's conditional JDK step exits early
  and `/opt/spark-java -> /opt/java17`. This is the first runtime where the
  cluster and Spark JDKs coincide on a non-8 major.
- Hadoop 3.4.1 with Java 17 is Spark 4.0's default profile
  (`java.version=17`, `hadoop.version=3.4.1` in the POM).
- PySpark 4.0.0 pins `py4j==0.10.9.9` (jar present as `jars/py4j-0.10.9.9.jar`).

## Packages compiled from source in the builder

Requirements sweep against PyPI (cp312, manylinux, aarch64):

| Package                | Situation                          | Builder dependency that covers it                          |
| ---------------------- | ---------------------------------- | ---------------------------------------------------------- |
| `psutil==5.9.0`        | no cp312 wheel                     | `build-essential`, `python3.12-dev`                        |
| `psycopg2==2.9.3`      | no cp312 wheel                     | `libpq-dev` (`pg_config`)                                  |
| `dbus-python==1.3.2`   | sdist only                         | `libdbus-1-dev`, `libdbus-glib-1-dev`, `patchelf`; meson/ninja via build isolation |
| `PyGObject==3.48.2`    | sdist only                         | `gobject-introspection`, `libgirepository1.0-dev`, `libcairo2-dev`; pycairo/meson via build isolation |
| `lazr.uri==1.0.6`, `ssh-import-id==5.11`, `wadllib==1.3.6` | sdist only, pure Python | none needed                                     |
| `pyiceberg==0.9.0`     | cp312 wheels are x86_64 only; aarch64 builds from sdist | poetry-core + Cython>=3 + setuptools via build isolation, one C extension (`avro/decoder_fast.pyx`) with gcc; the build script marks the extension `allowed_to_fail` outside cibuildwheel |

All of the first five are the same versions the 16.3 builder already compiles
with the same apt list. Rust-backed packages all ship cp312 (or abi3)
manylinux aarch64 wheels, so no cargo is needed: `rpds-py==0.22.3`,
`pydantic_core==2.27.2`, `cryptography==43.0.3` (abi3), `mmh3==5.1.0`,
`google-crc32c==1.7.1`; `msal==1.32.3` is pure Python. `pyiceberg` is Cython,
not Rust.

Builder step 5 (`pandas==2.2.3` with `Cython<3` + `setuptools==74.0.0`
constraints) only downloads the cp312 manylinux wheel (x86_64 and aarch64
both exist); no build happens, so the Cython constraint is inert. Step 6
then fetches `Cython==3.0.12` unconstrained (cp312 aarch64 wheel exists).

## Build commands

```bash
# 1. wheels (checkpoint)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.builder.new --build-arg DATABRICKS_RUNTIME=17.3 \
  -t lcccguy/databricks17.3-wheels:latest --push .

# 2. cluster image (no Spark)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.runtime.new --target cluster --build-arg DATABRICKS_RUNTIME=17.3 \
  -t lcccguy/databricks17.3:cluster --push .

# 3. local image (with Spark 4.0.0)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.runtime.new --target local --build-arg DATABRICKS_RUNTIME=17.3 \
  -t lcccguy/databricks17.3:latest --push .
```

## Not verified (no Docker daemon)

- An actual build on either architecture; in particular the from-source
  builds above and `python3 packaging/classic/setup.py -q sdist` under
  setuptools 74 were checked by reading, not by running.
- That the Databricks 17.3 cluster accepts the `cluster` image (JDK 17 on
  PATH is what the custom-container spec asks for).
