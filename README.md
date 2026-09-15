# DatabricksMultiArchBuilds

Multi-architecture (linux/amd64 + linux/arm64) Docker images that emulate the
Python environment of a Databricks Runtime LTS release: the exact Ubuntu point
release, Python, pip and the full "Installed Python libraries" table from the
runtime's release notes, installed as system packages. No Scala, no R, no
proprietary Databricks bits.

Two images per runtime, both built from the same pair of Dockerfiles:

| Image                                    | Built from                                  | Purpose                                                                                                          |
| ---------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `lcccguy/databricks<ver>-wheels:latest`  | `Dockerfile.builder.new`                    | Compiles every requirement into a wheel. Checkpoint for the slow build; never run directly.                      |
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

`DATABRICKS_RUNTIME` is the only build argument. The runtime stage takes its
wheels from `lcccguy/databricks${DATABRICKS_RUNTIME}-wheels:latest`, so step 1
must be pushed (or present in the local image store) before steps 2 and 3.
Pushing needs `docker login -u lcccguy` once per machine.

Databricks Container Services does not run on AWS Graviton instances, so the
arm64 half of the cluster image only matters for pulling it on an Apple
Silicon or Graviton development machine. Building it under QEMU emulation on
an x86 PC is very slow (the wheels stage compiles pandas); use a native arm64
builder such as a GitHub Actions `ubuntu-24.04-arm` runner for that half.

## Runtimes on `main`

| Runtime  | Ubuntu tag            | Python            | pip    | Cluster JDK                      | Spark | Hadoop | Delta | Spark JDK |
| -------- | --------------------- | ----------------- | ------ | -------------------------------- | ----- | ------ | ----- | --------- |
| 16.3     | `noble-20241015`      | 3.12.3            | 24.2   | Zulu 17.54.21 (17.0.13)          | 3.5.2 | 3.3.6  | 3.3.0 | 17        |
| 15.4 LTS | `jammy-20240808`      | 3.11.11 (source)  | 23.2.1 | Zulu 8.78.0.19 (8.0.412)         | 3.5.0 | 3.3.6  | 3.2.0 | 8         |

"(source)" means jammy does not ship that patch level (its `python3.11` is
3.11.0rc1), so CPython is compiled in a throwaway stage and copied in.

Other LTS releases are developed on `lts/<ver>` branches, each with its own
`notes/dbr-<ver>.md` describing the sources of every pin.

## Adding a runtime

1. `requirements/dbs-<ver>.txt`: the "Installed Python libraries" table of the
   runtime's release notes as `name==version`, dropping entries that are
   Ubuntu packages rather than PyPI projects (`unattended-upgrades`). Nothing
   else goes in this file: it is installed with `--no-deps`, exactly as
   Databricks' own reference image does, because the table is a complete
   `pip freeze` of the runtime. A dependency the table does not list is one
   Databricks does not ship.
2. `requirements/extras-<ver>.txt`: the non-Databricks additions (`dotenv`,
   `python-dotenv`, `azure-keyvault`, `azure-identity`). These resolve their own
   dependencies but are constrained to the table, so they can never move a pin;
   a conflict fails the build. **Never add `delta-spark` here**: it depends on
   `pyspark` and would pull Spark into the cluster image. The local stage
   installs it with `--no-deps`. Check the extras against the pins before
   building: `pip install --dry-run -c requirements/dbs-<ver>.txt -r requirements/extras-<ver>.txt`
   in a `python:<x.y>-slim` container with the runtime's pip catches a conflict
   in a minute instead of a 25-minute wheels build (14.3 and 15.4 need
   `azure-identity==1.17.1` because newer releases require an `azure-core`
   those runtimes do not ship).
3. `Dockerfile.builder.new`: one `FROM ubuntu:<dated tag> AS base-<ver>` line
   and one case in the step-0 block (`PYTHON_VERSION`, `PIP_VER`,
   `SETUPTOOLS_PIN`, `PANDAS_VER`).
4. `Dockerfile.runtime.new`: the same `FROM` line, one case in the cluster
   step-0 block (`PYTHON_VERSION`, `PYTHON_SOURCE_VERSION`,
   `PYTHON_RUNTIME_LIBS`, `PIP_VER`, `CLUSTER_JDK_MAJOR`, `CLUSTER_ZULU_ID`,
   `CLUSTER_ZULU_ARM64_EMBEDDED`) and one case in the local step-0 block
   (`SPARK_JDK_MAJOR`, `SPARK_ZULU_ID`, `SPARK_VER`, `HADOOP_VER`,
   `HADOOP_ARM64_SUFFIX`, `DELTA_VER`, `SCALA_BIN`).
5. `python scripts/check_dockerfile.py Dockerfile.builder.new Dockerfile.runtime.new`
   runs `bash -n` over every `RUN` body, checks that the `FROM` router and
   every case block list the same runtimes, and that both requirement files
   exist for each. It needs no Docker daemon.
