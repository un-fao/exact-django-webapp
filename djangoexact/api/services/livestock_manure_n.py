"""Livestock co-digestate and co-bedding N inputs and the managed manure N indicator, IPCC 2019 Vol. 4 Ch. 10.

The math lives in math_model/no_time_dependency_final/manure_nitrogen.py; this module maps the Livestock model onto it.
"""

from collections.abc import Mapping

import ipcc.models as ipcc
from math_model.no_time_dependency_final.manure_nitrogen import BEDDING_SYSTEMS, DIGESTER, effective_system_shares, share_of

PRP = "Pasture/Range/Paddock"
SCENARIOS = ("start", "w", "wo")
MANAGED_MANURE_N_AGGREGATE = "managed_manure_n"


def _system_names(awms) -> list:
    """Names aligned with the calculator's AWMS percentages: a queryset of systems, or the single complementary row."""
    if isinstance(awms, ipcc.LivestockAWMS):
        return [awms.manure_management_type.name_en]
    return list(awms.values_list("manure_management_type__name_en", flat=True))


def math_inputs(calculator, module, scenario: str) -> dict:
    """Extra MathLivestock inputs for the start -> scenario run, after LivestockCalculator.get_defaults()."""
    return {
        "manure_system_names_start": _system_names(calculator.animal_waste_management_systems_start),
        "manure_system_names_end": _system_names(getattr(calculator, f"animal_waste_management_systems_{scenario}")),
        "codigestate_n_start": module.co_digestate_n_start,
        "codigestate_n_end": getattr(module, f"co_digestate_n_{scenario}"),
        "bedding_n_start": module.co_bedding_n_start,
        "bedding_n_end": getattr(module, f"co_bedding_n_{scenario}"),
    }


def scenario_shares(values: Mapping, scenario: str, ipcc_region) -> dict | None:
    """Fraction of excreted N per managed system for one scenario, as the calculator applies it; None if not yet known."""
    category = values.get("livestock_category_type")
    production = values.get(f"livestock_production_type_{scenario}")
    if not (category and production and ipcc_region):
        return None

    rows = ipcc.LivestockAWMS.objects.filter(livestock_category_type=category, livestock_production_type=production, ipcc_region=ipcc_region)
    percentages = {name: value or 0 for name, value in rows.values_list("manure_management_type__name_en", "value")}
    prp_default = percentages.pop(PRP, 0)

    complementary = values.get(f"complementary_manure_management_type_{scenario}")
    if complementary:
        # A single system takes the whole non-PRP share whatever its table value (gas_head_calculation).
        percentages = {complementary.name_en: 0}

    prp_t2 = values.get(f"prp_percentage_t2_{scenario}")
    shares = effective_system_shares(list(percentages.values()), prp_default, prp_t2 * 100 if prp_t2 is not None else None)
    return dict(zip(percentages, shares))


def input_errors(values: Mapping, ipcc_region) -> dict:
    """Co-digestate needs an anaerobic digester share and co-bedding a solid storage or deep bedding share."""
    errors = {}
    for scenario in SCENARIOS:
        cdg = values.get(f"co_digestate_n_{scenario}")
        bedding = values.get(f"co_bedding_n_{scenario}")
        if not (cdg or bedding):
            continue
        shares = scenario_shares(values, scenario, ipcc_region)
        if shares is None:
            continue
        if cdg and not shares.get(DIGESTER):
            errors[f"co_digestate_n_{scenario}"] = "Co-digestate N needs a share of manure managed in an anaerobic digester."
        if bedding and not share_of(list(shares), list(shares.values()), BEDDING_SYSTEMS):
            errors[f"co_bedding_n_{scenario}"] = "Co-bedding N needs a share of manure in solid storage or deep bedding."
    return errors


def applicability(module) -> dict:
    """Per scenario, whether the co-digestate and co-bedding inputs apply (read serializer flags for the frontend)."""
    values = {field.name: getattr(module, field.name) for field in module._meta.fields}
    ipcc_region = module.activity.project.country.ipcc_region if module.activity.project.country else None
    flags = {}
    for scenario in SCENARIOS:
        shares = scenario_shares(values, scenario, ipcc_region) or {}
        flags[f"co_digestate_applicable_{scenario}"] = bool(shares.get(DIGESTER))
        flags[f"co_bedding_applicable_{scenario}"] = share_of(list(shares), list(shares.values()), BEDDING_SYSTEMS) > 0
    return flags


def managed_manure_n(module) -> dict:
    """Managed manure N available for other uses (IPCC 2019 Eq. 10.34), kg N/yr: at start and at full w / wo implementation."""
    # calculators imports this module for math_inputs.
    from api.calculators import LivestockCalculator

    calculator = LivestockCalculator(module)
    calculator.calculate()
    math_w, math_wo = calculator.math_w, calculator.math_wo
    first = math_w or math_wo
    return {
        "unit": "kg N/yr",
        "start": first.managed_manure_n_available_start if first else None,
        "w": math_w.managed_manure_n_available_end if math_w else None,
        "wo": math_wo.managed_manure_n_available_end if math_wo else None,
    }
