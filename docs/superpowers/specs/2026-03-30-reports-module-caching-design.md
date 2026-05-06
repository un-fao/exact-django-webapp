# Reports Module Caching Design

**Date:** 2026-03-30
**Status:** Approved
**Branch:** `feature/reports-module-cache-reads`

---

## Context

Every report request re-runs the full calculator for each module, even when the module data hasn't changed. Modules already carry a `CachedResultMixin` with `cached_results_by_activity_by_gas` (a dict with `"balance"`, `"total_w"`, `"total_wo"`, `"inventory"` keys) that is populated by the public API endpoint. `extract_emissions()` already supports this dict format. The pattern of reading from this cache is already proven in `modules.py` for submodule-level caching (Transport, Processing reports). This feature generalises that pattern to all top-level modules.

---

## Goal

When a module has a valid cache (`is_cached_results_valid()` returns `True`), skip `calculator.calculate()` and populate `emissions_set / emissions_set_w / emissions_set_wo` directly from `cached_results_by_activity_by_gas`. Fall back to the calculator when the cache is absent or stale. Keep the two paths entirely separate.

---

## Architecture

```
reports/
├── cache.py   NEW  — CacheResult, load_emissions_from_cache(), build_inventory_from_cache()
├── base.py    MOD  — __post_init__ dispatcher, LandModuleReport _from_cache guard
└── (all other files unchanged)
```

No DB migrations. No changes to `modules.py`, `land.py`, `renderer.py`, `html_context.py`, or `models.py`.

---

## `reports/cache.py` (new, ~50 lines)

Pure-Python module. No Django ORM, no calculator imports. No side effects.

### `CacheResult` dataclass

```python
@dataclass
class CacheResult:
    balance: Any          # cached_results_by_activity_by_gas["balance"]  → emissions_set
    with_project: Any     # cached_results_by_activity_by_gas["total_w"]  → emissions_set_w
    without_project: Any  # cached_results_by_activity_by_gas["total_wo"] → emissions_set_wo
    inventory: list       # cached_results_by_activity_by_gas["inventory"]
```

### `load_emissions_from_cache(module) -> CacheResult | None`

Returns `None` when:
- `module.is_cached_results_valid()` is `False`
- `module.cached_results_by_activity_by_gas` is `None`

Otherwise returns a `CacheResult` mapping the three scenario keys.

### `build_inventory_from_cache(cached_inventory, module, activity_title) -> list[InventoryItem]`

Reconstructs `InventoryItem` list from the cached inventory list:
```
{"activity": "Biomass", "gas_type": {"name": "CO2"}, "value": 1530.4}
→ InventoryItem(activity_name=activity_title, module_name=..., ipcc_category="Biomass", gas_type="CO2", value=1530.4)
```

---

## `reports/base.py` changes

### `BaseModuleReport` dataclass

Two new fields (with defaults, no impact on call sites):
```python
_from_cache: bool = field(default=False, repr=False)
_cached_inventory: list = field(default_factory=list, repr=False)
```

### `__post_init__` — dispatcher

```python
def __post_init__(self):
    from .cache import load_emissions_from_cache
    cache_result = load_emissions_from_cache(self.module)
    if cache_result is not None:
        self._init_from_cache(cache_result)
    else:
        self._init_from_calculator()
```

### `_init_from_cache(cache_result)` — cached path

```python
def _init_from_cache(self, cache_result):
    self.emissions_set    = cache_result.balance
    self.emissions_set_w  = cache_result.with_project
    self.emissions_set_wo = cache_result.without_project
    self._cached_inventory = cache_result.inventory
    self._from_cache = True
```

### `_init_from_calculator()` — calculated path (existing logic, extracted)

Unchanged logic: `self.calculator.calculate()`, populate `result`, `inventory`, `emissions_set*`.

### `_inventory_items_from_module()` — updated branch

```python
def _inventory_items_from_module(self, activity_title):
    if self._from_cache:
        from .cache import build_inventory_from_cache
        return build_inventory_from_cache(self._cached_inventory, self.module, activity_title)
    # existing logic unchanged
    if self.inventory is None:
        return []
    ...
```

### `LandModuleReport.__post_init__` — cache guard

```python
def __post_init__(self):
    super().__post_init__()
    length = self.module.activity.implementation_years + self.module.activity.capitalization_years
    if self._from_cache:
        self._units_breakdown_w  = [0.0] * length
        self._units_breakdown_wo = [0.0] * length
    else:
        break_w  = getattr(self.calculator.math_w,  "hectares_total", np.zeros(length))
        break_wo = getattr(self.calculator.math_wo, "hectares_total", np.zeros(length))
        self._units_breakdown_w  = list(np.round(break_w,  2))
        self._units_breakdown_wo = list(np.round(break_wo, 2))
```

---

## Data flow

```
BaseModuleReport.__post_init__
    │
    ├─ load_emissions_from_cache(module) → CacheResult?
    │
    ├─ CACHED PATH
    │   _init_from_cache():
    │     emissions_set   ← cached["balance"]
    │     emissions_set_w ← cached["total_w"]
    │     emissions_set_wo← cached["total_wo"]
    │     _from_cache = True
    │
    └─ CALCULATED PATH  (unchanged)
        _init_from_calculator():
          calculator.calculate() → result, inventory
          Result(*result).balance.yearly_emissions_by_sector_by_gas → emissions_set
          ...

LandModuleReport.__post_init__ (after super())
    _from_cache=True  → units_breakdown_w/wo = [0.0] * length
    _from_cache=False → calculator.math_w.hectares_total  (unchanged)

_inventory_items_from_module()
    _from_cache=True  → build_inventory_from_cache(...)
    _from_cache=False → self.inventory.emissions_by_sector_by_gas  (unchanged)
```

No changes required downstream: `extract_emissions()`, `_build_aggregated_from_module_emissions`, and `html_context._gas_totals` all already handle the dict format that the cache returns.

---

## Known limitation

**Land module `units_breakdown`:** When using cache, `units_breakdown_w/wo` is set to `[0.0] * duration` because `calculator.math_w.hectares_total` is only available after `calculate()` is called. This affects the "Additional Indicators" sheet (land area rows) and the cumulative hectares row in Results. Future work: cache `units_breakdown` alongside emissions (requires either a new model field or storing it in the existing cache payload).

---

## Verification

1. **Unit — `cache.py`**
   - `load_emissions_from_cache` returns `None` when `is_cached_results_valid()` is `False`
   - `load_emissions_from_cache` returns `None` when `cached_results_by_activity_by_gas` is `None`
   - `load_emissions_from_cache` maps keys correctly when cache is valid
   - `build_inventory_from_cache` produces correct `InventoryItem` list

2. **Integration — non-land module, valid cache**
   - Generate Excel report; assert output identical to uncached report for the same data

3. **Integration — cache miss**
   - Module with no cache / stale cache → calculator path runs, report is correct

4. **Integration — land module + cache**
   - `units_breakdown_w/wo` are all zeros; rest of report data is correct

5. **Integration — mixed**
   - Project with some modules cached, some not → cached modules use cache, uncached use calculator; final Excel is correct
