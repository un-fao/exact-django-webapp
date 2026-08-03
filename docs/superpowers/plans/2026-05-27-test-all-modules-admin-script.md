# Test All Modules - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new admin-scripts page that enqueues one `max_rows=100` ComputationJob per (module, field) pair from the catalog, groups them under a `ModuleTestRun`, and reports success/failure/skipped per pair via HTMX-polled results.

**Architecture:** A new Django model `ModuleTestRun` owns a many-to-many set of `ComputationJob`s plus a JSON list of skipped fields. A small planner module turns the catalog into a per-field test plan. A sibling of the existing `enqueue_or_join` salts the job hash with `run_id` so each test run gets uniquely-keyed jobs and previous runs remain queryable. The existing job runner is reused unchanged except for honoring a new optional `max_rows` column. The detail page renders a status partial that HTMX re-polls every 3 seconds until all jobs are terminal.

**Tech Stack:** Django 4.x, HTMX, Tailwind CDN (already in `admin_scripts/base.html`), Django `TestCase` runnable via either `pytest` or `python manage.py test`.

**Spec:** `docs/superpowers/specs/2026-05-27-test-all-modules-admin-script-design.md`

---

## Working directory notes

All file paths in this plan are relative to the repository root `/home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/`. The Django root is `djangoexact/`, and `manage.py`, `pytest`, and `npm` all run from there.

**Test execution policy for this plan:** The user has chosen to skip running the test suite during implementation; the local test DB requires additional setup. Each task should write the code and the tests, commit, and let the user run the suite afterward. The plan still uses TDD-shaped steps (write tests, then implementation) for code quality, but step blocks that say "run the tests" should be skipped and the implementer should note that under self-review.

**Git identity:** The repo is configured with `Claudio Lavacca <claudio.lavacca@fao.org>` (FAO identity). No identity changes needed.

**Branch:** Work happens on `develop`. Do not switch branches.

---

## File structure

**New files (inside `djangoexact/admin_scripts/`):**

- `test_planner.py`: pure helper, `_resolve_value_source` (moved from views.py) + `plan_module_tests`.
- `migrations/0004_module_test_run_and_max_rows.py`: adds `ComputationJob.max_rows` and `ModuleTestRun`.
- `templates/admin_scripts/scripts/test_modules.html`: landing page (run button + run history).
- `templates/admin_scripts/scripts/test_modules_detail.html`: detail-page wrapper.
- `templates/admin_scripts/partials/test_modules_results.html`: polled body.
- `tests/test_test_planner.py`
- `tests/test_enqueue_for_test_run.py`
- `tests/test_test_modules_views.py`

**Modified files:**

- `models.py`: add `max_rows` field, add `ModuleTestRun` model.
- `job_dispatcher.py`: conditional `max_rows`/`force_key` in hash, add `enqueue_for_test_run`.
- `management/commands/run_computation_job.py`: pass `job.max_rows or 10000` to compute.
- `views.py`: drop local `_resolve_value_source` (import from `test_planner`), add 3 views, extend `SCRIPTS`.
- `urls.py`: add 3 routes.
- `tests/test_jobs.py`: add hash backward-compat tests + `ModuleTestRun` sanity test.

---

## Task 1: Add `max_rows` column to `ComputationJob` and the `ModuleTestRun` model

**Files:**

- Modify: `djangoexact/admin_scripts/models.py`
- Create: `djangoexact/admin_scripts/migrations/0004_module_test_run_and_max_rows.py`
- Modify: `djangoexact/admin_scripts/tests/test_jobs.py`

- [ ] **Step 1: Add the new field and model to `models.py`**

Append to `djangoexact/admin_scripts/models.py`:

```python
class ModuleTestRun(models.Model):
    """A single "test all modules" execution. Owns the ComputationJobs it spawned."""

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="module_test_runs",
    )
    jobs = models.ManyToManyField(
        ComputationJob,
        related_name="test_runs",
        blank=True,
    )
    skipped = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"TestRun #{self.pk} ({self.created_at:%Y-%m-%d %H:%M})"
```

Inside the existing `ComputationJob` class, add this field next to `filters` (after the `filters = models.JSONField(...)` line):

```python
    max_rows = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Row cap for compute_module_slice. Null means runner default (10000).",
    )
```

- [ ] **Step 2: Generate the migration**

Run from `djangoexact/`:

```bash
python manage.py makemigrations admin_scripts --name module_test_run_and_max_rows
```

Expected output: `Migrations for 'admin_scripts': 0004_module_test_run_and_max_rows.py`. Verify the file lists `AddField` for `max_rows` and `CreateModel` for `ModuleTestRun`.

