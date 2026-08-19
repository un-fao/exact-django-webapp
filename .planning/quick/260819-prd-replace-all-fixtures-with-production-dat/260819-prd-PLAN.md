---
quick_id: 260819-prd
slug: replace-all-fixtures-with-production-dat
date: 2026-08-19
status: complete
---

# Quick Task 260819-prd — Replace all fixtures with production data

## Goal

Regenerate the committed reference-data fixtures from the production database
(`fao-exact:europe-west1:fao-exact-postgres`, reached through a local Cloud SQL
Auth Proxy on `127.0.0.1:5432`), making production the source of truth.

## Approach

Reuse the existing `dump_reference_data` management command rather than writing
anything new. `api/fixtures_manifest.py` is already the single source of truth
for which models are reference data and in what dependency order, and the
command already implements the PK-stability guardrail and combined-output write.

## Tasks

1. Establish a verified connection to production through the proxy.
2. Dry-run `dump_reference_data --app all`; review PK-stability findings and
   row-count deltas before writing.
3. Dump with `--force` (user-approved) and validate the result.

## Scope

In scope: the 162 models in `api/fixtures_manifest.py`, plus the generated
`all_reference_data.json` combined fixture — 163 files.

Out of scope (not manifest-managed, deliberately untouched):
- `test_seed_data.json` — 2 test users + 2 groups, loaded by CI. Must not be
  overwritten with production data.
- `group.json` — empty (0 rows), unreferenced.
- `all_api_dependencies.json` — legacy fallback in `ipcc/import_ipcc_fixtures.sh`.
