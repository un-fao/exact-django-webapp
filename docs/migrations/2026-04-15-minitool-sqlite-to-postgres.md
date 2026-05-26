# Minitool: SQLite → Postgres production cutover

**Status:** Manual. One-shot. Run only by an operator with DB credentials.
**Applies to:** Any environment (staging, prod) that still has a populated `djangoexact/minitool.db` SQLite file after the code change landed.

## Why

PR 1 of the scenario-builder-async-computation feature moves the `minitool` Django app off its dedicated SQLite DB (`djangoexact/minitool.db`) and onto the project's default Postgres instance. The code change is revertable via `git revert`; the data migration is a one-way operation and must be done deliberately, per environment, by a human.

## Preconditions

1. The new code (post-PR 1) is deployed and `manage.py migrate minitool` has been run against the default Postgres, producing empty tables.
2. The old `djangoexact/minitool.db` file still exists in the environment (verify with `ls -lh`).
3. The environment is in a maintenance window — `admin_scripts` is staff-only, so the blast radius is small, but new `ChangeRecord` writes during the cutover would be lost.
4. `pgloader` is available on the host running the migration. `brew install pgloader` on macOS; `apt-get install pgloader` on Debian/Ubuntu. Alternatively, Django `dumpdata` + `loaddata` works for databases under ~100MB — our file is 286 MB, so prefer pgloader.

## Option A — pgloader (recommended for >100MB files)

```bash
# 1. Take a snapshot of the source SQLite file (read-only cutover safety).
cp djangoexact/minitool.db /tmp/minitool-pre-cutover.db

# 2. Run pgloader with a command file that maps all 7 tables.
cat > /tmp/minitool-migrate.load <<'EOF'
LOAD DATABASE
  FROM sqlite:///tmp/minitool-pre-cutover.db
  INTO postgresql://DB_USER:DB_PASSWORD@DB_HOST:DB_PORT/DB_NAME

  WITH data only, truncate, disable triggers, reset sequences

  SET work_mem to '64MB', maintenance_work_mem to '512MB'

  CAST type datetime to timestamptz
       drop default drop not null using zero-dates-to-null,
       type date drop not null drop default using zero-dates-to-null

  INCLUDING ONLY TABLE NAMES MATCHING
    'minitool_entry',
    'minitool_statisticsmoduletotal',
    'minitool_emissionstatisticsbymodule',
    'minitool_changerecord',
    'minitool_changeaggregate',
    'minitool_emissionscenariocategory',
    'minitool_emissionscenario';
EOF

pgloader /tmp/minitool-migrate.load
```

**Expected output:** a summary table showing rows copied per table, zero errors.

## Option B — Django dumpdata/loaddata (safe for small datasets)

```bash
# 1. Dump from the SQLite alias (still accessible via Django if you temporarily
#    re-add the DATABASES["minitool"] block and the router).
python manage.py dumpdata minitool \
  --database=minitool \
  --natural-primary --natural-foreign \
  --indent 2 \
  -o /tmp/minitool-dump.json

# 2. Deploy the PR 1 code change (removes the alias).

# 3. Load into default Postgres.
python manage.py loaddata /tmp/minitool-dump.json --database=default
```

**Warning:** For a 286 MB SQLite file, the JSON dump can exceed 1 GB and `loaddata` can take >30 minutes. Option A is strongly preferred at this scale.

## Verification

Run these queries against the target Postgres and compare row counts against the source SQLite:

```bash
# Source counts
sqlite3 /tmp/minitool-pre-cutover.db "
SELECT 'entry', COUNT(*) FROM minitool_entry UNION ALL
SELECT 'stat_total', COUNT(*) FROM minitool_statisticsmoduletotal UNION ALL
SELECT 'emission_stat', COUNT(*) FROM minitool_emissionstatisticsbymodule UNION ALL
SELECT 'changerecord', COUNT(*) FROM minitool_changerecord UNION ALL
SELECT 'change_agg', COUNT(*) FROM minitool_changeaggregate UNION ALL
SELECT 'category', COUNT(*) FROM minitool_emissionscenariocategory UNION ALL
SELECT 'scenario', COUNT(*) FROM minitool_emissionscenario;
"

# Destination counts
python manage.py dbshell --database=default -- -c "
SELECT 'entry', COUNT(*) FROM minitool_entry UNION ALL
SELECT 'stat_total', COUNT(*) FROM minitool_statisticsmoduletotal UNION ALL
SELECT 'emission_stat', COUNT(*) FROM minitool_emissionstatisticsbymodule UNION ALL
SELECT 'changerecord', COUNT(*) FROM minitool_changerecord UNION ALL
SELECT 'change_agg', COUNT(*) FROM minitool_changeaggregate UNION ALL
SELECT 'category', COUNT(*) FROM minitool_emissionscenariocategory UNION ALL
SELECT 'scenario', COUNT(*) FROM minitool_emissionscenario;
"
```

Every row count must match. If any differ, **rollback** (see below) and investigate.

## Rollback

Rollback is the `git revert` of the PR 1 commits plus restoring `minitool.db` from `/tmp/minitool-pre-cutover.db`. Because PR 1's code change is self-contained and PR 2 does not depend on any data being in the new Postgres tables, rollback is low-risk for the first week after cutover.

After a successful, verified cutover, delete the snapshot:

```bash
rm /tmp/minitool-pre-cutover.db /tmp/minitool-migrate.load /tmp/minitool-dump.json
```
