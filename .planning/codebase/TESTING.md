# Testing Patterns

**Analysis Date:** 2026-07-08

## Test Framework

**Runner:**
- pytest 9.0.3 (installed in requirements.txt)
- Tests can also run via Django's built-in runner: `python manage.py test`
- Note: pytest-django is NOT installed; tests that need Django setup use Django's own TestCase/APITestCase classes

**Assertion Library:**
- unittest (Python standard library) assertions via Django TestCase classes
- DRF provides `status` module for HTTP status codes: `from rest_framework import status`

**Run Commands:**
```bash
# From djangoexact/ directory
pytest                                          # Run all pytest-discoverable tests
pytest api/tests/                               # Run all tests in one app
pytest api/tests/test_faostat_service.py        # Run one test file
pytest -k livestock                             # Run by keyword
python manage.py test api.tests                 # Django test runner (alternative)
python manage.py test                           # All Django tests
```

## Test File Organization

**Location:**
- Tests organized under each app's `tests/` directory
- Examples: `api/tests/`, `admin_scripts/tests/`, `math_model/tests/`
- Unit tests typically in `tests/unit/` subdirectory within each app
- Integration tests in parent `tests/` directory

**Naming:**
- Test files: `test_*.py` (pytest discovery pattern)
- Test classes: `*TestCase` or `*Test` suffix
- Test methods: `test_*` prefix (required by pytest/unittest)
- Examples: `test_reference_bootstrap.py`, `AnnualCroplandTestCase`, `test_faostat_service.py`

**Structure:**
```
djangoexact/
├── api/tests/
│   ├── __init__.py
│   ├── base_test_classes.py       # Shared test class hierarchy
│   ├── factories.py               # factory-boy model factories
│   ├── test_reference_bootstrap.py
│   ├── test_faostat_service.py
│   ├── test_compute_luc_slice.py
│   ├── modules/                   # Test scripts (not formal test classes)
│   │   ├── annual_cropland.py
│   │   └── flooded_rice.py
│   ├── unit/                      # Unit tests with API/serializer focus
│   │   ├── __init__.py
│   │   ├── factories.py           # Unit test-specific factories
│   │   ├── base_module.py         # Base test class for modules
│   │   ├── annual_cropland.py
│   │   ├── utils.py               # APITestCaseMixin and helpers
│   │   └── project.py
│   └── reports/                   # Report-specific tests
├── admin_scripts/tests/
│   ├── test_catalog.py
│   ├── test_views.py
│   └── test_jobs.py
└── math_model/tests/
    └── repro_perennial_agb_max_zero.py
```

## Test Structure

**Base Test Class Hierarchy:**

From `api/tests/base_test_classes.py` (TDD pattern with named test classes):
```python
class ProjectTest:
    """Base test setup: creates user, climates, countries, soil types, and project."""
    def __init__(self):
        self.user = User.objects.get(email="testuser@example.com")
        self.project = None
        # Helper method to create a project
    def create_project(self):
        self.project = ProjectFactory.create(owner=self.user, ...)

class ActivityTest(ProjectTest):
    """Extends ProjectTest: adds activity creation."""
    def __init__(self):
        super().__init__()
        self.create_project()
        self.activity = None
    def create_activity(self):
        self.activity = ActivityFactory.create(project=self.project, ...)

class ModuleTest(ActivityTest):
    """Extends ActivityTest: adds module creation and calculation."""
    def __init__(self):
        super().__init__()
        self.create_activity()
        self.module = None
    def create_module(self, **kwargs):
        self.module = super().create_module(self.module_type, **kwargs)
    def calculate_results(self):
        self.parent_module_results = CalculatorFactory().calculate_result(self.module)
```

These base classes are inherited by concrete test implementations, e.g.:
```python
# api/tests/modules/annual_cropland.py
class AnnualCroplandTest(t.ModuleTest):
    def __init__(self):
        super().__init__()
        self.module_type = ModuleType.objects.get(class_name="AnnualCropland")
        self.create_module()
    def test(self):
        self.calculate_results()
        generate_excel_report(self.project)

AnnualCroplandTest().test()  # Directly instantiate and run
```

**Unit Test Class Pattern:**

From `api/tests/unit/` (pytest/unittest compatible):
```python
from rest_framework.test import APITestCase
from api.tests.unit.utils import APITestCaseMixin

class AnnualCroplandTestCase(base_module.BaseModuleTestCase):
    def setUp(self):
        """Called before each test method."""
        self.ModuleClass = models.AnnualCropland
        super().setUp()  # Initializes project, user, authenticated request
        self.validated_data = factories.UnitTestAnnualCroplandFactory.get_validated_data()
        self.edit_module(self.module, self.user, self.validated_data)

    def test_modify(self):
        """Test updating module fields."""
        validated_data = copy.deepcopy(self.validated_data)
        validated_data["land_use_type_start"] = ...
        response = self.edit_module(self.module, self.user, validated_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_calculate_results(self):
        """Test API endpoint for calculation."""
        view = self.module_viewset.as_view({"get": "results"})
        request = self.request_factory.get(reverse(...))
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.module.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
```

