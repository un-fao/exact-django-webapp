"""LUC permutation planning helpers.

The Test All Modules admin script feeds its planner output into the same
``ComputationJob`` dispatcher every other module uses. For LandUseChange
we emit one entry per directed (start_template, w_template) pair drawn
from :data:`admin_scripts.catalog.luc_presets.LUC_PRESETS`.

``expand_preset`` resolves a single template into the concrete list of
field-dict combinations the runner will iterate. ``Fixed`` selectors
yield exactly one combination; ``Cycle`` selectors expand to one
combination per matching ORM row, taking the Cartesian product across
all cycled fields in the template.
"""
from __future__ import annotations

import enum
import itertools
from typing import Any

from admin_scripts.catalog.luc_presets import LUC_PRESETS, Cycle, Fixed


class Side(enum.Enum):
    START = "start"
    W = "w"


def _resolve_fk_by_name(model_cls, name: str):
    """Look up a row by ``name`` or ``name_en``. Raises if not found."""
    for field_name in ("name_en", "name"):
        try:
            return model_cls.objects.get(**{field_name: name})
        except model_cls.DoesNotExist:
            continue
        except Exception:
            # name_en may not be a field on this model; fall through to name.
            continue
    raise ValueError(
        f"{model_cls.__name__}: no row with name='{name}' or name_en='{name}'"
    )


def _field_value_choices(class_name: str, field_name: str, selector: Any) -> list[Any]:
    """Return the list of concrete values for one template entry.

    ``Fixed(value)`` returns ``[value]`` for scalars or ``[<resolved FK>]``
    for FK fields. ``Cycle(filter=...)`` reads the corresponding entry from
    ``MODULE_CONFIGS[class_name]["fields"]`` (the ``_start`` variant if
    present, else the bare field name) and forwards ``filter`` to the
    queryset.
    """
    from api.minitool import MODULE_CONFIGS

    fields = MODULE_CONFIGS.get(class_name, {}).get("fields", {})
    source = fields.get(f"{field_name}_start") or fields.get(field_name)

    if isinstance(selector, Fixed):
        if isinstance(selector.name, bool):
            return [selector.name]
        if source is None:
            return [selector.name]
        # source is a queryset of FK rows; resolve by name.
        model_cls = source.model
        return [_resolve_fk_by_name(model_cls, selector.name)]

    if isinstance(selector, Cycle):
        if source is None:
            raise ValueError(
                f"Cycle() on {class_name}.{field_name} but no MODULE_CONFIGS entry"
            )
        qs = source
        if selector.filter:
            qs = qs.filter(**selector.filter)
        return list(qs)

    raise TypeError(f"Unknown selector type: {selector!r}")


def expand_preset(class_name: str, template_idx: int, side: Side) -> list[dict[str, Any]]:
    """Expand one preset template into the list of concrete field dicts.

    When ``side == Side.W`` and the template has a ``_destination_overrides``
    dict, override entries replace matching field selectors before expansion.
    """
    template = dict(LUC_PRESETS[class_name][template_idx])
    overrides = template.pop("_destination_overrides", {})

    if side is Side.W and overrides:
        for field_name, selector in overrides.items():
            template[field_name] = selector

    if not template:
        return [{}]

    field_names = list(template.keys())
    per_field_values = [
        _field_value_choices(class_name, fname, template[fname])
        for fname in field_names
    ]
    return [
        dict(zip(field_names, combo))
        for combo in itertools.product(*per_field_values)
    ]
