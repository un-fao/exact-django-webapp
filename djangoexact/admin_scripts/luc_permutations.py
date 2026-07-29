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
    """Look up a row by ``name_en`` then ``name``. Raises ValueError if neither matches.

    A ``FieldError`` on ``name_en`` means the model doesn't carry that
    translated-name field; fall through to ``name``. Any other exception
    (``MultipleObjectsReturned``, DB issues, etc.) propagates so callers
    see real failures instead of a misleading "no row" error.
    """
    from django.core.exceptions import FieldError

    for field_name in ("name_en", "name"):
        try:
            return model_cls.objects.get(**{field_name: name})
        except model_cls.DoesNotExist:
            continue
        except FieldError:
            continue
    raise ValueError(
        f"{model_cls.__name__}: no row with name_en='{name}' or name='{name}'"
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
        # Scalar Fixed values bypass FK lookup. Today only ``bool`` lands
        # here (``is_biomass_burned``); ints/floats from MODULE_CONFIGS
        # entries that hold plain Python lists (e.g. ``fire_periodicity_*``,
        # ``area_m2_*``) would otherwise fall through to ``source.model``
        # and crash, so treat any non-queryset source as already a value list.
        if isinstance(selector.name, bool):
            return [selector.name]
        if source is None or not hasattr(source, "model"):
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


def list_preset_templates() -> list[tuple[str, int]]:
    """Return [(class_name, template_idx), ...] for every entry in LUC_PRESETS,
    ordered by class-name insertion order then template index.
    """
    out: list[tuple[str, int]] = []
    for class_name, templates in LUC_PRESETS.items():
        for idx in range(len(templates)):
            out.append((class_name, idx))
    return out


def format_identifier(class_name: str, template_idx: int) -> str:
    """Encode a (class_name, template_idx) tuple as a from/to_value string."""
    return f"{class_name}#{template_idx}"


def parse_identifier(value: str) -> tuple[str, int]:
    """Inverse of :func:`format_identifier`. Raises ``ValueError`` on bad input."""
    if "#" not in value:
        raise ValueError(f"LUC identifier missing '#': {value!r}")
    class_name, _, idx_str = value.partition("#")
    try:
        return class_name, int(idx_str)
    except ValueError as exc:
        raise ValueError(f"LUC identifier has non-integer index: {value!r}") from exc


def plan_luc_pairs() -> list[dict]:
    """Return one planner entry per directed (start_template, w_template) pair.

    Each entry slots into ``plan_module_tests``'s ``planned`` list with the
    same shape used for non-LUC modules:

        {"module_type": "LandUseChange",
         "field_name": "module_type",
         "from_value": "<ClassName>#<idx>",
         "to_value":   "<ClassName>#<idx>"}
    """
    templates = list_preset_templates()
    entries: list[dict] = []
    for start_class, start_idx in templates:
        from_value = format_identifier(start_class, start_idx)
        for w_class, w_idx in templates:
            entries.append({
                "module_type": "LandUseChange",
                "field_name": "module_type",
                "from_value": from_value,
                "to_value": format_identifier(w_class, w_idx),
            })
    return entries