**Django TestCase Variants Used:**

- `SimpleTestCase` - No database (for pure logic, YAML parsing, etc.)
  - Example: `admin_scripts/tests/test_catalog.py`
  - No database setup/teardown overhead

- `TestCase` - Database with rollback between tests (default, most common)
  - Example: `api/tests/test_compute_luc_slice.py`, unit tests
  - Each test runs in a transaction rolled back after completion

- `TransactionTestCase` - Full transaction support (when rollback alone is insufficient)
  - Example: `api/tests/test_reference_bootstrap.py`
  - Uses `available_apps` to scope which tables to flush
  - Slower, only when necessary

- `APITestCase` - REST framework support with database
  - Example: `api/tests/unit/annual_cropland.py`
  - Includes `APIRequestFactory` and `force_authenticate()`

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Patterns:**

```python
from unittest.mock import patch, MagicMock

# Patch external service
@patch('api.faostat_service.faostat')
def test_with_patch(mock_faostat):
    mock_faostat.get_data_df.return_value = pd.DataFrame(rows)
    # Test code here
    result = get_yield(...)
    mock_faostat.get_data_df.assert_called_once()

# Context manager pattern
with patch('api.minitool.DataManager'):
    data, errors = _compute_luc_slice(...)

# MagicMock for complex objects
mock = MagicMock()
mock.model.__name__ = 'ModelName'
mock.__class__ = type('QuerySet', (), {})
```

Example from `api/tests/test_faostat_service.py`:
```python
def _mock_faostat_returning(rows: list[dict]):
    """Return a MagicMock for the faostat module that yields *rows*."""
    mock_faostat = MagicMock()
    if rows:
        mock_faostat.get_data_df.return_value = pd.DataFrame(rows)
    else:
        mock_faostat.get_data_df.return_value = pd.DataFrame()
    mock_faostat.get_par.side_effect = _default_get_par
    return mock_faostat

@patch(_FAOSTAT_DATA_PATH)
def test_integration(mock_faostat):
    mock_faostat = _mock_faostat_returning(test_rows)
    # Test code
```

**What to Mock:**
- External API calls (FAOSTAT, Firebase, Google Cloud)
- File I/O operations (unless testing file handling specifically)
- Long-running operations (use `patch` to speed up tests)
- Non-deterministic behavior (randomness, current time)

**What NOT to Mock:**
- Django ORM queries (use test database instead)
- Core business logic (test the actual calculator functions)
- Model relationships (test via database)
- Serializer validation (test by calling serializer methods)

Example: Don't mock `CalculatorFactory().calculate_result()` in tests meant to verify calculations. Do mock it in API endpoint tests that only verify response structure.

## Fixtures and Factories

**Test Data:**

Using factory-boy `DjangoModelFactory` for model instances:
```python
from factory.django import DjangoModelFactory
import factory

class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.fuzzy.FuzzyText()
    implementation_years = factory.fuzzy.FuzzyInteger(5, 10)
    start_year_of_activities = factory.fuzzy.FuzzyInteger(2024, 2024)
    gw_potential = factory.fuzzy.FuzzyChoice(gw_potentials)

class ActivityFactory(DjangoModelFactory):
    class Meta:
        model = Activity

    name = factory.fuzzy.FuzzyText()
    change_rate = def_rate

# Usage
project = ProjectFactory.create(owner=user, climate=climate)
activity = ActivityFactory.create(project=project, name="Test Activity")
```

**Reference Data Fixtures:**

JSON fixtures loaded via management command:
```bash
# Load reference data into database
python manage.py load_reference_data --app=all

# Dump database to fixtures
python manage.py dump_reference_data --app=all

# Force overwrite (use for legitimate renames like Turkey -> Türkiye)
python manage.py dump_reference_data --app=all --force
```

Located in: `api/fixtures/`, `ipcc/fixtures/`
Manifest in: `api/fixtures_manifest.py`
Round-trip guarantee tested in: `api/tests/test_reference_bootstrap.py`

**Location:**
- Factory definitions: `api/tests/factories.py`, `api/tests/unit/factories.py`
- Fixture files: `api/fixtures/`, `ipcc/fixtures/`
- Test utilities: `api/tests/unit/utils.py`

