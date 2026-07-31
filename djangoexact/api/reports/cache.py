"""Cache adapter for the report computation pipeline.

Provides the bridge between the module-level cached results
(CachedResultMixin.cached_results_by_activity_by_gas) and the
report computation pipeline (BaseModuleReport.emissions_set*).

The cached and calculated paths are entirely separate:
  - load_emissions_from_cache()     → cached path
  - BaseModuleReport._init_from_calculator() → calculated path (unchanged)
"""
from __future__ import annotations

import logging as log
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from api.inventory_labels import inventory_label
from .data_types import InventoryItem

# Bumped whenever a fix changes the inventory a module contributes, so that
# caches written by the older code are recomputed instead of served.
INVENTORY_SCHEMA_VERSION = 2

# Modules whose cached inventory was always an empty list before the roll-up fix
# in BaseCalculator.inventory: their calculators keep no math module under the
# names the old lookup knew about, so nothing was ever recorded. Cache validity is
# keyed only on last_modified, so an untouched module would keep serving that
# empty list forever. Scoping the invalidation to these types keeps the one-time
# recompute cost off the land modules, whose cached inventory is unaffected.
INVENTORY_ROLLUP_FIXED_MODULES = frozenset({
    "Input",
    "Energy",
    "Irrigation",
    "Storage",
    "Processing",
    "Packaging",
    "Transport",
    "OrganicSoil",
})


class CacheWriteBatch:
    """Collects module cache writes during one project compute and flushes
    them as a single bulk_update per concrete module class.

    Registered modules are keyed by (type(module), module.pk) so that a
    module re-registered later in the same compute (e.g. the land-module
    minor-season re-saves) dedupes to the same entry. In the current design
    register() always receives the same instance per key (modules come from
    the shared Activity.cache_modules memo), but as a defensive measure, if
    two different instances of the same row are ever registered, the newly
    updated fields are copied onto the first-registered instance which stays
    the single source of truth, so no accumulated update is lost.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[type, Any], tuple[Any, set]] = {}

    def register(self, module, update_fields) -> None:
        key = (type(module), module.pk)
        existing_module, fields = self._entries.get(key, (None, set()))
        if existing_module is not None and existing_module is not module:
            for f in update_fields:
                setattr(existing_module, f, getattr(module, f))
            module = existing_module
        fields = fields | set(update_fields)
        self._entries[key] = (module, fields)

    def flush(self) -> None:
        by_class: dict[type, list] = defaultdict(list)
        fields_by_class: dict[type, set] = defaultdict(set)
        for (model_class, _pk), (module, fields) in self._entries.items():
            by_class[model_class].append(module)
            fields_by_class[model_class] |= fields

        for model_class, objs in by_class.items():
            fields = sorted(fields_by_class[model_class])
            if not objs or not fields:
                continue
            try:
                model_class.objects.bulk_update(objs, fields)
            except Exception as e:
                log.warning(
                    f"Could not bulk_update cache writes for {model_class.__name__}: {e}"
                )

        self._entries = {}


@dataclass
class CacheResult:
    """Emissions data loaded from a module's cached results."""
    balance: Any                        # cached["balance"]   → emissions_set
    with_project: Any                   # cached["total_w"]   → emissions_set_w
    without_project: Any                # cached["total_wo"]  → emissions_set_wo
    inventory: list = field(default_factory=list)  # cached["inventory"]
    units_breakdown_w: list | None = None
    units_breakdown_wo: list | None = None


def load_emissions_from_cache(module) -> CacheResult | None:
    """Try to load emission sets from the module's cached results.

    Returns None when:
    - The cache is invalid (module was modified after last cache write)
    - cached_results_by_activity_by_gas is None

    Otherwise returns a CacheResult mapping the three scenario keys.
    """
    if not module.is_cached_results_valid():
        return None
    cached = module.cached_results_by_activity_by_gas
    if cached is None:
        return None
    if (
        type(module).__name__ in INVENTORY_ROLLUP_FIXED_MODULES
        and cached.get("inventory_schema", 1) < INVENTORY_SCHEMA_VERSION
    ):
        # Written before the inventory roll-up fix, so its "inventory" key is an
        # empty list. Recalculate rather than serve rows that are known missing.
        return None
    units = module.cached_units_breakdown or {}
    return CacheResult(
        balance=cached["balance"],
        with_project=cached["total_w"],
        without_project=cached["total_wo"],
        inventory=cached.get("inventory") or [],
        units_breakdown_w=units.get("w"),
        units_breakdown_wo=units.get("wo"),
    )


def build_inventory_from_cache(
    cached_inventory: list,
    module: Any,
    activity_title: str,
) -> list[InventoryItem]:
    """Reconstruct InventoryItem list from cached inventory data.

    The cached inventory has the format:
        [{"activity": "Biomass", "gas_type": {"name": "CO2"}, "value": 1530.4}, ...]
    """
    items = []
    for entry in cached_inventory:
        activity = entry.get("activity") or "N/A"
        gas_type_data = entry.get("gas_type") or {}
        gas_type = (
            gas_type_data.get("name") if isinstance(gas_type_data, dict) else str(gas_type_data)
        ) or "N/A"
        value = entry.get("value", 0.0)
        items.append(InventoryItem(
            activity_name=activity_title,
            module_name=module.module_type.name,
            ipcc_category=inventory_label(module, activity),
            gas_type=gas_type,
            value=value,
        ))
    return items


def save_results_to_cache(module, emissions_set, emissions_set_w, emissions_set_wo, inventory, batch=None) -> None:
    """Persist calculator output to the module's cache after a fresh calculation.

    Only updates cached_results_by_activity_by_gas and last_cached_at so that
    future report runs hit the cache.  The other breakdown fields
    (cached_results_total, cached_results_by_activity, cached_results_by_gas)
    are left untouched; views.py will populate them on the next API call.

    When ``batch`` is provided (a CacheWriteBatch active for the current
    project compute), the in-memory field assignments below are made as
    usual but the actual write is deferred to the batch's single
    bulk_update per concrete module class, run once at the end of the
    project compute (see BaseProjectReport.compute). This is the R6
    cold-path write-batching optimization; the field assignments and their
    semantics are unchanged from the immediate-save path.

    cache_units_breakdown (a separate write, land modules only) is
    intentionally NOT part of this batch: it stays on the normal
    CachedResultMixin.save() path so its narrower, already-audited
    semantics are untouched.
    """
    from django.utils import timezone

    if module.pk is None:
        return

    def _serialize(es):
        rows = []
        for e in es:
            activity = e.activity
            if hasattr(activity, "value"):
                activity = activity.value
            rows.append({
                "activity": activity,
                "gas_type": {"name": e.gas_type.name if e.gas_type else None},
                "emissions": [{"value": v.value} for v in e.emissions],
            })
        return rows

    data = {
        "balance": _serialize(emissions_set),
        "total_w": _serialize(emissions_set_w),
        "total_wo": _serialize(emissions_set_wo),
        "inventory": inventory.to_dict() if inventory is not None else [],
        "inventory_schema": INVENTORY_SCHEMA_VERSION,
    }

    from datetime import timedelta

    update_fields = ["last_cached_at", "cached_results_by_activity_by_gas"]
    now = timezone.now()
    module.last_cached_at = now
    module.cached_results_by_activity_by_gas = data
    if module.last_modified is None:
        module.last_modified = now - timedelta(seconds=1)
        update_fields.append("last_modified")
    if hasattr(module, "skip_history_when_saving"):
        module.skip_history_when_saving = True

    if batch is not None:
        batch.register(module, update_fields)
        return

    module.save(update_fields=update_fields)