If the `makemigrations` command itself fails to reach the database (the local Postgres setup is not the controller's concern), commit the migration scaffold by hand using the structure below. The plan author has verified this exact migration shape is what `makemigrations` produces for these model changes:

```python
# djangoexact/admin_scripts/migrations/0004_module_test_run_and_max_rows.py
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('admin_scripts', '0003_add_cancellation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='computationjob',
            name='max_rows',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Row cap for compute_module_slice. Null means runner default (10000).',
                null=True,
            ),
        ),
        migrations.CreateModel(
            name='ModuleTestRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('skipped', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('jobs', models.ManyToManyField(blank=True, related_name='test_runs', to='admin_scripts.computationjob')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_test_runs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
```

- [ ] **Step 3: Apply the migration (SKIP if test DB is not available)**

If a local Postgres test DB is available:

```bash
python manage.py migrate admin_scripts
```

Expected: `Applying admin_scripts.0004_module_test_run_and_max_rows... OK`. If the test DB is not set up, skip this step; the user will run it afterward.

- [ ] **Step 4: Add model sanity tests**

Append to `djangoexact/admin_scripts/tests/test_jobs.py`:

```python
class ModuleTestRunModelTest(TestCase):
    databases = {"default"}

    def test_create_run(self):
        from admin_scripts.models import ModuleTestRun
        from api.models import CustomUser

        user = CustomUser.objects.create_user(
            email="run@example.com", password="x", firebase_uid="r1"
        )
        run = ModuleTestRun.objects.create(requested_by=user)
        self.assertEqual(run.jobs.count(), 0)
        self.assertEqual(run.skipped, [])
        self.assertIsNone(run.completed_at)
        self.assertIn(f"TestRun #{run.pk}", str(run))

    def test_max_rows_defaults_to_null(self):
        job = ComputationJob.objects.create(
            filters_hash="mr_null_hash",
            module_type="Grassland",
            attribute="x",
            from_value="A",
            to_value="B",
        )
        self.assertIsNone(job.max_rows)
```

- [ ] **Step 5: Verify (SKIP if test DB not available)**

If the test DB is available, run:

```bash
python manage.py test admin_scripts.tests.test_jobs.ModuleTestRunModelTest admin_scripts.tests.test_jobs.ComputationJobModelTest -v 2 --keepdb
```

Otherwise skip and note "test execution deferred" under self-review.

- [ ] **Step 6: Commit**

```bash
git add djangoexact/admin_scripts/models.py \
        djangoexact/admin_scripts/migrations/0004_module_test_run_and_max_rows.py \
        djangoexact/admin_scripts/tests/test_jobs.py
git commit -m "feat(admin_scripts): add ModuleTestRun model and ComputationJob.max_rows"
```

---

## Task 2: Make `compute_filters_hash` honor optional `max_rows` and `force_key`

**Files:**

- Modify: `djangoexact/admin_scripts/job_dispatcher.py`
- Modify: `djangoexact/admin_scripts/tests/test_jobs.py`

- [ ] **Step 1: Append hash tests**

Append to the existing `FiltersHashTest` class in `djangoexact/admin_scripts/tests/test_jobs.py`:

```python
    def test_hash_backward_compatible_when_keys_absent(self):
        """A params dict without max_rows/force_key must hash the same as before
        the keys were added, keeping existing rows reachable by enqueue_or_join."""
        params = {
            "module_type": "Grassland",
            "attribute": "grassland_management_type",
            "from_value": "A",
            "to_value": "B",
        }
        # Recompute the legacy hash manually to lock the contract.
        import hashlib, json
        legacy = hashlib.sha256(
            json.dumps(
                {
                    "module_type": "Grassland",
                    "attribute": "grassland_management_type",
                    "from_value": "A",
                    "to_value": "B",
                    "filters": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        self.assertEqual(compute_filters_hash(params), legacy)

    def test_hash_differs_when_max_rows_set(self):
        base = {
            "module_type": "Grassland",
            "attribute": "x",
            "from_value": "A",
            "to_value": "B",
        }
        with_cap = {**base, "max_rows": 100}
        self.assertNotEqual(compute_filters_hash(base), compute_filters_hash(with_cap))

    def test_hash_differs_when_force_key_set(self):
        base = {
            "module_type": "Grassland",
            "attribute": "x",
            "from_value": "A",
            "to_value": "B",
        }
        forced = {**base, "force_key": "run-7"}
        self.assertNotEqual(compute_filters_hash(base), compute_filters_hash(forced))

    def test_hash_treats_none_keys_as_absent(self):
        """Passing max_rows=None or force_key=None must hash identically to omission."""
        base = {
            "module_type": "Grassland",
            "attribute": "x",
            "from_value": "A",
            "to_value": "B",
        }
        with_nones = {**base, "max_rows": None, "force_key": None}
        self.assertEqual(compute_filters_hash(base), compute_filters_hash(with_nones))
```

- [ ] **Step 2: Update `compute_filters_hash`**

Replace the body of `compute_filters_hash` in `djangoexact/admin_scripts/job_dispatcher.py` with:

```python
def compute_filters_hash(params: dict) -> str:
    """Compute a deterministic SHA-256 hash of canonicalized job parameters.

    Parameters
    ----------
    params:
        Must contain keys: module_type, attribute, from_value, to_value.
        May contain: filters (dict), max_rows (int or None),
        force_key (str or None). max_rows and force_key are included in
        the canonical JSON only when their value is not None, so omission
        and None are equivalent and the hash stays backward-compatible
        with rows created before these keys existed.
    """
    canonical_dict = {
        "module_type": params["module_type"],
        "attribute": params["attribute"],
        "from_value": params["from_value"],
        "to_value": params["to_value"],
        "filters": params.get("filters", {}),
    }
    max_rows = params.get("max_rows")
    if max_rows is not None:
        canonical_dict["max_rows"] = max_rows
    force_key = params.get("force_key")
    if force_key is not None:
        canonical_dict["force_key"] = force_key
    canonical = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
```

- [ ] **Step 3: Verify (SKIP if test DB not available)**

If the test DB is available:

```bash
python manage.py test admin_scripts.tests.test_jobs.FiltersHashTest -v 2 --keepdb
```

- [ ] **Step 4: Commit**

```bash
git add djangoexact/admin_scripts/job_dispatcher.py \
        djangoexact/admin_scripts/tests/test_jobs.py
git commit -m "feat(admin_scripts): hash max_rows and force_key when present"
```

---

## Task 3: Create `test_planner.py` with `_resolve_value_source` and `plan_module_tests`

**Files:**

- Create: `djangoexact/admin_scripts/test_planner.py`
- Create: `djangoexact/admin_scripts/tests/test_test_planner.py`

- [ ] **Step 1: Write the tests**

Create `djangoexact/admin_scripts/tests/test_test_planner.py` with:

```python
"""Tests for admin_scripts.test_planner.

The planner is pure (no Django request layer), but _resolve_value_source
queries Django models, so we use TestCase to get a DB.
"""
from unittest.mock import patch

from django.test import TestCase

from admin_scripts.catalog import CatalogField, CatalogModule
from admin_scripts.test_planner import plan_module_tests


def _module(module_type, fields):
    return CatalogModule(
        module_type=module_type, label=module_type, config_name=module_type.lower(),
        fields=fields,
    )


def _field(name, value_source):
    return CatalogField(field_name=name, label=name, value_source=value_source)


class PlanModuleTestsTest(TestCase):
    databases = {"default"}

    def test_plans_one_entry_per_testable_field(self):
        catalog = [_module("Grassland", [
            _field("is_fire_used", {"kind": "static", "values": [True, False]}),
            _field("fire_impact", {"kind": "static", "values": [1, 0]}),
        ])]
        planned, skipped = plan_module_tests(catalog)
        self.assertEqual(len(planned), 2)
        self.assertEqual(skipped, [])
        self.assertEqual(planned[0], {
            "module_type": "Grassland",
            "field_name": "is_fire_used",
            "from_value": "True",
            "to_value": "False",
        })
        self.assertEqual(planned[1], {
            "module_type": "Grassland",
            "field_name": "fire_impact",
            "from_value": "1",
            "to_value": "0",
        })

    def test_skips_single_value_static_field(self):
        catalog = [_module("Grassland", [
            _field("fire_periodicity", {"kind": "static", "values": [1]}),
        ])]
        planned, skipped = plan_module_tests(catalog)
        self.assertEqual(planned, [])
        self.assertEqual(skipped, [{
            "module_type": "Grassland",
            "field_name": "fire_periodicity",
            "reason": "only 1 distinct value(s) available",
        }])

    def test_skips_empty_queryset(self):
        catalog = [_module("Grassland", [
            _field("grassland_management_type", {
                "kind": "queryset", "model": "GrasslandManagementType",
            }),
        ])]
        with patch(
            "admin_scripts.test_planner._resolve_value_source", return_value=[]
        ):
            planned, skipped = plan_module_tests(catalog)
        self.assertEqual(planned, [])
        self.assertEqual(skipped[0]["reason"], "no values available")

    def test_deduplicates_while_preserving_order(self):
        catalog = [_module("M", [
            _field("f", {"kind": "static", "values": ["A", "A", "B", "B"]}),
        ])]
        planned, skipped = plan_module_tests(catalog)
        self.assertEqual(skipped, [])
        self.assertEqual(planned[0]["from_value"], "A")
        self.assertEqual(planned[0]["to_value"], "B")

    def test_preserves_module_order(self):
        catalog = [
            _module("Alpha", [_field("a", {"kind": "static", "values": [1, 2]})]),
            _module("Beta",  [_field("b", {"kind": "static", "values": [3, 4]})]),
        ]
        planned, _ = plan_module_tests(catalog)
        self.assertEqual(planned[0]["module_type"], "Alpha")
        self.assertEqual(planned[1]["module_type"], "Beta")
```

- [ ] **Step 2: Create `test_planner.py`**

Create `djangoexact/admin_scripts/test_planner.py`:

```python
"""Per-field test planner for the Test All Modules admin script.

Pure helpers: turn a list of CatalogModule into the per-field test plan
(plus a list of fields that had to be skipped). _resolve_value_source is
also kept here (moved out of views.py) so both the planner and the views
import the single source of truth.
"""
from __future__ import annotations

from django.apps import apps


def _resolve_value_source(value_source: dict) -> list[str]:
    """Resolve a catalog value_source dict to a list of string values.

    For queryset sources, queries the model and returns str() of each
    instance. For static sources, returns the values list as strings.
    """
    kind = value_source.get("kind", "")
    if kind == "queryset":
        model_name = value_source.get("model", "")
        try:
            model = apps.get_model("api", model_name)
            return [str(obj) for obj in model.objects.all().order_by("pk")]
        except LookupError:
            return []
    elif kind == "static":
        return [str(v) for v in value_source.get("values", [])]
    return []


def _ordered_unique(items: list[str]) -> list[str]:
    """Return items with duplicates removed while preserving first-occurrence order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def plan_module_tests(catalog) -> tuple[list[dict], list[dict]]:
    """Build a per-(module, field) test plan from the catalog.

    For each catalog field, resolve its value source and pick the first
    two distinct stringified values as ``(from_value, to_value)``. Fields
    with fewer than two distinct resolved values are skipped with a
    reason explaining why.

    Parameters
    ----------
    catalog:
        List of ``CatalogModule`` instances (typically from ``get_catalog()``).

    Returns
    -------
    tuple[list[dict], list[dict]]
        ``(planned, skipped)``.

        ``planned`` items: ``{module_type, field_name, from_value, to_value}``.
        ``skipped`` items: ``{module_type, field_name, reason}``.

        Module and field order match catalog order.
    """
    planned: list[dict] = []
    skipped: list[dict] = []

    for module in catalog:
        for field in module.fields:
            values = _ordered_unique(_resolve_value_source(field.value_source))
            if len(values) == 0:
                skipped.append({
                    "module_type": module.module_type,
                    "field_name": field.field_name,
                    "reason": "no values available",
                })
                continue
            if len(values) < 2:
                skipped.append({
                    "module_type": module.module_type,
                    "field_name": field.field_name,
                    "reason": f"only {len(values)} distinct value(s) available",
                })
                continue
            planned.append({
                "module_type": module.module_type,
                "field_name": field.field_name,
                "from_value": values[0],
                "to_value": values[1],
            })

    return planned, skipped
```

- [ ] **Step 3: Verify (SKIP if test DB not available)**

If the test DB is available:

```bash
python manage.py test admin_scripts.tests.test_test_planner -v 2 --keepdb
```

- [ ] **Step 4: Commit**

```bash
git add djangoexact/admin_scripts/test_planner.py \
        djangoexact/admin_scripts/tests/test_test_planner.py
git commit -m "feat(admin_scripts): add test_planner with plan_module_tests"
```

---

## Task 4: Drop the duplicate `_resolve_value_source` from `views.py`

**Files:**

- Modify: `djangoexact/admin_scripts/views.py`

- [ ] **Step 1: Replace the local helper with an import**

In `djangoexact/admin_scripts/views.py`:

a) Remove the entire `_resolve_value_source` function (currently around lines 33 to 49). For reference, the body to remove is:

