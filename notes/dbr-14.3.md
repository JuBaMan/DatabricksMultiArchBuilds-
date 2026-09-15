# Databricks Runtime 14.3 LTS

Release notes: https://docs.databricks.com/aws/en/release-notes/runtime/14.3lts
Branch: `lts/14.3`. Images: `lcccguy/databricks14.3-wheels:latest`,
`lcccguy/databricks14.3:cluster`, `lcccguy/databricks14.3:latest`.

## Values

| Variable                      | Value                          | Source                                                                                                                                                                                                                                                                              |
| ----------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| base image                    | `ubuntu:jammy-20240125`        | "System environment: Ubuntu 22.04.3 LTS". Dated jammy tags in the 22.04.3 window: `20240111`, `20240125`, `20240212` (22.04.4 shipped 2024-02-22). The amd64 layer of `jammy-20240125` (config created 2024-01-25T17:54Z, layer `sha256:57c139bb…`, 29.5 MB) has `VERSION="22.04.3 LTS (Jammy Jellyfish)"` in `/usr/lib/os-release` (`/etc/os-release` symlinks to it). arm64/v8 is in the manifest list. |
| `PYTHON_VERSION`              | `3.10`                         | "Python: 3.10.12". jammy's `python3.10` is `3.10.12-1~22.04.18`, so `apt-cache show python3.10` succeeds and the deadsnakes branch in step 2 is skipped.                                                                                                                              |
| `PIP_VER`                     | `22.3.1`                       | pip pin in "Installed Python libraries"                                                                                                                                                                                                                                              |
| `SETUPTOOLS_PIN`              | `65.6.3`                       | setuptools pin                                                                                                                                                                                                                                                                      |
| `PANDAS_VER`                  | `1.5.3`                        | pandas pin (cp310 manylinux wheels exist for x86_64 and aarch64, so step 5 downloads instead of compiling)                                                                                                                                                                          |
| `CLUSTER_JDK_MAJOR`           | `8`                            | "Java: Zulu 8.74.0.17-CA-linux64" (JDK 8.0.392)                                                                                                                                                                                                                                     |
| `CLUSTER_ZULU_ID`             | `zulu8.74.0.17-ca-jdk8.0.392`  | Azul tarball id; `cdn.azul.com/zulu/bin/<id>-linux_{x64,aarch64}.tar.gz`                                                                                                                                                                                                             |
| `CLUSTER_ZULU_ARM64_EMBEDDED` | `false`                        | the aarch64 tarball is under the regular `zulu/bin` path (HTTP 200), not `zulu-embedded`                                                                                                                                                                                             |
| `SPARK_JDK_MAJOR`             | `8`                            | Spark 3.5.0 runs on the cluster stage's JDK 8; `/opt/java8` already exists, so nothing is downloaded                                                                                                                                                                                 |
| `SPARK_ZULU_ID`               | (empty)                        | unused because `SPARK_JDK_MAJOR == CLUSTER_JDK_MAJOR`                                                                                                                                                                                                                                |
| `SPARK_VER`                   | `3.5.0`                        | "powered by Apache Spark 3.5.0" at the top of the release notes                                                                                                                                                                                                                     |
| `HADOOP_VER`                  | `3.3.6`                        | `spark-parent_2.12-3.5.0.pom` says `<hadoop.version>3.3.4`; the repo uses 3.3.6 for every Spark 3.5.x runtime (15.4, 16.3). 3.3.4 has no aarch64 tarball at all (404 on both `downloads` and `archive.apache.org`) and is no longer on `downloads.apache.org`. See caveats.          |
| `HADOOP_ARM64_SUFFIX`         | `-aarch64`                     | `hadoop-3.3.6-aarch64.tar.gz` exists on `downloads.apache.org`                                                                                                                                                                                                                       |
| `DELTA_VER`                   | `3.1.0`                        | "Delta Lake: 3.1.0"                                                                                                                                                                                                                                                                 |
| `SCALA_BIN`                   | `2.12`                         | `io.delta:delta-spark_2.12:3.1.0` on Maven Central                                                                                                                                                                                                                                  |

`requirements/dbs-14.3.txt`: the "Installed Python libraries" table as
`name==version` (157 pins) minus `unattended-upgrades` (an Ubuntu package),
plus the usual extras `dotenv==0.9.9`, `python-dotenv==1.1.0`,
`azure-keyvault==4.2.0`, `azure-identity==1.17.1`. No `delta-spark`.
`azure-identity` is 1.17.1 rather than the 1.19.0 used on newer runtimes
because 1.18+ requires `azure-core>=1.31`, and every such azure-core needs
`typing-extensions>=4.6`, which conflicts with this runtime's
`typing_extensions==4.4.0`. With 1.17.1 pip 22.3.1 resolves to
`azure-core==1.29.1` under the full pin set (verified with a dry-run
install on Python 3.10, 2026-09-15).

## Verification (2026-09-15, static checks and HTTP HEAD only; no Docker daemon)

