"""Reservoir (flooded land) as the final land use of a land use change, IPCC 2019 Vol. 4 Ch. 7.

The LUC calculators (DeforestationCalculator, OtherLandUseCalculator) already remove the pre-flood biomass, as for
any conversion. FloodedLandCalculator delegates here to add, on the converted area of each scenario that ends flooded:
- the loss of the pre-flood soil carbon (final FLU 0, as NEXT does), through the NotCultivatedLand soil path that
  OtherLandCalculator uses, with no biomass growth after flooding;
- reservoir CH4 and CO2 per yearly flooded cohort (math_model.reservoirs.FloodedLandConversion).
"""

from math_model.no_time_dependency_final.ghg_emissions_classes import Result as MathResult
from math_model.no_time_dependency_final.not_cultivated_land import NotCultivatedLand
from math_model.no_time_dependency_final.reservoirs import FloodedLandConversion, trophic_alpha

import ipcc.models as ipcc
from api.services import reservoirs

FLOODED_FLU = 0.0
SCENARIOS = ("w", "wo")


def trophic_state(module, scenario: str):
    trophic_type = getattr(module, f"trophic_type_{scenario}")
    return ipcc.TrophicStateFactor.objects.filter(trophic_type=trophic_type).first() if trophic_type else None


def class_alpha(module, scenario: str) -> float:
    return reservoirs.class_alpha(trophic_state(module, scenario))


def alpha(module, scenario: str) -> float:
    return trophic_alpha(getattr(module, f"alpha_t2_{scenario}"), getattr(module, f"mean_annual_t2_{scenario}"), class_alpha(module, scenario))


def _soil(calc, scenario: str) -> NotCultivatedLand:
    soil = NotCultivatedLand(
        hectares_start=0,
        hectares_end=calc.area,
        implementation_time=calc.activity.implementation_years,
        capitalization_time=calc.activity.capitalization_years,
        rate_type=calc.change_rate.name,
        delay=calc.activity.delay,
        nitrous_constant=calc.project.gwp.n2o,
        ef_nitrous_som=calc.som.value,
        soc_start_default=calc.soc_start.value,
        soc_end_default=getattr(calc, f"soc_{scenario}").value,
        soc_start_tier_2=calc.soc_t2_start,
        soc_end_tier_2=getattr(calc, f"soc_t2_{scenario}"),
        calculate_soc_som=getattr(calc, f"calculate_soc_som_{scenario}"),
        fmg_start_default=calc.fmg_start.value,
        fmg_end_default=getattr(calc, f"fmg_{scenario}").value,
        fmg_start_tier_2=calc.module_start.fmg_t2_start,
        flu_start_default=calc.flu_start.value,
        flu_end_default=FLOODED_FLU,
        flu_start_tier_2=calc.module_start.flu_t2_start,
        fi_start_default=calc.fi_start.value,
        fi_end_default=getattr(calc, f"fi_{scenario}").value,
        fi_start_tier_2=calc.module_start.fi_t2_start,
        calculate_biomass=False,
    )
    soil.calculate_emissions()
    return soil


def _reservoir(calc, ef: ipcc.ReservoirEmissionFactor, scenario: str) -> FloodedLandConversion:
    module = calc.module
    le_20 = getattr(module, f"ch4_ef_le_20_t2_{scenario}")
    gt_20 = getattr(module, f"ch4_ef_gt_20_t2_{scenario}")
    reservoir = FloodedLandConversion(
        area=calc.area,
        alpha=alpha(module, scenario),
        ch4_ef_age_le_20=ef.ch4_age_le_20 if le_20 is None else le_20,
        ch4_ef_age_gt_20=ef.ch4_age_gt_20 if gt_20 is None else gt_20,
        co2_c_ef_age_le_20=ef.co2_c_age_le_20,
        rd=reservoirs.rd(module),
        methane_constant=calc.project.gwp.ch4,
        implementation_time=calc.activity.implementation_years,
        capitalization_time=calc.activity.capitalization_years,
        rate_type=calc.change_rate.name,
        delay=calc.activity.delay,
    )
    reservoir.calculate_emissions()
    return reservoir


def calculate(calc) -> tuple:
    calc.get_defaults()
    module = calc.module
    ef = reservoirs.reservoir_emission_factor(calc.climate, calc.moisture)
    activity = calc.activity

    results = {}
    for scenario, ends_flooded in zip(SCENARIOS, (module.is_with(), module.is_without())):
        if not ends_flooded:
            results[scenario] = MathResult(activity.implementation_years, activity.capitalization_years, activity.delay)
            continue
        soil = _soil(calc, scenario)
        # The soil path carries the start-year inventory (BaseCalculator.inventory reads math_w / math_wo).
        setattr(calc, f"math_{scenario}", soil)
        results[scenario] = soil.result + _reservoir(calc, ef, scenario).result
    return results["w"], results["wo"]