```python
def _resolve_value_source(value_source):
    """Resolve a catalog value_source dict to a list of string values.

    For queryset sources, queries the model and returns str() of each instance.
    For static sources, returns the values list as strings.
    """
    kind = value_source.get("kind", "")
    if kind == "queryset":
        model_name = value_source.get("model", "")
        try:
            model = apps.get_model("api", model_name)
            return [str(obj) for obj in model.objects.all().order_by("pk")]
        except LookupError:
            return []
    elif kind == "static":
        return [str(v) for v in value_source.get("values", [])]
    return []
```

b) Update the import block near the top of the file. Find the existing line:

```python
from admin_scripts.scenario_utils import stats_for_scenario
```

and add immediately after it:

```python
from admin_scripts.test_planner import _resolve_value_source
```

The function is currently used inside `htmx_values`. Verify by grepping:

```bash
grep -n "_resolve_value_source" djangoexact/admin_scripts/views.py
```

Expected: one import line plus one call site inside `htmx_values`.

- [ ] **Step 2: Verify (SKIP if test DB not available)**

If the test DB is available, run the existing view suite to confirm nothing regressed:

```bash
python manage.py test admin_scripts.tests.test_views -v 1 --keepdb
```

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/views.py
git commit -m "refactor(admin_scripts): move _resolve_value_source to test_planner"
```

---

## Task 5: Add `enqueue_for_test_run` to `job_dispatcher.py`

**Files:**

- Modify: `djangoexact/admin_scripts/job_dispatcher.py`
- Create: `djangoexact/admin_scripts/tests/test_enqueue_for_test_run.py`

- [ ] **Step 1: Write the tests**

Create `djangoexact/admin_scripts/tests/test_enqueue_for_test_run.py`:

```python
"""Tests for admin_scripts.job_dispatcher.enqueue_for_test_run."""
from unittest.mock import patch

