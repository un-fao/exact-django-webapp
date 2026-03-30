"""Cache adapter for the report computation pipeline.

Provides the bridge between the module-level cached results
(CachedResultMixin.cached_results_by_activity_by_gas) and the
report computation pipeline (BaseModuleReport.emissions_set*).

The cached and calculated paths are entirely separate:
  - load_emissions_from_cache()     → cached path
  - BaseModuleReport._init_from_calculator() → calculated path (unchanged)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .data_types import InventoryItem


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
            ipcc_category=activity,
            gas_type=gas_type,
            value=value,
        ))
    return items
