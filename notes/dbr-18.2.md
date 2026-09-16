# Databricks Runtime 18.2

Release notes: https://docs.databricks.com/aws/en/release-notes/runtime/18.2

Not an LTS at the time of writing (18.x LTS not yet declared); added on the
same rules as the LTS runtimes. First Spark 4.1 / JDK 21 runtime in this repo.
Everything below was checked without a Docker daemon: HTTP HEAD requests,
Maven POM reads, PyPI JSON, and `/etc/os-release` of the candidate base tags.

## Values

| Variable                      | Value                          | Source                                                                                     |
| ----------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------ |
| Base image                    | `ubuntu:noble-20260210.1`      | "Ubuntu 24.04.4 LTS"; first noble tag whose `/etc/os-release` says `24.04.4` (`noble-20260113` is still 24.04.3) |
| `PYTHON_VERSION`              | `3.12`                         | "Python: 3.12.3" (noble's native `python3.12` is 3.12.3)                                   |
| `PIP_VER`                     | `25.0.1`                       | `pip` pin in "Installed Python libraries"                                                  |
| `SETUPTOOLS_PIN`              | `78.1.1`                       | `setuptools` pin                                                                           |
| `PANDAS_VER`                  | `2.2.3`                        | `pandas` pin (cp312 manylinux wheels exist for x86_64 and aarch64: downloaded, not compiled) |
| `CLUSTER_JDK_MAJOR`           | `21`                           | "Java: Zulu21.42+19-CA" (JDK 21.0.7); custom-container spec says match the runtime's Java  |
| `CLUSTER_ZULU_ID`             | `zulu21.42.19-ca-jdk21.0.7`    | Azul CDN tarball id for Zulu 21.42.19 / JDK 21.0.7                                         |
| `CLUSTER_ZULU_ARM64_EMBEDDED` | `false`                        | JDK 21 aarch64 lives under `cdn.azul.com/zulu/bin` (HEAD 200)                              |
| `SPARK_JDK_MAJOR`             | `21`                           | runtime default Java is 21; `/opt/java21` already exists from the cluster stage, so nothing is downloaded |
| `SPARK_ZULU_ID`               | `zulu21.42.19-ca-jdk21.0.7`    | same id (only used if the cluster JDK were missing)                                        |
| `SPARK_VER`                   | `4.1.0`                        | "includes Apache Spark 4.1.0"                                                              |
| `HADOOP_VER`                  | `3.4.2`                        | `<hadoop.version>3.4.2` in `spark-parent_2.13-4.1.0.pom` on Maven Central (the notes' Java table also lists `hadoop-client-runtime 3.4.2`) |
| `HADOOP_ARM64_SUFFIX`         | (empty)                        | `downloads.apache.org/hadoop/common/hadoop-3.4.2/` has no `-aarch64` tarball (HEAD 404)    |
| `DELTA_VER`                   | `4.2.0`                        | "Delta Lake: 4.2.0"                                                                        |
| `SCALA_BIN`                   | `2.13`                         | "Scala: 2.13.16"; Spark 4.x is Scala 2.13 only                                             |

Other pins from the table that the Dockerfiles rely on: numpy 2.1.3,
pyarrow 21.0.0, Cython 3.1.5, grpcio 1.67.0, protobuf 5.29.4, virtualenv
20.29.3, scikit-learn 1.6.1, azure-identity 1.20.0, wheel 0.45.1.

## Requirements files

`requirements/dbs-18.2.txt`: the "Installed Python libraries" table as
`name==version` (264 pins) minus `unattended-upgrades` (an Ubuntu package),
installed with `--no-deps`. Every pin was checked against PyPI JSON; 8 are
sdist-only for cp312/aarch64 and compile in the wheels stage (dbus-python,
lazr.uri, psutil 5.9.0, psycopg2, PyGObject, pyiceberg, ssh-import-id,
wadllib) — the same set of build-system cases the older runtimes already
handle.

`requirements/extras-18.2.txt`: `dotenv==0.9.9`, `azure-keyvault==4.2.0`
only. Unlike older runtimes, 18.2's own table already ships
`python-dotenv==1.2.1` and `azure-identity==1.20.0`, so neither may be
re-pinned in the extras (a `python-dotenv==1.1.0` extra would conflict with
the constraint). Dry-run verified with pip 25.0.1 on `python:3.12-slim`:
every resolved version lands exactly on a table pin, plus the
`azure-keyvault-{certificates,keys,secrets}` sub-packages the meta-package
pulls in.

## Verification (static checks and HTTP HEAD only; no Docker daemon)

| Check                                                                                     | Result |
| ----------------------------------------------------------------------------------------- | ------ |
| `zulu21.42.19-ca-jdk21.0.7-linux_x64.tar.gz` / `-linux_aarch64.tar.gz` on cdn.azul.com    | 200 / 200 |
| `spark-4.1.0-bin-without-hadoop.tgz` + `.sha512` on archive.apache.org                    | 200 / 200 |
| `hadoop-3.4.2.tar.gz` + `.sha512` on downloads.apache.org                                 | 200 / 200 |
| `hadoop-3.4.2-aarch64.tar.gz`                                                             | 404 (expected; suffix left empty) |
| `delta-spark_2.13-4.2.0.jar`, `delta-storage-4.2.0.jar` on Maven Central                  | 200 / 200 |
| `delta-spark==4.2.0` on PyPI                                                              | 200; `py3-none-any` wheel; requires `pyspark>=4.0.1,<=4.1.1` (satisfied by 4.1.0, installed `--no-deps` anyway) |
| `spark-parent_2.13-4.1.0.pom`                                                             | `java.version=17`, `scala.binary.version=2.13`, `hadoop.version=3.4.2` |
| Every `name==version` in `requirements/dbs-18.2.txt` (264 pins)                           | exists on PyPI |
| Extras dry-run under `-c dbs-18.2.txt` (pip 25.0.1, python:3.12-slim)                     | resolves; no pin moved |
