"""Per-field test planner for the Test All Modules admin script.

Pure helpers: turn a list of CatalogModule into the per-field test plan
(plus a list of fields that had to be skipped). _resolve_value_source is
also kept here (moved out of views.py) so both the planner and the views
import the single source of truth.
"""
from __future__ import annotations

from django.apps import apps


# LandUseChange permutations now route through a dedicated saved-fixtures
# runner; the planner emits one entry per (start_template, w_template) pair
# from admin_scripts.luc_permutations.plan_luc_pairs(). See
# api/services/luc_compute.py for the runner.


def _resolve_value_source(value_source: dict, module_type: str = "", field_name: str = "") -> list[str]:
    """Resolve a catalog value_source to a list of string values.

    Prefer the live MODULE_CONFIGS field declaration over the catalog spec.
    The catalog declares ``{kind: queryset, model: LandUseType}`` (unfiltered),
    while MODULE_CONFIGS may apply per-module filters such as
    ``LandUseType.objects.filter(module_types__name="Perennial Cropland")``.
    Picking from the unfiltered global list produces from/to pairs the runner
    later rejects in ``_find_instance_by_name`` ("Could not find 'X' in [...]").
    Reading from MODULE_CONFIGS keeps the planner and runner in lockstep.
    """
    if module_type and field_name:
        try:
            from api.minitool import MODULE_CONFIGS
            fields = MODULE_CONFIGS.get(module_type, {}).get("fields", {})
            for key in (f"{field_name}_start", field_name):
                if key in fields:
                    source = fields[key]
                    try:
                        return [str(item) for item in source]
                    except TypeError:
                        # A single model instance, not iterable. Treat as
                        # a one-value source so the planner skips with a
                        # clear "only 1 distinct value(s) available" reason
                        # rather than blowing up.
                        return [str(source)]
        except Exception:
            pass  # Fall through to catalog-based resolution

    # Catalog fallback (used by tests that pass synthetic value_sources
    # without a matching MODULE_CONFIGS entry).
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
        if module.module_type == "LandUseChange":
            # LUC pairs come from plan_luc_pairs(); the catalog entry's
            # fields are informational only for LUC.
            from admin_scripts.luc_permutations import plan_luc_pairs
            planned.extend(plan_luc_pairs())
            continue

        for field in module.fields:
            values = _ordered_unique(_resolve_value_source(
                field.value_source, module.module_type, field.field_name,
            ))
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