| Check                                                                                                     | Result                                                                                                  |
| --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `zulu8.74.0.17-ca-jdk8.0.392-linux_x64.tar.gz` / `-linux_aarch64.tar.gz`                                  | 200 / 200                                                                                               |
| `spark-3.5.0-bin-without-hadoop.tgz` and `.sha512`                                                         | 200 / 200; sha512 file is GNU format (`<hash>  spark-3.5.0-bin-without-hadoop.tgz`), accepted as-is   |
| `hadoop-3.3.6.tar.gz`, `hadoop-3.3.6-aarch64.tar.gz` and both `.sha512`                                    | all 200; both sha512 files are BSD format naming `hadoop-3.3.6-RC1.tar.gz`; the step's `sed` rewrites that to the downloaded filename and `sha512sum --check` parses the result (tested against dummy files: hash mismatch, no format error) |
| `delta-spark_2.12-3.1.0.jar`, `delta-storage-3.1.0.jar`, `pypi.org/pypi/delta-spark/3.1.0/json`           | 200 / 200 / 200                                                                                         |
| jammy apt packages used by both Dockerfiles                                                               | all present (`packages.ubuntu.com/jammy/<pkg>`): python3.10(-dev,-venv) 3.10.12, libodbc2, libgirepository-1.0-1, gir1.2-glib-2.0, libdbus-glib-1-2, libpq5, monit, acl, libgomp1, libgirepository1.0-dev, libdbus-glib-1-dev, patchelf, cmake, plus unixodbc-dev 2.3.9 |
| all 157 pins on PyPI                                                                                       | every `name==version` resolves                                                                          |
| `scripts/check_dockerfile.py Dockerfile.builder.new Dockerfile.runtime.new`                              | passes; 14.3 present in the FROM router and in all three case blocks; each block run with `DATABRICKS_RUNTIME=14.3` emits the values above |
| `--break-system-packages`                                                                                 | not passed anywhere (only `ARG PIP_BREAK_SYSTEM_PACKAGES=1`); pip 22.3.1 ignores unknown `PIP_*` keys and jammy has no `EXTERNALLY-MANAGED` marker anyway |
| `bootstrap.pypa.io/get-pip.py`                                                                            | `min_version = (3, 10)`, bundles pip 26.2.1; installs `pip==22.3.1` on 3.10                             |

## Packages built from source in the wheel stage

| Package                                          | Why                                              | Build dependency in the builder                              |
| ------------------------------------------------ | ------------------------------------------------ | ------------------------------------------------------------ |
| `pyodbc==4.0.32` (both arches)                   | no Linux wheels on PyPI                          | `unixodbc-dev` (added on this branch; `sql.h`, `-lodbc`)     |
| `psycopg2==2.9.3` (both arches)                  | no Linux wheels                                  | `libpq-dev` (present)                                        |
| `pyrsistent==0.18.0`, `tornado==6.1` (both)      | no cp310 wheels                                  | `build-essential` + `python3.10-dev` suffice                 |
| `psutil==5.9.0` (aarch64 only)                   | cp310 wheel for x86_64 only                      | `build-essential` suffices                                   |
| `dbus-python==1.2.18`, `PyGObject==3.42.1`       | sdist-only (same pins as 15.4)                   | `libdbus-1-dev`, `libdbus-glib-1-dev`, `libgirepository1.0-dev`, `libcairo2-dev` (present); PyGObject pulls `pycairo` as a build dep |
| `blinker==1.4`, `lazr.restfulclient==0.14.4`, `lazr.uri==1.0.6`, `ssh-import-id==5.11`, `wadllib==1.3.6` | sdist-only, pure Python | none                                                         |

`argon2-cffi-bindings==21.2.0` and `cryptography==39.0.1` ship `abi3`
manylinux wheels for both arches; nothing here needs Rust/cargo.

## Caveats

- **`unixodbc-dev` was added to the builder's step 1** (own commit). This is
  the only shared-step change; 15.4 (pyodbc 4.0.39) and 16.3 (pyodbc 5.0.1)
  download manylinux wheels and never compile pyodbc.
- `HADOOP_VER=3.3.6` deviates from the Spark 3.5.0 POM (`3.3.4`) on purpose,
  matching 15.4 which runs the same Spark; Hadoop 3.3.4 has no aarch64
  tarball.
- On Python < 3.12 `get-pip.py` also installs the latest `setuptools` and
  `wheel` when they are absent. The builder then pins
  `setuptools==65.6.3` in step 3 and the runtime replaces both with the
  `setuptools==65.6.3` / `wheel==0.38.4` wheels from the requirements in
  step 5, so the final image carries the release-note versions. If upstream
  raises the floor of `get-pip.py` above 3.10, switch to
  `https://bootstrap.pypa.io/pip/3.10/get-pip.py`.
- jammy's `libpython3.10-stdlib` ships only `distutils/__init__.py` and
  `distutils/version.py` (the full module is `python3-distutils`, not
  installed). pip 22.3.1 uses `sysconfig` on 3.10 and only imports
  `_distutils` when `sysconfig._PIP_USE_SYSCONFIG` is false; sdist builds
  run inside pip's isolated env with setuptools 65's `distutils-precedence.pth`
  shim, which serves `import distutils` from `setuptools._distutils`.
- Zulu JDK 8 has no `jshell`; the JDK step already skips that alternative.
- Not verified without a daemon: the actual compilation of the packages
  above and the ~2 h wheel build itself.

## Build

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.builder.new --build-arg DATABRICKS_RUNTIME=14.3 \
  -t lcccguy/databricks14.3-wheels:latest --push .

docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.runtime.new --target cluster --build-arg DATABRICKS_RUNTIME=14.3 \
  -t lcccguy/databricks14.3:cluster --push .

docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.runtime.new --target local --build-arg DATABRICKS_RUNTIME=14.3 \
  -t lcccguy/databricks14.3:latest --push .
```