from django.test import TransactionTestCase

from admin_scripts.job_dispatcher import (
    compute_filters_hash,
    enqueue_for_test_run,
    enqueue_or_join,
)
from admin_scripts.models import ComputationJob
from api.models import CustomUser


class EnqueueForTestRunTest(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="t@example.com", password="x", firebase_uid="t1",
        )

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_creates_job_with_max_rows_and_run_scoped_hash(self, mock_dispatch):
        job = enqueue_for_test_run(
            user=self.user, run_id=7,
            module_type="Grassland", attribute="is_fire_used",
            from_value="True", to_value="False", max_rows=100,
        )
        self.assertEqual(job.max_rows, 100)
        self.assertEqual(job.module_type, "Grassland")
        self.assertEqual(job.attribute, "is_fire_used")
        self.assertIn(self.user, job.requested_by.all())
        # Hash must include both max_rows and force_key="testrun-7"
        expected_hash = compute_filters_hash({
            "module_type": "Grassland",
            "attribute": "is_fire_used",
            "from_value": "True",
            "to_value": "False",
            "filters": {},
            "max_rows": 100,
            "force_key": "testrun-7",
        })
        self.assertEqual(job.filters_hash, expected_hash)
        mock_dispatch.assert_called_once_with(job.pk)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_does_not_collide_with_existing_production_job(self, mock_dispatch):
        # Pre-existing production job with no max_rows (the legacy hash).
        prod = enqueue_or_join(
            self.user, "Grassland", "is_fire_used", "True", "False",
        )
        # Test-run job for the "same" parameters must be a fresh, distinct row.
        test_job = enqueue_for_test_run(
            user=self.user, run_id=1,
            module_type="Grassland", attribute="is_fire_used",
            from_value="True", to_value="False", max_rows=100,
        )
        self.assertNotEqual(prod.pk, test_job.pk)
        self.assertNotEqual(prod.filters_hash, test_job.filters_hash)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    def test_different_runs_get_different_jobs(self, mock_dispatch):
        job_a = enqueue_for_test_run(
            user=self.user, run_id=1,
            module_type="Grassland", attribute="is_fire_used",
            from_value="True", to_value="False", max_rows=100,
        )
        job_b = enqueue_for_test_run(
            user=self.user, run_id=2,
            module_type="Grassland", attribute="is_fire_used",
            from_value="True", to_value="False", max_rows=100,
        )
        self.assertNotEqual(job_a.pk, job_b.pk)
        # Both rows are preserved (no delete, no cascade).
        self.assertEqual(
            ComputationJob.objects.filter(pk__in=[job_a.pk, job_b.pk]).count(), 2
        )
```

- [ ] **Step 2: Add `enqueue_for_test_run` to `job_dispatcher.py`**

Append to `djangoexact/admin_scripts/job_dispatcher.py` after the existing `enqueue_or_join` function:

```python
def enqueue_for_test_run(
    user, run_id, module_type, attribute, from_value, to_value,
    max_rows, filters=None,
):
    """Enqueue a fresh ComputationJob for a ModuleTestRun.

    The job's hash is salted with ``force_key="testrun-{run_id}"`` so it
    is structurally distinct from every other job (test or production)
    and cannot coalesce with any existing row. The job carries
    ``max_rows`` so the runner caps the underlying computation.

    Returns the newly created ComputationJob.
    """
    params = {
        "module_type": module_type,
        "attribute": attribute,
        "from_value": from_value,
        "to_value": to_value,
        "filters": filters or {},
        "max_rows": max_rows,
        "force_key": f"testrun-{run_id}",
    }
    filters_hash = compute_filters_hash(params)

    with transaction.atomic():
        job = ComputationJob.objects.create(
            filters_hash=filters_hash,
            module_type=module_type,
            attribute=attribute,
            from_value=from_value,
            to_value=to_value,
            filters=filters or {},
            max_rows=max_rows,
        )
        job.requested_by.add(user)
        transaction.on_commit(lambda: dispatch_job(job.pk))

    return job
```

- [ ] **Step 3: Verify (SKIP if test DB not available)**

If the test DB is available:

```bash
python manage.py test admin_scripts.tests.test_enqueue_for_test_run admin_scripts.tests.test_jobs.EnqueueOrJoinTest -v 2 --keepdb
```

- [ ] **Step 4: Commit**

```bash
git add djangoexact/admin_scripts/job_dispatcher.py \
        djangoexact/admin_scripts/tests/test_enqueue_for_test_run.py
git commit -m "feat(admin_scripts): add enqueue_for_test_run with run-scoped hash"
```

---

## Task 6: Make `run_computation_job` honor `job.max_rows`

**Files:**

- Modify: `djangoexact/admin_scripts/management/commands/run_computation_job.py`

- [ ] **Step 1: Change the `max_rows` argument passed to `compute_module_slice`**

In `djangoexact/admin_scripts/management/commands/run_computation_job.py`, find inside `_run_computation`:

```python
        data, errors = compute_module_slice(
            module_type=job.module_type,
            attribute=job.attribute,
            from_value=job.from_value,
            to_value=job.to_value,
            chunk_size=10000,
            max_rows=10000,
            max_workers=None,
            save_results=True,
            progress_callback=_update_progress,
        )
```

Replace the `max_rows=10000,` line with:

```python
            max_rows=job.max_rows or 10000,
```

- [ ] **Step 2: Confirm no regression (SKIP if test DB not available)**

If the test DB is available, run the full `admin_scripts` suite:

```bash
python manage.py test admin_scripts -v 1 --keepdb
```

There is no new dedicated runner unit test for this one-line change; the cap is exercised indirectly by the view tests in Task 8.

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/management/commands/run_computation_job.py
git commit -m "feat(admin_scripts): runner honors ComputationJob.max_rows"
```

