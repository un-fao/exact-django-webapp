#!/usr/bin/env bash
#
# Build an offline EX-ACT reference database from the committed fixtures.
#
# This exists so the offline tool stops shipping a pre-seeded db.sqlite3 whose
# reference primary keys have drifted away from the committed fixtures. A
# database built here has, by construction, the same reference PKs as any online
# installation bootstrapped from the same commit.
#
# Usage:
#   bash scripts/build_offline_db.sh /path/to/output.sqlite3
#
# Run from the Django root (the directory holding manage.py). The migrate step
# takes tens of minutes; see docs/guides/offline-db-bootstrap.md.

set -euo pipefail

OUT="${1:-}"
if [ -z "$OUT" ]; then
  echo "usage: bash scripts/build_offline_db.sh <output-sqlite-path>" >&2
  exit 2
fi

if [ ! -f manage.py ]; then
  echo "error: run this from the Django root (the directory holding manage.py)" >&2
  exit 2
fi

# A stale database must never be silently reused: that is the exact failure this
# script exists to remove. Refuse rather than append to an existing file.
if [ -e "$OUT" ]; then
  echo "error: $OUT already exists. Remove it first; this script never reuses a database." >&2
  exit 2
fi

PYTHON="${PYTHON:-../.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python"
fi

mkdir -p "$(dirname "$OUT")"

export DB_ENGINE="django.db.backends.sqlite3"
export DB_NAME="$OUT"
export DJANGO_DEBUG="${DJANGO_DEBUG:-True}"

echo "Building offline reference database at: $OUT"
echo "WARNING: the migrate step runs ~290 migrations against a fresh sqlite file"
echo "         and takes tens of minutes. Do not interrupt it."

START=$(date +%s)

echo
echo "[1/3] migrate"
"$PYTHON" manage.py migrate --noinput

echo
echo "[2/3] load_reference_data --app=all"
"$PYTHON" manage.py load_reference_data --app=all

echo
echo "[3/3] verify_reference_parity --app=all"
"$PYTHON" manage.py verify_reference_parity --app=all

ELAPSED=$(( $(date +%s) - START ))
echo
echo "Done in $((ELAPSED / 60))m $((ELAPSED % 60))s: $OUT"
