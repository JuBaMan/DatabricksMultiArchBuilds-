# DatabricksMultiArchBuilds

Multi-architecture (linux/amd64 + linux/arm64) Docker images that emulate the
Python environment of a Databricks Runtime LTS release: the exact Ubuntu point
release, Python, pip/setuptools and the full "Installed Python libraries" table
from the runtime's release notes, installed as system packages. No Scala, no R,
no proprietary Databricks bits.

Two images per runtime, both built from the same pair of Dockerfiles:

| Image                                    | Built from                                  | Purpose                                                                                                          |
| ---------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `lcccguy/databricks<ver>-wheels:latest`  | `Dockerfile.builder.new`                    | Compiles every requirement into a wheel. Checkpoint for the ~2 h build; never run directly.                      |
| `lcccguy/databricks<ver>:cluster`        | `Dockerfile.runtime.new --target cluster`   | No Spark, no Hadoop. Carries only the JDK the runtime lists. Use as a custom container on a Databricks cluster.  |
| `lcccguy/databricks<ver>:latest`         | `Dockerfile.runtime.new --target local`     | Adds Spark, Hadoop, Delta Lake, PySpark, delta-spark and the Azure CLI for local development.                    |

## Building

```bash
# 1. wheels (checkpoint)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.builder.new --build-arg DATABRICKS_RUNTIME=16.3 \
  -t lcccguy/databricks16.3-wheels:latest --push .

# 2. cluster image (no Spark)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.runtime.new --target cluster --build-arg DATABRICKS_RUNTIME=16.3 \
  -t lcccguy/databricks16.3:cluster --push .

# 3. local image (with Spark)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.runtime.new --target local --build-arg DATABRICKS_RUNTIME=16.3 \
  -t lcccguy/databricks16.3:latest --push .
```

`DATABRICKS_RUNTIME` is the only build argument. The runtime stage pulls its
wheels from `lcccguy/databricks${DATABRICKS_RUNTIME}-wheels:latest`.

## Runtimes on `main`

| Runtime  | Ubuntu tag            | Python | pip    | Cluster JDK                      | Spark | Hadoop | Delta | Spark JDK |
| -------- | --------------------- | ------ | ------ | -------------------------------- | ----- | ------ | ----- | --------- |
| 16.3     | `noble-20241015`      | 3.12   | 24.2   | Zulu 8.72.0.17 (8.0.382)         | 3.5.2 | 3.3.6  | 3.3.0 | 17        |
| 15.4 LTS | `jammy-20240808`      | 3.11   | 23.2.1 | Zulu 8.78.0.19 (8.0.412)         | 3.5.0 | 3.3.6  | 3.2.0 | 8         |

Other LTS releases are developed on `lts/<ver>` branches, each with its own
`notes/dbr-<ver>.md` describing the sources of every pin.

## Adding a runtime

1. `requirements/dbs-<ver>.txt`: the "Installed Python libraries" table of the
   runtime's release notes as `name==version`, dropping entries that are Ubuntu
   packages rather than PyPI projects (`unattended-upgrades`), then the
   non-Databricks extras at the bottom (`dotenv`, `python-dotenv`,
   `azure-identity`, `azure-keyvault`). **Never add `delta-spark` here**: it
   depends on `pyspark` and would pull Spark into the cluster image. The local
   stage installs it with `--no-deps`.
2. `Dockerfile.builder.new`: one `FROM ubuntu:<dated tag> AS base-<ver>` line
   and one case in the step-0 block (`PYTHON_VERSION`, `PIP_VER`,
   `SETUPTOOLS_PIN`, `PANDAS_VER`).
3. `Dockerfile.runtime.new`: the same `FROM` line, one case in the cluster
   step-0 block (Python, pip, `CLUSTER_JDK_MAJOR`, `CLUSTER_ZULU_ID`,
   `CLUSTER_ZULU_ARM64_EMBEDDED`) and one case in the local step-0 block
   (`SPARK_JDK_MAJOR`, `SPARK_ZULU_ID`, `SPARK_VER`, `HADOOP_VER`,
   `HADOOP_ARM64_SUFFIX`, `DELTA_VER`, `SCALA_BIN`).
4. `python scripts/check_dockerfile.py Dockerfile.builder.new Dockerfile.runtime.new`
   runs `bash -n` over every `RUN` body and checks that the `FROM` router and
   every case block list the same runtimes. It needs no Docker daemon.

Where each value comes from:

- Ubuntu tag: the dated `ubuntu:<codename>-<date>` image whose date falls
  inside the point release named under "System environment" (for example
  24.04.2 → the first noble tag after 2025-02-20 and before 24.04.3).
- Python, Java, Delta Lake: the "System environment" block.
- pip, setuptools, pandas: their pins in "Installed Python libraries".
- Spark: "powered by Apache Spark x.y.z" at the top of the release notes.
- Hadoop: `<hadoop.version>` in `spark-parent_<scala>-<spark>.pom` on Maven
  Central. Apache publishes `-aarch64` tarballs for only some Hadoop releases;
  set `HADOOP_ARM64_SUFFIX` to `-aarch64` when one exists and leave it empty
  otherwise (the x64 tarball is pure Java apart from `lib/native`, which is
  dropped on arm64).
- Zulu ids: `https://api.azul.com/metadata/v1/zulu/packages/?java_version=<x.y.z>&os=linux&arch=x64&archive_type=tar.gz&java_package_type=jdk`.
  Older JDK 8 aarch64 tarballs live only under `cdn.azul.com/zulu-embedded`;
  `CLUSTER_ZULU_ARM64_EMBEDDED=true` switches the path.
- Cluster JDK: the custom-container spec says to match the runtime's default
  Java, so runtimes whose notes list Zulu 17 carry Java 17 in the cluster
  image and need no second JDK in the local stage.
