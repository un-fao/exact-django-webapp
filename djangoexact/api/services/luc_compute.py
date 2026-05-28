"""Saved-fixtures permutation runner for LandUseChange.

Unlike per-module slices, LUC needs a saved ``Activity`` with attached
sibling land modules so ``LandUseChange.get_modules()`` resolves. This
module wraps that work in ``transaction.atomic`` + ``set_rollback(True)``
so each combination's fixtures are rolled back; only the data dicts
collected in memory escape the transaction.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def iterate_concrete_combos(
    start_spec: tuple[str, int],
    w_spec: tuple[str, int],
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Cross-product of expand_preset(start, START) x expand_preset(w, W).

    Yields ``(start_values, w_values)`` field dicts. ``w_values`` already
    has any ``_destination_overrides`` applied.
    """
    from admin_scripts.luc_permutations import Side, expand_preset

    start_combos = expand_preset(start_spec[0], start_spec[1], Side.START)
    w_combos = expand_preset(w_spec[0], w_spec[1], Side.W)
    for s in start_combos:
        for w in w_combos:
            yield s, w


def _save_sibling(activity, sibling_class, start_values, w_values):
    """Save one land-module sibling on ``activity`` with start/w/wo fields.

    Each base field in ``start_values`` is written to the model's
    ``_start`` attribute. The corresponding ``_w`` attribute uses
    ``w_values[field]`` when the key exists (same-class case) or the
    start value as filler (different-class case). ``_wo`` mirrors start
    (matches LandUseChangeProcessor's existing convention).
    """
    from api import models as api_models

    model_cls = getattr(api_models, sibling_class)
    instance = model_cls(activity=activity)
    for field_name, start_val in start_values.items():
        setattr(instance, f"{field_name}_start", start_val)
        setattr(instance, f"{field_name}_w", w_values.get(field_name, start_val))
        setattr(instance, f"{field_name}_wo", start_val)
    # area is required on every LandModule but isn't part of the preset.
    if hasattr(instance, "area"):
        instance.area = 1
    instance.save()
    return instance


def build_luc_fixture(start_class, start_values, w_class, w_values):
    """Build & save Project, Activity, sibling(s), and a LandUseChange.

    Caller MUST run this inside a ``transaction.atomic()`` block and call
    ``transaction.set_rollback(True)`` after running the calculator so
    nothing persists to the database.
    """
    from api import models as api_models
    import api.tests.factories as factories
    from ipcc import models as ipcc_models

    owner = factories.UserFactory.create()
    country = api_models.Country.objects.first()
    # The LUC calculator dereferences project.climate.name, project.moisture,
    # and project.soil_type without None-guards (api/calculators.py SOC
    # lookups). Pick a climate/moisture/soil_type triple that has a
    # SoilOrganicCarbon record so those lookups succeed downstream.
    soc = ipcc_models.SoilOrganicCarbon.objects.filter(value__isnull=False).first()
    if soc is None:
        raise RuntimeError("No SoilOrganicCarbon reference data; cannot build LUC fixture")
    climate, moisture, soil_type = soc.climate, soc.moisture, soc.soil_type
    project = factories.ProjectFactory.create(
        owner=owner,
        country=country,
        climate=climate,
        moisture=moisture,
        soil_type=soil_type,
    )
    activity = factories.ActivityFactory.create(project=project)

    if start_class == w_class:
        _save_sibling(activity, start_class, start_values, w_values)
    else:
        # Different classes: each side gets its own sibling. The w fields
        # on the start sibling and the start fields on the w sibling get
        # the same-side preset values (they aren't read by the calculator
        # but the model requires non-null in some cases).
        _save_sibling(activity, start_class, start_values, start_values)
        _save_sibling(activity, w_class, w_values, w_values)

    module_type_start = api_models.ModuleType.objects.get(class_name=start_class)
    module_type_w = api_models.ModuleType.objects.get(class_name=w_class)

    luc = api_models.LandUseChange.objects.create(
        activity=activity,
        module_type_start=module_type_start,
        module_type_w=module_type_w,
        module_type_wo=module_type_start,
        area=1,
        is_fire_used_start=False,
        is_fire_used_w=False,
        is_fire_used_wo=False,
    )
    return luc


def _serialize_result(luc, start_values, w_values, result, from_value, to_value) -> dict:
    """Reduce one calculator result to a dict for DataManager / ChangeRecord."""
    def _str(v):
        return None if v is None else str(v)

    return {
        "from_value": from_value,
        "to_value": to_value,
        "start_class": luc.module_type_start.class_name,
        "w_class": luc.module_type_w.class_name,
        "start_values": {k: _str(v) for k, v in start_values.items()},
        "w_values": {k: _str(v) for k, v in w_values.items()},
        "result": result,
    }


def _compute_luc_slice(
    from_value: str,
    to_value: str,
    *,
    save_results: bool = True,
    progress_callback=None,
) -> tuple[list[dict], list[dict]]:
    """Iterate concrete LUC combinations and run LandUseChangeCalculator.

    Each combination builds saved fixtures inside ``transaction.atomic``
    and rolls back after the calculator returns. Errors are captured per
    combination so a single bad combo doesn't abort the slice.
    """
    from django.db import transaction
    from admin_scripts.luc_permutations import parse_identifier
    from api.calculators import LandUseChangeCalculator

    start_spec = parse_identifier(from_value)
    w_spec = parse_identifier(to_value)

    data: list[dict] = []
    errors: list[dict] = []

    combos = list(iterate_concrete_combos(start_spec, w_spec))
    total = len(combos)
    for i, (start_values, w_values) in enumerate(combos):
        with transaction.atomic():
            try:
                luc = build_luc_fixture(
                    start_class=start_spec[0], start_values=start_values,
                    w_class=w_spec[0], w_values=w_values,
                )
                result = LandUseChangeCalculator(luc).calculate()
                data.append(_serialize_result(
                    luc, start_values, w_values, result,
                    from_value, to_value,
                ))
            except Exception as exc:
                errors.append({
                    "from_value": from_value,
                    "to_value": to_value,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                })
            finally:
                transaction.set_rollback(True)
        if progress_callback and total:
            progress_callback(int(100 * (i + 1) / total))

    if save_results and data:
        from api.minitool import DataManager
        DataManager().save_data(data, errors, "LandUseChange")

    logger.info(
        "LUC slice %s -> %s: %d data, %d errors (from %d combos)",
        from_value, to_value, len(data), len(errors), total,
    )
    return data, errors
