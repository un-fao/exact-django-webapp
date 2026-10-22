"""Reservoir (flooded land) waterbodies: IPCC 2019 Vol. 4 Ch. 7 inputs for math_model.reservoirs.

Kept out of calculators.py: WaterbodyCalculator delegates here when the waterbody type is a reservoir.
"""

from math_model.no_time_dependency_final.ghg_emissions_classes import Result as MathResult
from math_model.no_time_dependency_final.reservoirs import LAND_CONVERTED_YEARS, RD_DEFAULT, RESERVOIR_DEFAULT_ALPHA, Reservoir, trophic_alpha

import ipcc.models as ipcc


def reservoir_emission_factor(climate, moisture) -> ipcc.ReservoirEmissionFactor:
    try:
        return ipcc.ReservoirEmissionFactor.objects.get(climate=climate, moisture=moisture)
    except ipcc.ReservoirEmissionFactor.DoesNotExist:
        raise ValueError(f"No IPCC reservoir emission factor for {climate} / {moisture}.")


def class_alpha(trophic_state) -> float:
    """Table 7.11 alpha of the selected trophic class. EX-ACT's "Default" class (alpha 1, for ponds) is not a
    Table 7.11 class, so reservoirs use the oligotrophic value instead, as NEXT does."""
    trophic_type = trophic_state.trophic_type if trophic_state is not None and trophic_state.trophic_type_id else None
    if trophic_type is None or trophic_type.name_en == "Default":
        return RESERVOIR_DEFAULT_ALPHA
    return trophic_state.value


def require_age(module) -> int:
    if module.reservoir_age_start is None:
        raise ValueError("Reservoir age at the start of the project is required.")
    return module.reservoir_age_start


def ch4_ef_at_start(module, ef: ipcc.ReservoirEmissionFactor) -> float:
    """Tier 1 CH4 EF that applies in the first project year, shown as the Tier 2 default."""
    return ef.ch4_age_le_20 if require_age(module) < LAND_CONVERTED_YEARS else ef.ch4_age_gt_20


def rd(module) -> float:
    if not module.downstream_emissions:
        return 0.0
    return RD_DEFAULT if module.rd_t2 is None else module.rd_t2


def _math(calculator, module, ef, scenario: str, area_start: float, area_end: float, alpha_start: float, alpha_end: float) -> Reservoir:
    ch4_t2 = getattr(module, f"ch4_ef_t2_{scenario}")
    activity = calculator.activity
    math = Reservoir(
        area_start=area_start,
        area_end=area_end,
        alpha_start=alpha_start,
        alpha_end=alpha_end,
        age_at_series_start=require_age(module) + activity.delay,
        # A Tier 2 CH4 EF is a single measured value, so it replaces both age classes.
        ch4_ef_age_le_20=ef.ch4_age_le_20 if ch4_t2 is None else ch4_t2,
        ch4_ef_age_gt_20=ef.ch4_age_gt_20 if ch4_t2 is None else ch4_t2,
        co2_c_ef_age_le_20=ef.co2_c_age_le_20,
        rd=rd(module),
        methane_constant=calculator.project.gwp.ch4,
        implementation_time=activity.implementation_years,
        capitalization_time=activity.capitalization_years,
        rate_type=calculator.change_rate.name,
        delay=activity.delay,
    )
    math.calculate_emissions()
    return math


def _alpha(calculator, module, scenario: str) -> float:
    default = class_alpha(getattr(calculator, f"trophic_state_{scenario}"))
    return trophic_alpha(getattr(module, f"alpha_t2_{scenario}"), getattr(module, f"mean_annual_t2_{scenario}"), default)


def calculate(calculator) -> tuple:
    """Same scenario shape as WaterbodyCalculator.calculate: start phases out, w / wo phase in."""
    module = calculator.module
    activity = calculator.activity
    ef = calculator.reservoir_ef
    alpha_start = _alpha(calculator, module, "start")

    calculator.math_start = _math(calculator, module, ef, "start", module.area, 0, alpha_start, 0)
    if module.is_with():
        calculator.math_w = _math(calculator, module, ef, "w", 0, module.area, alpha_start, _alpha(calculator, module, "w"))
    if module.is_without():
        calculator.math_wo = _math(calculator, module, ef, "wo", 0, module.area, alpha_start, _alpha(calculator, module, "wo"))

    empty = MathResult(activity.implementation_years, activity.capitalization_years, activity.delay)
    calculator.results_start = calculator.math_start.result
    calculator.results_w = calculator.math_w.result if calculator.math_w else empty
    calculator.results_wo = calculator.math_wo.result if calculator.math_wo else empty
    return (calculator.results_w + calculator.results_start, calculator.results_wo + calculator.results_start)