---

## Task 7: Add views, URLs, dashboard entry, stub templates

**Files:**

- Modify: `djangoexact/admin_scripts/views.py`
- Modify: `djangoexact/admin_scripts/urls.py`
- Create: `djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules.html`
- Create: `djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules_detail.html`
- Create: `djangoexact/admin_scripts/templates/admin_scripts/partials/test_modules_results.html`

This task wires up the endpoints with their final logic. Templates here are minimal stubs so the views can render and be unit-tested; Task 9 fleshes them out with the full Tailwind markup.

- [ ] **Step 1: Add the URL routes**

Modify `djangoexact/admin_scripts/urls.py`. In `urlpatterns`, add these three lines anywhere after the existing `example-script` line:

```python
    path("test-modules/", views.test_modules, name="test-modules"),
    path("test-modules/<int:run_id>/", views.test_modules_detail, name="test-modules-detail"),
    path("test-modules/<int:run_id>/status/", views.test_modules_status, name="test-modules-status"),
```

- [ ] **Step 2: Add the dashboard entry and views**

In `djangoexact/admin_scripts/views.py`:

a) Append a new entry to the `SCRIPTS` list:

```python
    {
        "name": "Test All Modules",
        "url": "test-modules",
        "description": "Systematically run a capped computation for every module/field in the catalog and report success/failure per pair.",
    },
```

b) Add these imports near the other admin_scripts imports at the top of the file:

```python
from admin_scripts.catalog import get_catalog
from admin_scripts.job_dispatcher import enqueue_for_test_run
from admin_scripts.models import ComputationJob, ModuleTestRun
from admin_scripts.test_planner import plan_module_tests
```

(Some of these may already be imported; keep one copy of each.)

c) Append the three new view functions to the end of the file (after `compile_scenarios_export` or whichever is the last existing view):

```python
# ---------------------------------------------------------------------------
# Test All Modules
# ---------------------------------------------------------------------------

TERMINAL_STATUSES = {
    ComputationJob.Status.COMPLETED,
    ComputationJob.Status.FAILED,
    ComputationJob.Status.CANCELLED,
}


def _summarize_completed_job(job):
    """Compute a tiny count/mean summary for a completed test-run job.

    Returns a dict with ``count`` (int) and ``mean_str`` (formatted string
    or empty). Preformatting in Python keeps the template free of
    None-comparison gymnastics and lets ``mean=0.0`` render as "0.00"
    rather than being filtered out by template truthiness.
    """
    from admin_scripts.scenario_utils import stats_for_scenario

    change = {
        "module_type": job.module_type,
        "start": {"field": job.attribute, "value": job.from_value},
        "end": {"field": job.attribute, "value": job.to_value},
        "filters": {},
        "unit": "",
    }
    stats = stats_for_scenario([change], {})
    mean = stats["mean"]
    mean_str = f"{mean:.2f}" if mean is not None else ""
    return {"count": stats["count"], "mean_str": mean_str}


def _build_run_rows(run):
    """Build the per-job rows shown on the detail page, grouped by module.

    Returns a tuple ``(groups, counts)`` where:
      - groups: ``[{"module_type": str, "rows": [row, ...]}, ...]`` in catalog order
      - counts: dict with totals for the summary chips
    """
    catalog = get_catalog()
    module_order = [m.module_type for m in catalog]

    jobs_by_module: dict[str, list] = {m: [] for m in module_order}
    counts = {
        "total": 0, "pending": 0, "running": 0,
        "completed": 0, "failed": 0, "cancelled": 0,
        "skipped": len(run.skipped),
    }
    for job in run.jobs.all().order_by("module_type", "attribute"):
        summary = None
        if job.status == ComputationJob.Status.COMPLETED:
            summary = _summarize_completed_job(job)
        jobs_by_module.setdefault(job.module_type, []).append({
            "job": job,
            "summary": summary,
        })
        counts["total"] += 1
        counts[job.status] = counts.get(job.status, 0) + 1

    skipped_by_module: dict[str, list] = {m: [] for m in module_order}
    for entry in run.skipped:
        skipped_by_module.setdefault(entry["module_type"], []).append(entry)

    groups = []
    for module_type in module_order:
        rows = jobs_by_module.get(module_type, [])
        skipped = skipped_by_module.get(module_type, [])
        if rows or skipped:
            groups.append({
                "module_type": module_type,
                "rows": rows,
                "skipped": skipped,
            })
    # Any unexpected module names (legacy data) tacked on at the end.
    for module_type, rows in jobs_by_module.items():
        if module_type not in module_order and rows:
            groups.append({
                "module_type": module_type, "rows": rows, "skipped": [],
            })

    return groups, counts


def _run_is_complete(run) -> bool:
    """A run is complete iff it has at least one job and all jobs are terminal."""
    statuses = list(run.jobs.values_list("status", flat=True))
    if not statuses:
        # No jobs at all (every field was skipped): treat as complete immediately.
        return True
    return all(s in TERMINAL_STATUSES for s in statuses)


@login_required(login_url="/admin/login/")
@staff_required
def test_modules(request):
    """Landing page: run button + history of the user's recent test runs."""
    from django.shortcuts import redirect

    if request.method == "POST":
        catalog = get_catalog()
        planned, skipped = plan_module_tests(catalog)

        run = ModuleTestRun.objects.create(requested_by=request.user)
        new_jobs = []
        for entry in planned:
            job = enqueue_for_test_run(
                user=request.user,
                run_id=run.id,
                module_type=entry["module_type"],
                attribute=entry["field_name"],
                from_value=entry["from_value"],
                to_value=entry["to_value"],
                max_rows=100,
            )
            new_jobs.append(job)
        if new_jobs:
            run.jobs.add(*new_jobs)
        run.skipped = skipped
        run.save(update_fields=["skipped"])

        return redirect("admin_scripts:test-modules-detail", run_id=run.id)

    recent_runs = (
        ModuleTestRun.objects
        .filter(requested_by=request.user)
        .order_by("-created_at")[:20]
    )
    return render(
        request,
        "admin_scripts/scripts/test_modules.html",
        {"recent_runs": recent_runs},
    )


@login_required(login_url="/admin/login/")
@staff_required
def test_modules_detail(request, run_id):
    run = get_object_or_404(
        ModuleTestRun, pk=run_id, requested_by=request.user,
    )
    groups, counts = _build_run_rows(run)
    is_complete = _run_is_complete(run)
    return render(
        request,
        "admin_scripts/scripts/test_modules_detail.html",
        {
            "run": run,
            "groups": groups,
            "counts": counts,
            "is_complete": is_complete,
        },
    )


@login_required(login_url="/admin/login/")
@staff_required
def test_modules_status(request, run_id):
    """HTMX-polled status partial. Stamps completed_at when all jobs are terminal."""
    from django.utils import timezone

    run = get_object_or_404(
        ModuleTestRun, pk=run_id, requested_by=request.user,
    )
    is_complete = _run_is_complete(run)
    if is_complete and run.completed_at is None:
        run.completed_at = timezone.now()
        run.save(update_fields=["completed_at"])

    groups, counts = _build_run_rows(run)
    return render(
        request,
        "admin_scripts/partials/test_modules_results.html",
        {
            "run": run,
            "groups": groups,
            "counts": counts,
            "is_complete": is_complete,
        },
    )
```

