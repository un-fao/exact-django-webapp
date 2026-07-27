# Coding Conventions

**Analysis Date:** 2026-07-08

## Naming Patterns

**Files:**
- Python modules use `snake_case.py` format
- Test files follow `test_*.py` pattern or inherit naming from subjects
- Examples: `calculators.py`, `models.py`, `serializers.py`, `test_faostat_service.py`, `test_reference_bootstrap.py`

**Functions:**
- All functions use `snake_case`
- Descriptive names: `get_or_raise()`, `find_modules()`, `build_luc_fixture()`, `has_project_permission()`
- Prefix convention: `get_*`, `find_*`, `create_*`, `update_*`, `delete_*`
- Examples: `get_model()`, `find_organic_soil_parent_module()`, `copy_project()`, `validate_catalog()`

**Variables:**
- Lowercase `snake_case` for all variables
- Boolean prefixes: `is_*`, `has_*`, `can_*`
- Examples: `is_fire_used_start`, `has_project_permission`, `can_access`

**Classes:**
- `PascalCase` for all class names
- Model classes: descriptive nouns like `CustomUser`, `ProjectMembership`, `LandUseChange`
- Test classes: `*TestCase` or `*Test` suffix
- Factory classes: `*Factory` suffix
- Exception classes: inherit from base exception with `*Error` suffix
- Examples: `AnnualCroplandTestCase`, `UserFactory`, `FAOSTATError`, `FAOSTATNetworkError`

**Constants:**
- `UPPER_CASE` for module-level constants
- Examples: `RICE_CULTIVATION_DAYS = 113`, `CN_RATIO_CROP = 10`

**Enums:**
- `PascalCase` for enum class names
- `UPPER_CASE` for enum members
- Include descriptive values for utility: `ScenarioTypes.START = "start"` with verbose name
- Examples: `ScenarioTypes`, `EmissionTypes.CO2`, `InvitationStatus.PENDING`

## Code Style

**Formatting:**
- No official code formatter enforced (no Black, Prettier, or Ruff configuration detected)
- Four-space indentation standard per Django/Python conventions
- Line length not explicitly limited; codebase shows ~100-120 character typical lines
- No trailing commas enforced in standard patterns

**Linting:**
- No `.eslintrc`, `.flake8`, `.pylintrc`, or `pyproject.toml` with tool.black/ruff detected
- Security scanning expected: `bandit -r djangoexact` and `pip-audit` run before PRs (per CLAUDE.md)
- No TypeScript/JavaScript in this project; frontend assets compiled via webpack/npm

**Import Organization:**

Order (in this sequence):
1. Standard library: `import os`, `import json`, `import logging`
2. Third-party libraries: `from django.*`, `from rest_framework.*`, `from factory.*`
3. Django/project apps: `from ipcc.models import *`, `from api.models import *`
4. Local utilities: `from . import utilities`, `from .models import CustomUser`

No blank lines between groups in most files observed; pragmatic rather than rigid.

Examples from codebase:
```python
# api/calculators.py
import re
import copy
import json
from django.core import exceptions
import logging as log
from abc import ABC, abstractmethod
from django.apps import apps
from django.db.models import Q
import django.db.models as models
from ipcc import models as ipcc
from math_model.no_time_dependency_final.annuals import AnnualCropland as MathAnnualCropland
from api.utilities import FOSSIL_METHANE_FUELS, getattr_or_default
from . import utilities as utils
from .models import (Activity, Comment, ...)
```

**Path Aliases:**
- Relative imports for local modules: `from . import utilities`, `from .models import Activity`
- Full paths for cross-app imports: `from ipcc.models import *`, `from api.models import CustomUser`

## Error Handling

**Pattern: Exception Hierarchy**
- Define a base exception class for each domain
- Create specific exception subclasses that inherit from the base
- Callers can catch base type when they do not distinguish causes

Example from `api/faostat_exceptions.py`:
```python
class FAOSTATError(Exception):
    """Base exception for all FAOSTAT service errors."""

class FAOSTATNoDataError(FAOSTATError):
    """Raised when the FAOSTAT API returns no data."""

class FAOSTATNetworkError(FAOSTATError):
    """Raised when the FAOSTAT API is unreachable."""

class FAOSTATInvalidInputError(FAOSTATError):
    """Raised when inputs are empty or unrecognized."""
```

**Pattern: Try/Except in Views**
- DRF views catch specific exceptions first, then generic `Exception`
- Log exceptions with `logger.exception(e)` to capture full stack
- Return DRF `ValidationError` or `ErrorResponse` with descriptive messages
- Examples in `api/views.py`:
  - Catch `Project.DoesNotExist` for 404
  - Catch `FieldDoesNotExist` for schema-related errors
  - Catch generic `Exception` as fallback with logging

Pattern:
```python
try:
    # operation
except SpecificException as e:
    logger.error(f"Specific: {e}")
    raise ValidationError(f"User-facing message: {str(e)}")
except Exception as e:
    logger.exception(e)  # Full traceback
    raise ValidationError("Unexpected error occurred")
```

**Pattern: Validation in Serializers**
- Use `serializer.is_valid(raise_exception=True)` in views
- DRF raises `ValidationError` automatically on invalid data
- Custom validation in serializer methods with descriptive messages

