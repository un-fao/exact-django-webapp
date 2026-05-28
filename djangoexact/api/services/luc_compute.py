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

    project = api_models.Project.objects.create()
    activity = api_models.Activity.objects.create(project=project)

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
