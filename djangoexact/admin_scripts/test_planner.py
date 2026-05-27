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