**Pattern: Defensive Defaults**
- Use `getattr_or_default(obj, key, default=0)` from utilities for safe field access
- Query methods: `filter().first()` instead of `get()` when absence is possible
- Example: `cpk_optional = models.ForeignKey(..., null=True, blank=True)`

## Logging

**Framework:** `logging` module (Python standard library)

**Conventions:**
- Import as `import logging as log` (consistent alias)
- Module logger: `logger = logging.getLogger("console")` in views
- Usage: `logger.info()`, `logger.error()`, `logger.exception(e)`
- `logger.exception(e)` includes full stack trace; use for unexpected errors

Examples:
```python
# api/base_test_classes.py
import logging as log
log.basicConfig(level=log.INFO)
log.info(f"Created project with parameters {self.get_parameters(self.project)}")
log.error(traceback.format_exc())

# api/views.py
logger = logging.getLogger("console")
logger.error(f"Activity {pk} generated an exception: {exc}")
logger.exception(e)  # Full traceback
```

**When to Log:**
- Info: Major operations (module created, project copied)
- Error: Caught exceptions with context
- Exception: Unexpected errors, include stack trace

## Comments

**When to Comment:**
- Complex algorithm steps (especially in math_model layers)
- Non-obvious field mappings or transformations
- Why, not what (code shows what; comments explain why)
- Example from `api/services/luc_compute.py`:
  ```python
  # The LUC calculator gates on module.status == READY for every sibling
  # (api/calculators.py:1117 in OtherLandUseCalculator, :823 in
  # DeforestationCalculator). Module.status is nullable with no default,
  # so a fresh instance has status=None and the calculator raises
  # "All modules associated with the land use change must be ready" or
  # "Forest module is not complete". Mirror the factories.py convention
  # and set it explicitly.
  ```

**Docstrings:**
- Module-level docstrings at top of file, triple quotes
- Function docstrings for complex logic, especially in test helpers
- Format: One-line summary, blank line, detailed description if needed
- Example from `api/calculators.py`:
  ```python
  """
  Calculators module for the EX-ACT Django application.

  This module contains calculator classes that interface between Django models and the mathematical
  emission calculation models. Each calculator:
  1. Fetches the necessary input data from Django models
  2. Retrieves default values from IPCC tables when needed
  ...
  """
  ```

## Function Design

**Size:**
- Most functions 10-50 lines
- Utilities: 5-15 lines (helpers like `avg()`, `snake_case()`)
- Methods: 20-40 lines (calculators, serializers)
- No explicit size limit enforced

**Parameters:**
- Positional for required arguments
- Keyword-only for optional complex objects
- Type hints used inconsistently; some functions have them, most don't
- Example: `def get_or_raise(model, filter_criteria, error_message, method="get")`

**Return Values:**
- Single return or tuple for multi-value returns
- Example from tests: `data, errors = _compute_luc_slice(...)`
- None for void operations (save, update)
- Dataclass or SimpleNamespace for structured returns

## Module Design

**Exports:**
- Top-level functions and classes exported by default (no `__all__` widely used)
- Star imports common in test factories: `from .models import *`, `from .factories import *`
- Explicit imports preferred in production code: `from api.models import CustomUser as User`

**Barrel Files:**
- `__init__.py` files typically empty or minimal
- No centralized re-exports pattern observed; each module imports what it needs

**Patterns:**
- Utilities collected in `utilities.py` with single-purpose functions
- Services layer in `services/` subdirectory (e.g., `luc_compute.py`, `minitool_changes_import.py`)
- Calculators isolated in `calculators.py` (adapter layer between models and math_model)
- Models, serializers, views organized by app (`api/models.py`, `api/serializers.py`, etc.)

## Validators

**Field Validators:**
- Use Django's `validators.RegexValidator` for field constraints
- Define at module level for reuse
- Example from `api/models.py`:
  ```python
  alphanumeric = validators.RegexValidator(r"^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed.")
  letters_only = validators.RegexValidator(r"^[a-zA-Z]*$", "Only letters are allowed.")
  pc_as_float = validators.RegexValidator(r"^[0-1]*\.?[0-9]*$", "Only correctly formatted percentages are allowed.")
  
  class CustomUser(AbstractUser):
      firebase_uid = models.CharField(..., validators=[alphanumeric], ...)
  ```

## Commit Conventions

**Format:** Conventional Commits enforced by commitizen (`cz.toml` specifies `cz_conventional_commits`)

**Types:**
- `feat:` - New feature (e.g., "feat(api): compute_module_slice routes LandUseChange")
- `fix:` - Bug fix (e.g., "fix(reports): correct fishery catch totals")
- `test:` - Test additions/changes (e.g., "test(admin_scripts): end-to-end LUC enqueue")
- `chore:` - Maintenance (e.g., "chore: remove em-dashes from LUC permutation code")
- `docs:` - Documentation (e.g., "docs(admin_scripts): plan to implement LandUseChange permutations")
- `refactor:` - Code refactoring (e.g., "refactor(api): drop Staff group auto-sync signals")

**Format:** `type(scope): brief one-line description`
- Scope optional: app name or feature area (e.g., `api`, `reports`, `calculators`)
- Description: imperative mood, no period at end
- Example: `fix(calculators): None-guard dm_content_minor for crops missing IPCC dry_matter`

**Changelog:** Automatically updated on bump via `update_changelog_on_bump = true` in cz.toml

---

*Convention analysis: 2026-07-08*
