# Offline database bootstrap

How to build the offline tool's database from the committed fixtures instead of
from a pre-seeded binary snapshot, and how to prove that the result carries the
same reference primary keys as an online installation.

Related: [`fixtures-guide.md`](./fixtures-guide.md) for the fixture pipeline and
its PK-stability guardrail.

## Why this exists

`.exactproject` export encodes every reference-data relation as a raw integer
primary key. Import (before `formatVersion: 2`) resolved nothing: it wrote the
exported integer straight into the FK column. That is only safe while both
installations agree on what primary key N means.

They did not agree. The `release/offline-tool` branch ships a committed 53 MB
`djangoexact/db.sqlite3` that was seeded independently rather than through
`load_reference_data`, so its reference PKs drifted away from the committed
fixtures the online deployment is built from. Measured drift at the time of
writing: 83 of 162 manifest reference models differ.

Two consequences, one loud and one silent:

- `ipcc.GlobalWarmingPotential` PK ranges are fully disjoint (fixtures use 8-12,
  the shipped offline DB uses 1-5) and `Project.gw_potential` is NOT NULL, so
  every online-to-offline import fails at the first row.
- Where PKs happen to collide, the import succeeds and the project silently
  displays the wrong climate, soil type, GWP report or module type. In a GHG
  appraisal tool that is a correctness bug, and nothing surfaces it.

Building the offline database from the same fixtures as the online deployment
removes the cause. The `formatVersion: 2` natural-key encoding, added on the same
branch, is what protects files exported from offline builds already installed.

## Building a reference database

From the Django root (`djangoexact/`, the directory holding `manage.py`):

```bash
bash scripts/build_offline_db.sh /path/to/exact-offline.sqlite3
```

The script:

1. refuses to run if the output file already exists, so a stale database can
   never be silently reused,
2. exports `DB_ENGINE=django.db.backends.sqlite3` and `DB_NAME=<output>`,
3. runs `manage.py migrate --noinput`,
4. runs `manage.py load_reference_data --app=all`,
5. runs `manage.py verify_reference_parity --app=all` and fails the build if it
   exits non-zero.

`set -euo pipefail` is on, so any step failing aborts the whole run and leaves a
partial file you must delete before retrying.

Override the interpreter with `PYTHON=/path/to/python` if `../.venv/bin/python`
is not the right one.

### Measured cost

Full run on a developer laptop against a fresh sqlite file: **20m 29s**, measured
by the script's own timer, producing a 52 MB database.

Almost all of that is step 3: roughly 290 migrations plus the table rebuilds that
`simple_history` and `sqlite`'s ALTER TABLE emulation force. It is not a defect
and it cannot usefully be shortened without squashing migrations. Budget for it
in any packaging pipeline, and do not run it per build if the fixture set and
migration set have not changed.

`load_reference_data --app=all` and `verify_reference_parity --app=all` are both
fast by comparison.

## What `verify_reference_parity` proves

```bash
python manage.py verify_reference_parity --app=all         # human-readable
python manage.py verify_reference_parity --app=ipcc --json # machine-readable
```

For every model in `api/fixtures_manifest.py` it compares the identity of each
primary key in the database against the identity the committed fixture assigns
to that same primary key, and reports three categories:

| Category | Meaning | Severity |
| --- | --- | --- |
| `changed` | A pk exists on both sides but names a different row. An exported integer FK will resolve to the wrong reference row. | **Fatal**, exit code 1 |
| `missing_in_db` | A pk is in the fixtures but not in this database. Imports referencing it fail loudly. | Warning |
| `extra_in_db` | A pk is in this database but not in the fixtures. Usually local additions. | Warning |

Only `changed` sets the exit code, mirroring the dump guardrail semantics in
`fixtures-guide.md`: adding rows is always allowed, removing rows warns, and
reusing a primary key for a different row is the violation.

The identity compared is the manifest's `order_by` tuple, which the manifest
contract already requires to be a deterministic per-model identity. Where
`order_by` is `("id",)` alone (most `ipcc` entries) the `name` column is appended,
otherwise the comparison would compare a pk against itself and detect nothing.
Translation rewriting is turned off on the query so the database is read from the
same base column the fixture stores.

What it does not prove: that the *values* on a row are correct. It answers the
identity question only. Use `load_reference_data --verify` or
`dump_reference_data` for full round-trip equality.

## Handoff checklist for `release/offline-tool`

**None of the following has been performed.** This branch delivers the tooling
only. The steps below must be executed on `release/offline-tool` by whoever owns
that branch and its packaging step.

1. **Measure before changing anything.** Run
   `python manage.py verify_reference_parity --app=all` against the shipped
   `djangoexact/db.sqlite3` and record the output. The decision to stop shipping
   that file should rest on the recorded numbers, not on this document's
   assertion.
2. **Stop tracking the snapshot.** `git rm --cached djangoexact/db.sqlite3` and
   add it to `.gitignore`. Note that this stops the drift going forward but does
   not reclaim the 53 MB already in history; rewriting history to reclaim it is a
   separate decision with its own blast radius, and is not required for
   correctness.
3. **Generate the database at package time** with
   `bash scripts/build_offline_db.sh <output>`, from **the same commit** as the
   online deployment. Same commit is the whole point: it is what makes the
   reference primary keys equal by construction.
4. **Gate packaging on parity.** The packaging step must fail if
   `verify_reference_parity --app=all` exits non-zero. Building an offline
   database that has already drifted is the failure this work exists to prevent.
5. **Confirm the offline environment sets a sqlite engine.** The offline `.env`
   must set `DB_ENGINE=django.db.backends.sqlite3` and `DB_NAME` to the packaged
   file. This only works once the `settings.py` change on this branch (the
   Postgres-only `OPTIONS` block is now applied only when the resolved engine is
   postgresql) has been merged down into `release/offline-tool`. Before that
   change, any sqlite run dies with
   `TypeError: 'connect_timeout' is an invalid keyword argument for Connection()`.

## Unconfirmed

Recorded verbatim, because guessing here would be worse than saying so. Nothing
below could be established from this repository.

- `release/offline-tool:djangoexact/djangoexact/settings_offline.py` is
  byte-identical to `develop`'s `settings.py` on the database question. It does
  `from .settings import *`, strips the `minitool` and `admin_scripts` apps, pops
  the `minitool` database alias, and swaps `ROOT_URLCONF`. It says nothing about
  how the `default` database is provisioned or which engine it uses.
- **No `.env` file is committed on `release/offline-tool`.** So the actual
  `DB_ENGINE` / `DB_NAME` the offline build runs with is not visible from git.
- **No packaging script, Dockerfile or installer spec exists in the repository
  that consumes `djangoexact/db.sqlite3`.** The only Dockerfiles present
  (`deploy/Dockerfile.computation_job`, `deploy/Dockerfile.web_service`) are the
  GCP deployment images and do not reference it.

The packaging step therefore lives outside this Django root, and steps 3 to 5
above cannot be written as concrete commands until its owner describes it.
**This document is the request for that confirmation.** Whoever owns the offline
packaging should reply with: where the offline database file is produced or
copied, what sets `DB_ENGINE` and `DB_NAME` at runtime, and where in that
pipeline `build_offline_db.sh` and the `verify_reference_parity` gate should be
inserted.
