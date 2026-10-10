#!/usr/bin/env bash
# Generates the effective package set for the "elfo" image flavor from the
# LTS release-notes table and a delta file:
#   manifest  = <dbs.txt> minus the delta's "-package" lines
#   additions = the delta's "pkg==version" lines (installed after the extras)
# Package names are compared PEP 503-normalised (case and -_. insensitive).
# Removals absent from the table are skipped with a note (runtimes differ).
#
# Usage: bash gen_elfo_manifest.sh <dbs.txt> <elfo.txt> <out-manifest> <out-additions>
set -euo pipefail

if [ $# -ne 4 ]; then
    echo "usage: $0 <dbs.txt> <elfo-delta.txt> <out-manifest> <out-additions>" >&2
    exit 2
fi
DBS=$1 DELTA=$2 OUT_MANIFEST=$3 OUT_ADDITIONS=$4

[ -f "$DBS" ]   || { echo "missing dbs file: $DBS" >&2; exit 2; }
[ -f "$DELTA" ] || { echo "missing delta file: $DELTA" >&2; exit 2; }

: > "$OUT_MANIFEST"
: > "$OUT_ADDITIONS"

awk -v out_m="$OUT_MANIFEST" -v out_a="$OUT_ADDITIONS" '
function norm(s) { s = tolower(s); gsub(/[._-]+/, "-", s); return s }
FNR == NR {                                    # pass 1: the delta file
    line = $0
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
    if (line == "" || line ~ /^#/) next
    if (line ~ /^-/) {
        name = substr(line, 2)
        if (name !~ /^[A-Za-z0-9][A-Za-z0-9._-]*$/) {
            printf("invalid removal (must be -package, no version): %s\n", line) > "/dev/stderr"
            bad = 1; next
        }
        rem[norm(name)] = name
        next
    }
    if (line !~ /^[A-Za-z0-9][A-Za-z0-9._-]*==[^=[:space:]]+$/) {
        printf("invalid addition (must be package==version): %s\n", line) > "/dev/stderr"
        bad = 1; next
    }
    print line >> out_a
    nadd++
    next
}
{                                              # pass 2: the dbs table
    split($0, parts, "==")
    key = norm(parts[1])
    if (key in rem) { seen[key] = 1; nrem++; next }
    print $0 >> out_m
}
END {
    if (bad) exit 1
    for (k in rem) if (!(k in seen))
        printf("note: removal not in this runtime, skipped: %s\n", rem[k]) > "/dev/stderr"
    printf("gen_elfo_manifest: %d removed, %d additions\n", nrem, nadd) > "/dev/stderr"
}' "$DELTA" "$DBS"