Example helper from utils:
```python
class APITestCaseMixin:
    """Provides edit_module(), add_comment(), copy_activity() helpers."""
    def edit_module(self, module, user, data):
        request = self.request_factory.patch(f'/api/modules/{module.id}/', data=data)
        force_authenticate(request, user=user)
        return self.module_viewset(request, pk=module.pk)
```

## Coverage

**Requirements:** None enforced (no coverage.rc or pytest.ini with coverage settings)

**View Coverage:**
```bash
# No built-in command; would require pytest-cov to be added
# Not currently installed
```

**Current State:**
- Tests focus on critical paths: calculators, model creation, data import/export
- Coverage not tracked or enforced via CI
- Manual review of test coverage when adding major features recommended

## Test Types

**Unit Tests:**
- Scope: Single class or function in isolation
- Location: `api/tests/unit/`, `admin_scripts/tests/`
- Pattern: Mock external dependencies, test logic directly
- Example: `test_catalog.py` tests YAML parsing without database
- Run: `pytest api/tests/unit/`

**Integration Tests:**
- Scope: Multiple components working together (models + serializers + views, or calculators + models)
- Location: `api/tests/` (non-unit subdirectory)
- Pattern: Use test database, real Django models, mock only external services
- Example: `test_compute_luc_slice.py` tests calculator with real fixtures and LUC models
- Run: `pytest api/tests/test_*.py`

**E2E Tests:**
- Not used in this codebase
- No Selenium/Playwright tests found
- Frontend testing appears manual or via CI/CD environment

**Reference Data Integrity:**
- Tests: `test_reference_bootstrap.py`
- Ensures fixtures round-trip: load -> dump -> compare produces identical JSON
- Guards against "silent FK breakage" when PK semantic identity changes

## Common Patterns

**Async Testing:**
Not found in codebase (no async views or async database calls observed).

**Error Testing:**

Testing exception raising and handling:
```python
from api.faostat_exceptions import FAOSTATError

class TestExceptionHierarchy:
    def test_faostat_no_data_error_is_subclass_of_faostat_error(self):
        assert issubclass(FAOSTATNoDataError, FAOSTATError)

    def test_all_three_are_catchable_via_base_type(self):
        # Test that raising any subclass and catching base succeeds
        with pytest.raises(FAOSTATError):
            raise FAOSTATNetworkError("...")
```

**Transaction Rollback Pattern:**

For tests that must not persist changes (e.g., permutation testing):
```python
from django.db import transaction

with transaction.atomic():
    # Create fixtures
    luc = build_luc_fixture(...)
    # Run calculator (may fail, that's OK)
    data, errors = calculate(luc)
    # Rollback so next test sees clean DB
    transaction.set_rollback(True)
# data/errors collected; database unchanged
```

**Filtering QuerySets in Tests:**

Using `.first()` instead of `.get()` when testing optional conditions:
```python
# Preferred: returns None if not found
land_use_type = LandUseType.objects.filter(...).first()

# Avoid in tests: raises DoesNotExist if not found
try:
    land_use_type = LandUseType.objects.get(...)
except LandUseType.DoesNotExist:
    land_use_type = None
```

**Test Discovery:**

Pytest discovers tests automatically:
- Files matching `test_*.py`
- Classes matching `Test*`
- Methods matching `test_*`

Django test runner (manage.py) discovers tests in `tests.py` or `tests/` directory with proper naming.

No `pytest.ini` or `conftest.py` in repo; pytest uses Django default discovery via installed app scanning.

## Database State Management

**Test Isolation:**
- `TestCase`: Each test runs in a transaction, rolled back after completion
- Fixtures loaded via `load_reference_data` persist across test runs in the test database
- `TransactionTestCase` uses `available_apps` to limit flush scope:
  ```python
  class ReferenceDataBootstrapTests(TransactionTestCase):
      available_apps = ["api", "ipcc"]  # Only flush these app tables
  ```

**Fixture Loading:**
- IPCC reference data (countries, climate types, GWP coefficients) loaded once per test run
- Custom fixture data created per-test via factories
- `call_command("load_reference_data", "--app=all", verbosity=0)` used in tests

**Database Routing:**
- `DATABASE_ROUTERS` in settings.py point both ipcc and api to the "default" DB
- Tests use this same default database
- No sharding or multi-DB testing observed

## Known Gaps

- No E2E/UI testing with Playwright or Selenium
- Coverage reporting not enforced or tracked
- No performance/load testing framework in place
- Math model unit tests minimal (mostly integration via calculators)
- Test-module scripts (`api/tests/modules/*.py`) manually instantiated, not discovered by pytest

---

*Testing analysis: 2026-07-08*
