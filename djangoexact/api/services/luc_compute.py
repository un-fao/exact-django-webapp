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

    For each base field name in ``start_values``, write to the model's
    ``_start`` / ``_w`` / ``_wo`` triplet when those attributes exist
    (the LandModule convention), otherwise write to the bare attribute
    (some FK fields like ``ForestManagement.forest_type`` are plain
    scalars without a triplet). ``_w`` falls back to the start value
    when ``w_values`` doesn't have an entry for the same key
    (different-class case).
    """
    from api import models as api_models

    model_cls = getattr(api_models, sibling_class)
    instance = model_cls(activity=activity)

    # The LUC calculator gates on module.status == READY for every sibling
    # (api/calculators.py:1117 in OtherLandUseCalculator, :823 in
    # DeforestationCalculator). Module.status is nullable with no default,
    # so a fresh instance has status=None and the calculator raises
    # "All modules associated with the land use change must be ready" or
    # "Forest module is not complete". Mirror the factories.py convention
    # and set it explicitly.
    instance.status = api_models.StatusType.objects.get(name_en="READY")

    field_names = {f.name for f in model_cls._meta.get_fields()}

    for field_name, start_val in start_values.items():
        sided_start = f"{field_name}_start"
        if sided_start in field_names:
            setattr(instance, sided_start, start_val)
            setattr(instance, f"{field_name}_w", w_values.get(field_name, start_val))
            setattr(instance, f"{field_name}_wo", start_val)
        else:
            # Non-sided FK field (e.g. ForestManagement.forest_type).
            # Use the start value; same-class transitions can drift via w_values
            # only when the field actually varies between sides, but plain
            # scalar FK fields on a single sibling can hold only one value.
            setattr(instance, field_name, start_val)
    # area is required on every LandModule but isn't part of the preset.
    if hasattr(instance, "area"):
        instance.area = 1
    instance.save()
    return instance


def _pick_country_for_slice(api_models, ipcc_models, start_class, start_values, climate):
    """Pick a Country whose region satisfies the calculator's region-restricted
    reference-data lookups for this slice.

    The DeforestationCalculator path (start_class=ForestManagement) queries
    ``ForestManagementAGB`` by ``(land_use_type, climate, region, forest_type)``
    and raises when no row matches. ``Country.objects.first()`` returns an
    Oceania country, but in the review DB AGB coverage for ``Coniferous
    Forest`` in ``Boreal`` climate only exists in Asian regions, Europe,
    and North America. Pick a country from one of those regions so the
    lookup hits a row instead of raising.

    For non-ForestManagement starts the OtherLandUseCalculator path is used,
    which does not need a region-restricted AGB row, so the same fallback
    (``Country.objects.first()``) is fine.
    """
    if start_class != "ForestManagement":
        return api_models.Country.objects.first()
    forest_lut = start_values.get("land_use_type")
    if forest_lut is None:
        return api_models.Country.objects.first()
    covered_region_ids = list(
        ipcc_models.ForestManagementAGB.objects
        .filter(land_use_type=forest_lut, climate=climate)
        .values_list("region_id", flat=True).distinct()
    )
    return (
        api_models.Country.objects.filter(region_id__in=covered_region_ids).first()
        or api_models.Country.objects.first()
    )


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
    # The LUC calculator dereferences project.climate.name, project.moisture,
    # and project.soil_type without None-guards (api/calculators.py SOC
    # lookups). Pick a climate/moisture/soil_type triple that has a
    # SoilOrganicCarbon record so those lookups succeed downstream.
    soc = ipcc_models.SoilOrganicCarbon.objects.filter(value__isnull=False).first()
    if soc is None:
        raise RuntimeError("No SoilOrganicCarbon reference data; cannot build LUC fixture")
    climate, moisture, soil_type = soc.climate, soc.moisture, soc.soil_type
    country = _pick_country_for_slice(api_models, ipcc_models, start_class, start_values, climate)
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


def _serialize_result(luc, start_values, w_values, balance, from_value, to_value) -> dict:
    """Reduce one calculator result to a dict for DataManager / ChangeRecord.

    Shape matches the per-row dicts that the non-LUC PermutationComputer
    emits, so the same importer
    (api.services.minitool_changes_import.import_changes_from_data) can
    write ChangeRecord rows without a LUC-specific branch. The
    ``module_type_start`` / ``module_type_w`` pair is what
    ``_iter_column_pairs`` reads to produce a ``field="module_type"`` row
    carrying the preset-identifier from/to values that the scenario builder
    dropdown emits and queries against.
    """
    def _str(v):
        return None if v is None else str(v)

    project = luc.activity.project
    region_obj = project.country.region if project.country else None
    return {
        "region": _str(region_obj) or "",
        "climate": _str(project.climate) or "",
        "moisture": _str(project.moisture) or "",
        "soil_type": _str(project.soil_type) or "",
        "total": balance,
        "module_type_start": from_value,
        "module_type_w": to_value,
        "from_value": from_value,
        "to_value": to_value,
        "start_class": luc.module_type_start.class_name,
        "w_class": luc.module_type_w.class_name,
        "start_values": {k: _str(v) for k, v in start_values.items()},
        "w_values": {k: _str(v) for k, v in w_values.items()},
    }


def _compute_luc_slice(
    from_value: str,
    to_value: str,
    *,
    save_results: bool = True,
    progress_callback=None,
    max_rows: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Iterate concrete LUC combinations and run LandUseChangeCalculator.

    Each combination builds saved fixtures inside ``transaction.atomic``
    and rolls back after the calculator returns. Errors are captured per
    combination so a single bad combo doesn't abort the slice.

    ``max_rows`` caps the number of concrete combos actually run (i.e.
    ``combos = combos[:max_rows]`` before the loop), not the number of
    rows in the resulting ``data`` list. A combo can still yield zero
    rows by erroring out, so ``len(data) <= max_rows`` is the only
    guarantee.
    """
    from django.db import transaction
    from admin_scripts.luc_permutations import parse_identifier
    from api.calculators import CalculatorFactory

    start_spec = parse_identifier(from_value)
    w_spec = parse_identifier(to_value)

    data: list[dict] = []
    errors: list[dict] = []

    combos = list(iterate_concrete_combos(start_spec, w_spec))
    if max_rows is not None:
        combos = combos[:max_rows]
    total = len(combos)
    for i, (start_values, w_values) in enumerate(combos):
        with transaction.atomic():
            try:
                luc = build_luc_fixture(
                    start_class=start_spec[0], start_values=start_values,
                    w_class=w_spec[0], w_values=w_values,
                )
                # Mirror the non-LUC PermutationComputer: take the scalar
                # balance from breakdown(TOTAL)[2] so ChangeRecord.total is
                # a float, not a Python object the scenario UI can't aggregate.
                balance = CalculatorFactory().calculate_result(luc)[0][2]
                data.append(_serialize_result(
                    luc, start_values, w_values, balance,
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
        # Persist to ChangeRecord too. Without this the scenario-builder /
        # test-modules detail view (which queries ChangeRecord via
        # stats_for_scenario) shows count=0 for every "Completed" LUC job
        # because the GCS CSV upload is the only thing that ran.
        from api.services.minitool_changes_import import import_changes_from_data
        import_changes_from_data(data, "LandUseChange")

    logger.info(
        "LUC slice %s -> %s: %d data, %d errors (from %d combos)",
        from_value, to_value, len(data), len(errors), total,
    )
    return data, errors