6. Build the three images for amd64 and run the smoke test below before
   pushing anything.

Where each value comes from:

- Ubuntu tag: the dated `ubuntu:<codename>-<date>` image whose date falls
  inside the point release named under "System environment" (for example
  24.04.2 → the first noble tag after 2025-02-20 and before 24.04.3).
- Python, Java, Delta Lake: the "System environment" block. If the Ubuntu
  release's `python3.x` package is not that exact patch level, set
  `PYTHON_SOURCE_VERSION` and list the shared libraries CPython links on that
  Ubuntu release in `PYTHON_RUNTIME_LIBS` (package names changed between jammy
  and noble).
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

## Size and fidelity rules

These apply to every runtime, present and future. The Dockerfiles repeat the
relevant rule next to each step.

- **The cluster image contains what Databricks' custom-container spec requires
  and nothing else.** The spec lists a JDK on `PATH`, `bash`, `iproute2`,
  `coreutils`, `procps`, `sudo`, `acl` and the `/databricks/python3`
  virtualenv; the reference image also creates the `libraries` user and sets a
  UTF-8 locale. Spark, Hadoop and Delta are injected by Databricks at cluster
  start and are never installed in the cluster image; `pip list` in it shows
  no `pyspark`. Every other apt package is a shared library some wheel links
  against and is justified in a comment next to it. No `-dev` packages, no
  compilers: everything that needs a compiler is built in the wheels image or
  in the throwaway `python-src` stage.
- **The library set is the release-notes table, byte for byte.** The table is
  installed with `--no-deps`; the extras are constrained to it. An image's
  `pip freeze` therefore differs from the table only by the extras and their
  own dependencies. Do not "fix" a package whose declared dependency is
  missing from the table: Databricks ships it that way.
- **Nothing that is only needed during a step survives it.** Wheels and
  requirement files are bind mounts, never `COPY` layers (a copied then
  deleted `/wheels` still cost 335 MB per image). Tarballs are removed in the
  `RUN` that extracts them. Every `RUN` that touches apt or pip removes its
  lists, caches and logs before it ends, because a deletion in a later layer
  does not shrink the image.
- **Downloaded artifacts are trimmed in the same `RUN`.** JDK: no `src.zip`,
  `jmods`, demos, samples or man pages. Spark: no YARN shuffle service, no
  YARN/Mesos/Kubernetes jars, R bindings, examples or sample data; PySpark is
  put on `sys.path` with a `.pth` file instead of being pip-installed, which
  is how Databricks exposes it and avoids a second copy of every jar. Hadoop:
  only `common`, `hdfs`, `hadoop-mapreduce-client-core`, the Azure connectors
  and `libhadoop.so` survive; docs, YARN, the shaded client jars, S3/Aliyun/
  Kafka connectors and test/source jars are dropped. Python from source: no
  test suite, IDLE, tkinter, static library or `-O` bytecode variants.
- **Bytecode caches are kept.** `__pycache__` is 220 to 380 MB per cluster
  image. Every Spark Python worker imports numpy and pandas on start, and
  without cached bytecode each cold process recompiles them; in a read-only or
  non-root container that happens on every start. Dropping the caches is a
  one-line change (`--no-compile` on the pip calls in step 4 of the cluster
  stage) if a smaller image matters more than start-up time.
- **The Azure CLI is the one deliberate exception.** It is 634 MB with its
  own bundled CPython and exists only in the local image for convenience;
  delete that step if you do not use `az`.

## Verifying an image

Run this in the local image; it writes a Delta table, reads it back and reports
the JVM Spark actually runs on (Spark's progress bar uses `\r`, so read the
result from the file rather than grepping stdout):

```bash
docker run --rm lcccguy/databricks16.3:latest bash -lc 'cd /tmp && python -c "
from pyspark.sql import SparkSession
s = SparkSession.builder.master(\"local[2]\").getOrCreate()
s.range(5).write.format(\"delta\").mode(\"overwrite\").save(\"/tmp/d\")
n = s.read.format(\"delta\").load(\"/tmp/d\").count()
jv = s._jvm.System.getProperty(\"java.version\")
open(\"/tmp/out.txt\",\"w\").write(f\"rows={n} spark={s.version} jvm={jv}\n\")
s.stop()
" >/dev/null 2>&1; cat /tmp/out.txt; python --version; java -version 2>&1 | head -1'
```

For the cluster image, check that the pins match the table and that nothing
Spark-related is present:

```bash
docker run --rm -i lcccguy/databricks16.3:cluster bash -c \
  'pip freeze | grep -iE "pyspark|delta|hadoop"; python --version; java -version 2>&1 | head -1; ls /databricks'
```
