#!/usr/bin/env python3
"""Static checks for the Dockerfiles in this repo (no Docker daemon needed).

  python scripts/check_dockerfile.py Dockerfile.builder.new Dockerfile.runtime.new

For every RUN instruction the shell body is extracted (line continuations
joined, '#' comment lines inside the body dropped the way BuildKit does,
leading `--mount=…` flags stripped) and handed to `bash -n`.  For every
`case "${DATABRICKS_RUNTIME}"` block the set of runtime labels is printed so
the builder / cluster / local blocks and the FROM router can be compared at a
glance, and every runtime in the router must have both requirement files
(`requirements/dbs-<ver>.txt` and `requirements/extras-<ver>.txt`).  Exit
status is non-zero on any syntax error, CRLF line ending, router/case
mismatch, or missing requirement file.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASH_CANDIDATES = [
    os.environ.get("BASH"),
    r"C:\Program Files\Git\usr\bin\bash.exe",
    r"C:\Program Files\Git\bin\bash.exe",
    "/usr/bin/bash",
    "/bin/bash",
]


def find_bash():
    for cand in BASH_CANDIDATES:
        if cand and os.path.isfile(cand):
            return cand
    found = shutil.which("bash")
    if found and "System32" not in found:  # avoid the WSL launcher on Windows
        return found
    sys.exit("bash not found; set BASH=<path to bash>")


def instructions(text):
    """Yield (instruction, argument) pairs with continuation lines joined."""
    buf = []
    for line in text.splitlines():
        stripped = line.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if buf and stripped.startswith("#"):
            continue  # BuildKit drops comment lines inside a continuation
        buf.append(line)
        if not stripped.endswith("\\"):
            joined = "\n".join(buf)
            buf = []
            m = re.match(r"\s*([A-Za-z]+)\s+(.*)", joined, re.S)
            if m:
                yield m.group(1).upper(), m.group(2)


def main(paths):
    bash = find_bash()
    ok = True
    for path in paths:
        text = open(path, encoding="utf-8", newline="").read()
        if "\r" in text:
            print(f"{path}: contains CRLF line endings; continuations will break")
            ok = False
        runs = 0
        routers = []
        cases = []
        for ins, arg in instructions(text):
            if ins == "FROM":
                m = re.search(r"AS base-([0-9]+\.[0-9]+)", arg)
                if m:
                    routers.append(m.group(1))
            if ins == "RUN":
                runs += 1
                # BuildKit removes the backslash-newline pair outright, so a
                # continued command becomes one physical line.  RUN flags
                # (--mount=…) precede the shell body and are not shell.
                body = arg.replace("\\\n", " ")
                body = re.sub(r"^(?:--\S+\s+)+", "", body)
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".sh", delete=False, encoding="utf-8", newline="\n"
                ) as f:
                    f.write(body)
                    tmp = f.name
                r = subprocess.run([bash, "-n", tmp], capture_output=True, text=True)
                os.unlink(tmp)
                if r.returncode != 0:
                    ok = False
                    print(f"{path}: RUN #{runs} fails bash -n:\n{r.stderr}\n--- body ---\n{body}\n")
                if 'case "${DATABRICKS_RUNTIME}"' in body:
                    cases.append(re.findall(r"(?:^|\s)([0-9]+\.[0-9]+)\)\s", body))
                    # Every case must write the same KEY= set to /etc/dbr.env:
                    # a key missing from one runtime only fails later under
                    # `set -u`, deep inside a build.
                    keysets = {}
                    for ver, blk in re.findall(
                        r"(?:^|\s)([0-9]+\.[0-9]+)\)\s*printf(.*?)(?=/etc/dbr\.env)", body, re.S
                    ):
                        keysets[ver] = set(re.findall(r"'([A-Z_0-9]+)=", blk))
                    ref = next(iter(keysets.values()), set())
                    for ver, keys in keysets.items():
                        if keys != ref:
                            ok = False
                            print(f"{path}: case {ver} writes keys {sorted(keys ^ ref)} differently from the others")
        print(f"{path}: {runs} RUN instructions checked with `{os.path.basename(bash)} -n`")
        print(f"  FROM router runtimes : {routers}")
        for i, c in enumerate(cases, 1):
            print(f"  case block {i} runtimes : {c}")
            if sorted(c) != sorted(routers):
                ok = False
                print(f"  !! case block {i} does not match the FROM router")
        req_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "requirements")
        for ver in routers:
            for kind in ("dbs", "extras"):
                f = os.path.join(req_dir, f"{kind}-{ver}.txt")
                if not os.path.isfile(f):
                    ok = False
                    print(f"  !! missing {os.path.relpath(f)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