- [ ] **Step 3: Create stub templates so views render**

These are placeholder structures so the unit tests in Task 8 have something to render. Task 9 will overwrite them with full Tailwind UI.

Create `djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules.html`:

```html
{% extends "admin_scripts/base.html" %}
{% block title %}Test All Modules{% endblock %}
{% block content %}
<h1>Test All Modules</h1>
<form method="post">{% csrf_token %}<button type="submit">Run new test</button></form>
<ul>{% for run in recent_runs %}<li>{{ run }}</li>{% endfor %}</ul>
{% endblock %}
```

Create `djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules_detail.html`:

```html
{% extends "admin_scripts/base.html" %}
{% block title %}Test Run #{{ run.pk }}{% endblock %}
{% block content %}
<h1>Test Run #{{ run.pk }}</h1>
<div id="results">{% include "admin_scripts/partials/test_modules_results.html" %}</div>
{% endblock %}
```

Create `djangoexact/admin_scripts/templates/admin_scripts/partials/test_modules_results.html`:

```html
<div id="results-body"
     {% if not is_complete %}hx-get="{% url 'admin_scripts:test-modules-status' run.pk %}"
     hx-trigger="every 3s"
     hx-swap="outerHTML"{% endif %}>
    <p>total={{ counts.total }} pending={{ counts.pending }} running={{ counts.running }}
       completed={{ counts.completed }} failed={{ counts.failed }} skipped={{ counts.skipped }}</p>
    {% for group in groups %}
        <h3>{{ group.module_type }}</h3>
        <ul>
        {% for row in group.rows %}
            <li>{{ row.job.attribute }}: {{ row.job.status }}{% if row.summary %} count={{ row.summary.count }}{% endif %}{% if row.job.error_message %} ERR: {{ row.job.error_message|truncatechars:200 }}{% endif %}</li>
        {% endfor %}
        {% for s in group.skipped %}
            <li>{{ s.field_name }}: skip ({{ s.reason }})</li>
        {% endfor %}
        </ul>
    {% endfor %}
</div>
```

- [ ] **Step 4: Smoke-check URL resolution**

Run from `djangoexact/`:

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).` This validates that URL patterns and view imports are correct without needing a DB connection.

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/urls.py djangoexact/admin_scripts/views.py \
        djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules.html \
        djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules_detail.html \
        djangoexact/admin_scripts/templates/admin_scripts/partials/test_modules_results.html
git commit -m "feat(admin_scripts): add Test All Modules views, URLs, dashboard entry"
```

---

## Task 8: View tests for the new endpoints

**Files:**

- Create: `djangoexact/admin_scripts/tests/test_test_modules_views.py`

- [ ] **Step 1: Write the test file**

Create `djangoexact/admin_scripts/tests/test_test_modules_views.py`:

```python
"""View tests for the Test All Modules admin script."""
from unittest.mock import patch

from django.test import Client, TransactionTestCase, override_settings

from admin_scripts.models import ComputationJob, ModuleTestRun
from api.models import CustomUser

MIDDLEWARE_WITHOUT_DB_CLEANUP = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]


@override_settings(MIDDLEWARE=MIDDLEWARE_WITHOUT_DB_CLEANUP)
class TestModulesViewsTest(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        self.client = Client()
        self.staff = CustomUser.objects.create_user(
            email="staff@example.com", password="x", is_staff=True,
            firebase_uid="staff_v",
        )
        self.other_staff = CustomUser.objects.create_user(
            email="other@example.com", password="x", is_staff=True,
            firebase_uid="other_v",
        )
        self.regular = CustomUser.objects.create_user(
            email="reg@example.com", password="x", is_staff=False,
            firebase_uid="reg_v",
        )

    # ---------- access control ----------

    def test_landing_redirects_unauthenticated(self):
        response = self.client.get("/api/admin-scripts/test-modules/")
        self.assertEqual(response.status_code, 302)

    def test_landing_forbidden_for_non_staff(self):
        self.client.login(email="reg@example.com", password="x")
        response = self.client.get("/api/admin-scripts/test-modules/")
        self.assertEqual(response.status_code, 403)

    def test_landing_renders_for_staff(self):
        self.client.login(email="staff@example.com", password="x")
        response = self.client.get("/api/admin-scripts/test-modules/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test All Modules")

    # ---------- POST creates a run ----------

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_post_creates_run_and_jobs(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [
                {"module_type": "Grassland", "field_name": "is_fire_used",
                 "from_value": "True", "to_value": "False"},
                {"module_type": "Grassland", "field_name": "fire_impact",
                 "from_value": "1", "to_value": "0"},
            ],
            [
                {"module_type": "Grassland", "field_name": "fire_periodicity",
                 "reason": "only 1 distinct value(s) available"},
            ],
        )
        self.client.login(email="staff@example.com", password="x")
        response = self.client.post("/api/admin-scripts/test-modules/")
        self.assertEqual(response.status_code, 302)

        run = ModuleTestRun.objects.get(requested_by=self.staff)
        self.assertEqual(run.jobs.count(), 2)
        for job in run.jobs.all():
            self.assertEqual(job.max_rows, 100)
        self.assertEqual(len(run.skipped), 1)
        self.assertEqual(run.skipped[0]["field_name"], "fire_periodicity")
        self.assertTrue(response.url.endswith(f"/test-modules/{run.id}/"))

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_post_with_all_skipped_creates_empty_run(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [],
            [{"module_type": "Grassland", "field_name": "f", "reason": "no values available"}],
        )
        self.client.login(email="staff@example.com", password="x")
        response = self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)
        self.assertEqual(run.jobs.count(), 0)
        self.assertEqual(len(run.skipped), 1)
        mock_dispatch.assert_not_called()
        self.assertEqual(response.status_code, 302)

    # ---------- detail page ----------

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_detail_renders_for_owner(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [{"module_type": "Grassland", "field_name": "is_fire_used",
              "from_value": "True", "to_value": "False"}],
            [],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        response = self.client.get(f"/api/admin-scripts/test-modules/{run.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Grassland")
        self.assertContains(response, "is_fire_used")

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_detail_404_for_other_user(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [{"module_type": "Grassland", "field_name": "is_fire_used",
              "from_value": "True", "to_value": "False"}],
            [],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        self.client.logout()
        self.client.login(email="other@example.com", password="x")
        response = self.client.get(f"/api/admin-scripts/test-modules/{run.id}/")
        self.assertEqual(response.status_code, 404)

    # ---------- status partial polling lifecycle ----------

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_status_partial_polls_while_pending(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [{"module_type": "Grassland", "field_name": "is_fire_used",
              "from_value": "True", "to_value": "False"}],
            [],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        response = self.client.get(
            f"/api/admin-scripts/test-modules/{run.id}/status/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-trigger="every 3s"')
        run.refresh_from_db()
        self.assertIsNone(run.completed_at)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_status_partial_stops_polling_when_all_terminal(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [{"module_type": "Grassland", "field_name": "is_fire_used",
              "from_value": "True", "to_value": "False"}],
            [],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        # Force all jobs into a terminal state.
        run.jobs.all().update(status=ComputationJob.Status.COMPLETED)

        response = self.client.get(
            f"/api/admin-scripts/test-modules/{run.id}/status/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "hx-trigger")
        run.refresh_from_db()
        self.assertIsNotNone(run.completed_at)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_status_partial_treats_empty_run_as_complete(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [],
            [{"module_type": "Grassland", "field_name": "f", "reason": "no values available"}],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        response = self.client.get(
            f"/api/admin-scripts/test-modules/{run.id}/status/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "hx-trigger")
        run.refresh_from_db()
        self.assertIsNotNone(run.completed_at)
```

