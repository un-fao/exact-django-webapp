"""Waterbody (flooded land) as the final land use of a land use change, IPCC 2019 Vol. 4 Ch. 7.

The LUC calculators (DeforestationCalculator, OtherLandUseCalculator) remove the pre-flood biomass, as for any
conversion (section 7.3.2.1 sends it to Vol. 4 Ch. 2). In a LUC the soil carbon change is computed by the end
module's own calculator; WaterbodyLandCalculator delegates here instead, and adds, on the converted area of each
scenario that ends flooded:
- reservoir: CH4 and CO2 per yearly flooded cohort, <= 20 / > 20 years factors (Eq. 7.15, 7.10, 7.13);
- pond, canal or ditch: constant CH4 (Eq. 7.12) and no CO2, which IPCC does not estimate for them.

No soil carbon change is booked: the reservoir CO2 factor of Table 7.13 is the decay of the flooded organic matter,
derived from the pre-flood soil carbon stock (Eq. 7.14), so a separate soil loss would count it twice.
"""

from math_model.no_time_dependency_final.ghg_emissions_classes import Result as MathResult
from math_model.no_time_dependency_final.reservoirs import ReservoirConversion, trophic_alpha

import ipcc.models as ipcc
from api.services import reservoirs

SCENARIOS = ("w", "wo")


def trophic_state(module, scenario: str):
    trophic_type = getattr(module, f"trophic_type_{scenario}")
    return ipcc.TrophicStateFactor.objects.filter(trophic_type=trophic_type).first() if trophic_type else None


def class_alpha(module, scenario: str) -> float:
    state = trophic_state(module, scenario)
    if module.is_reservoir():
        return reservoirs.class_alpha(state)
    # Ponds keep EX-ACT's class values, "Default" included, as the Waterbody module does.
    return state.value if state is not None else 1.0


def alpha(module, scenario: str) -> float:
    return trophic_alpha(getattr(module, f"alpha_t2_{scenario}"), getattr(module, f"mean_annual_t2_{scenario}"), class_alpha(module, scenario))


def require_type(module):
    if module.waterbody_type_id is None:
        raise ValueError("Waterbody type is required.")
    return module.waterbody_type


def pond_emission_factor(climate, moisture, waterbody_type) -> float | None:
    ef = ipcc.OtherConstructedWaterbodiesEmissionFactor.objects.filter(climate=climate, moisture=moisture, waterbody_type=waterbody_type).first()
    return ef.value if ef else None


def _conversion(calc, scenario: str) -> ReservoirConversion:
    module = calc.module
    waterbody_type = require_type(module)
    ch4_t2 = getattr(module, f"ch4_ef_t2_{scenario}")
    if module.is_reservoir():
        ef = reservoirs.reservoir_emission_factor(calc.climate, calc.moisture)
        old_t2 = getattr(module, f"ch4_ef_old_t2_{scenario}")
        ch4_young = ef.ch4_age_le_20 if ch4_t2 is None else ch4_t2
        ch4_old = ef.ch4_age_gt_20 if old_t2 is None else old_t2
        co2_c, rd = ef.co2_c_age_le_20, reservoirs.rd(module)
    else:
        ch4_young = pond_emission_factor(calc.climate, calc.moisture, waterbody_type) if ch4_t2 is None else ch4_t2
        if ch4_young is None:
            raise ValueError(f"Methane Emission Factor for {waterbody_type.name} is missing. Please provide a tier 2 value.")
        ch4_old, co2_c, rd = ch4_young, 0.0, 0.0

    conversion = ReservoirConversion(
        area=calc.area,
        alpha=alpha(module, scenario),
        ch4_ef_age_le_20=ch4_young,
        ch4_ef_age_gt_20=ch4_old,
        co2_c_ef_age_le_20=co2_c,
        rd=rd,
        methane_constant=calc.project.gwp.ch4,
        implementation_time=calc.activity.implementation_years,
        capitalization_time=calc.activity.capitalization_years,
        rate_type=calc.change_rate.name,
        delay=calc.activity.delay,
    )
    conversion.calculate_emissions()
    return conversion


def calculate(calc) -> tuple:
    calc.get_defaults()
    module = calc.module
    activity = calc.activity

    results = {}
    for scenario, ends_flooded in zip(SCENARIOS, (module.is_with(), module.is_without())):
        if not ends_flooded:
            results[scenario] = MathResult(activity.implementation_years, activity.capitalization_years, activity.delay)
            continue
        conversion = _conversion(calc, scenario)
        # BaseCalculator.inventory reads math_w / math_wo.
        setattr(calc, f"math_{scenario}", conversion)
        results[scenario] = conversion.result
    return results["w"], results["wo"]