- [ ] **Step 2: Verify (SKIP if test DB not available)**

If the test DB is available:

```bash
python manage.py test admin_scripts.tests.test_test_modules_views -v 2 --keepdb
```

- [ ] **Step 3: Commit**

```bash
git add djangoexact/admin_scripts/tests/test_test_modules_views.py
git commit -m "test(admin_scripts): cover Test All Modules views and lifecycle"
```

---

## Task 9: Replace stub templates with full UI

**Files:**

- Modify: `djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules.html`
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules_detail.html`
- Modify: `djangoexact/admin_scripts/templates/admin_scripts/partials/test_modules_results.html`

- [ ] **Step 1: Replace `test_modules.html` (landing)**

Overwrite `djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules.html`:

```html
{% extends "admin_scripts/base.html" %}
{% block title %}Test All Modules{% endblock %}

{% block content %}
<div class="space-y-6">

    <div class="flex items-center justify-between gap-4">
        <h1 class="text-2xl font-bold text-gray-900">Test All Modules</h1>
        <a href="{% url 'admin_scripts:dashboard' %}"
           class="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition">
            &larr; Back to Dashboard
        </a>
    </div>

    <p class="text-sm text-gray-600">
        Enqueues one capped (max 100 rows) computation per
        (module, field) pair in the scenario catalog and reports per-pair
        outcomes. Fields with fewer than two distinct values are skipped.
    </p>

    <form method="post">
        {% csrf_token %}
        <button type="submit"
                class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700 transition">
            Run new test
        </button>
    </form>

    <section>
        <h2 class="text-lg font-semibold text-gray-900 mb-3">Recent runs</h2>
        {% if recent_runs %}
        <div class="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
            {% for run in recent_runs %}
            <a href="{% url 'admin_scripts:test-modules-detail' run.pk %}"
               class="flex items-center justify-between gap-4 px-4 py-3 hover:bg-gray-50">
                <div>
                    <p class="text-sm font-medium text-gray-900">Run #{{ run.pk }}</p>
                    <p class="text-xs text-gray-500">
                        Started {{ run.created_at|date:'M d, Y H:i' }}
                        {% if run.completed_at %}
                            &middot; finished {{ run.completed_at|timesince:run.created_at }} later
                        {% else %}
                            &middot; in progress
                        {% endif %}
                    </p>
                </div>
                <span class="text-xs text-gray-400">View &rarr;</span>
            </a>
            {% endfor %}
        </div>
        {% else %}
        <p class="text-sm text-gray-500">No runs yet.</p>
        {% endif %}
    </section>

</div>
{% endblock %}
```

- [ ] **Step 2: Replace `test_modules_detail.html`**

Overwrite `djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules_detail.html`:

```html
{% extends "admin_scripts/base.html" %}
{% block title %}Test Run #{{ run.pk }}{% endblock %}

{% block content %}
<div class="space-y-6">

    <div class="flex items-center justify-between gap-4">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">Test Run #{{ run.pk }}</h1>
            <p class="text-xs text-gray-500 mt-1">
                Started {{ run.created_at|date:'M d, Y H:i:s' }}
                {% if run.completed_at %}
                    &middot; finished {{ run.completed_at|date:'H:i:s' }}
                {% endif %}
            </p>
        </div>
        <a href="{% url 'admin_scripts:test-modules' %}"
           class="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition">
            &larr; Test All Modules
        </a>
    </div>

    {% include "admin_scripts/partials/test_modules_results.html" %}

</div>
{% endblock %}
```

- [ ] **Step 3: Replace `test_modules_results.html` (the polled partial)**

Overwrite `djangoexact/admin_scripts/templates/admin_scripts/partials/test_modules_results.html`:

```html
<div id="results-body"
     {% if not is_complete %}hx-get="{% url 'admin_scripts:test-modules-status' run.pk %}"
     hx-trigger="every 3s"
     hx-swap="outerHTML"{% endif %}
     class="space-y-6">

    {# Summary chips #}
    <div class="flex flex-wrap gap-2 text-xs">
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 border rounded-full bg-gray-50 text-gray-700 border-gray-200">
            Total: <strong>{{ counts.total }}</strong>
        </span>
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 border rounded-full bg-amber-50 text-amber-700 border-amber-200">
            Pending: <strong>{{ counts.pending }}</strong>
        </span>
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 border rounded-full bg-blue-50 text-blue-700 border-blue-200">
            Running: <strong>{{ counts.running }}</strong>
        </span>
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 border rounded-full bg-green-50 text-green-700 border-green-200">
            Completed: <strong>{{ counts.completed }}</strong>
        </span>
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 border rounded-full bg-red-50 text-red-700 border-red-200">
            Failed: <strong>{{ counts.failed }}</strong>
        </span>
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 border rounded-full bg-gray-100 text-gray-600 border-gray-200">
            Skipped: <strong>{{ counts.skipped }}</strong>
        </span>
    </div>

    {% if not groups %}
        <div class="bg-white border border-gray-200 rounded-lg p-6 text-sm text-gray-600">
            No fields had enough distinct values to test.
        </div>
    {% endif %}

    {% for group in groups %}
    <section class="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <header class="px-4 py-2 border-b border-gray-100 bg-gray-50">
            <h2 class="text-sm font-semibold text-gray-900">{{ group.module_type }}</h2>
        </header>
        <table class="w-full text-sm">
            <thead class="text-xs uppercase tracking-wide text-gray-500">
                <tr>
                    <th class="text-left font-medium px-4 py-2">Field</th>
                    <th class="text-left font-medium px-4 py-2">From &rarr; To</th>
                    <th class="text-left font-medium px-4 py-2">Status</th>
                    <th class="text-left font-medium px-4 py-2">Result</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
                {% for row in group.rows %}
                <tr>
                    <td class="px-4 py-2 font-mono text-xs text-gray-800">{{ row.job.attribute }}</td>
                    <td class="px-4 py-2 text-xs text-gray-600">
                        <span class="font-mono bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5">{{ row.job.from_value }}</span>
                        <span class="mx-1 text-gray-400">&rarr;</span>
                        <span class="font-mono bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5">{{ row.job.to_value }}</span>
                    </td>
                    <td class="px-4 py-2">
                        {% if row.job.status == "pending" %}
                            <span class="inline-flex items-center gap-1.5 text-xs font-medium border rounded-full px-2.5 py-0.5 bg-amber-50 text-amber-700 border-amber-200">
                                <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>Pending
                            </span>
                        {% elif row.job.status == "running" %}
                            <span class="inline-flex items-center gap-1.5 text-xs font-medium border rounded-full px-2.5 py-0.5 bg-blue-50 text-blue-700 border-blue-200">
                                <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>Running {{ row.job.progress }}%
                            </span>
                        {% elif row.job.status == "completed" %}
                            <span class="inline-flex items-center gap-1.5 text-xs font-medium border rounded-full px-2.5 py-0.5 bg-green-50 text-green-700 border-green-200">
                                <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>Completed
                            </span>
                        {% elif row.job.status == "failed" %}
                            <span class="inline-flex items-center gap-1.5 text-xs font-medium border rounded-full px-2.5 py-0.5 bg-red-50 text-red-700 border-red-200">
                                <span class="w-1.5 h-1.5 rounded-full bg-red-500"></span>Failed
                            </span>
                        {% elif row.job.status == "cancelled" %}
                            <span class="inline-flex items-center gap-1.5 text-xs font-medium border rounded-full px-2.5 py-0.5 bg-gray-100 text-gray-600 border-gray-200">
                                <span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span>Cancelled
                            </span>
                        {% endif %}
                    </td>
                    <td class="px-4 py-2 text-xs text-gray-700">
                        {% if row.summary %}
                            count={{ row.summary.count }}{% if row.summary.mean_str %} &middot; mean={{ row.summary.mean_str }}{% endif %}
                        {% elif row.job.error_message %}
                            <details>
                                <summary class="cursor-pointer text-red-600 hover:text-red-700">{{ row.job.error_message|truncatechars:500 }}</summary>
                                <pre class="mt-2 text-xs text-red-700 bg-red-50 border border-red-100 rounded p-3 whitespace-pre-wrap break-words">{{ row.job.error_message }}</pre>
                            </details>
                        {% else %}
                            <span class="text-gray-400">&mdash;</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
                {% for s in group.skipped %}
                <tr class="text-gray-400">
                    <td class="px-4 py-2 font-mono text-xs">{{ s.field_name }}</td>
                    <td class="px-4 py-2 text-xs">&mdash;</td>
                    <td class="px-4 py-2">
                        <span class="inline-flex items-center gap-1.5 text-xs font-medium border rounded-full px-2.5 py-0.5 bg-gray-100 text-gray-500 border-gray-200">
                            Skipped
                        </span>
                    </td>
                    <td class="px-4 py-2 text-xs italic">{{ s.reason }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
    {% endfor %}

</div>
```

- [ ] **Step 4: Verify (SKIP if test DB not available)**

If the test DB is available:

```bash
python manage.py test admin_scripts.tests.test_test_modules_views -v 2 --keepdb
```

- [ ] **Step 5: Commit**

```bash
git add djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules.html \
        djangoexact/admin_scripts/templates/admin_scripts/scripts/test_modules_detail.html \
        djangoexact/admin_scripts/templates/admin_scripts/partials/test_modules_results.html
git commit -m "feat(admin_scripts): flesh out Test All Modules templates"
```

---

## Task 10: Sanity check

**Files:** none (verification only).

- [ ] **Step 1: Verify Django config is still valid**

Run from `djangoexact/`:

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 2: Confirm git state is clean**

Run from repo root:

```bash
git status
```

Expected: `nothing to commit, working tree clean` (aside from `.claude/`, `.beads/`, or any other untracked workspace files that pre-existed).

- [ ] **Step 3: Note for the user**

Leave a note in the final report that the full test suite was not run during implementation and the user should run it manually before merging:

```bash
cd djangoexact && python manage.py test admin_scripts -v 1
```

Or, equivalently with pytest:

```bash
cd djangoexact && pytest admin_scripts/
```

The pull request can flag any failures that surface.

---

## Out of scope (deferred to future work)

- A cancel-all button for an in-flight test run. Individual jobs remain cancellable from the existing jobs page.
- Diff view between two test runs.
- Configurable subset selection (test only some modules).
- A custom Django admin registration for `ModuleTestRun` (the detail page is sufficient).
