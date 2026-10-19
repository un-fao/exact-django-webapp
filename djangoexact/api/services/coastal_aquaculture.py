"""Aquaculture ponds in the Coastal Wetland module: reference lookups and inputs for math_model.coastal_aquaculture.

Kept out of calculators.py: CoastalWetlandCalculator only adds the pond result to each scenario.
Fish N2O here is the same emission the Aquaculture module computes from annual production, so the
same fish must not be entered in both modules. Nothing links the two, so this is a UI hint, not a validation.
"""

from dataclasses import dataclass, field

import ipcc.models as ipcc
from api.models import ApplicationParameter, CoastalWetland
from math_model.no_time_dependency_final.coastal_aquaculture import CoastalAquaculturePonds

SCENARIOS = ("start", "w", "wo")
SALINE = ">18"
# IPCC 2019 Table 7.12: saline ponds are > 18 ppt, brackish ponds share the freshwater EF.
SALINE_POND = "Saline Pond"
BRACKISH_POND = "Brackishwater Pond"
# Eq. 7.12: alpha = 1 at Tier 1 when no trophic state is given.
TIER_1_ALPHA = 1.0


def has_ponds(module: CoastalWetland) -> bool:
    return any((getattr(module, f"pond_area_{s}") or 0) > 0 for s in SCENARIOS)


def pond_type_name(salinity_value: str | None) -> str:
    return SALINE_POND if salinity_value == SALINE else BRACKISH_POND


@dataclass
class PondFactors:
    """Tier 1 defaults; None where the reference row is missing (a Tier 2 value is then required)."""

    ch4_ef: float | None
    n2o_ef: float | None
    alpha: dict[str, float | None] = field(default_factory=dict)


def _alpha(trophic_type) -> float | None:
    if trophic_type is None:
        return TIER_1_ALPHA
    factor = ipcc.TrophicStateFactor.objects.filter(trophic_type=trophic_type).first()
    return factor.value if factor else None


def pond_factors(module: CoastalWetland, climate, moisture, salinity_value: str | None) -> PondFactors:
    ef = ipcc.OtherConstructedWaterbodiesEmissionFactor.objects.filter(
        climate=climate, moisture=moisture, waterbody_type__name_en=pond_type_name(salinity_value)
    ).first()
    n2o = ApplicationParameter.objects.filter(name="nitrous_ef_default").first()
    return PondFactors(
        ch4_ef=ef.value if ef else None,
        n2o_ef=n2o.value if n2o else None,
        alpha={s: _alpha(getattr(module, f"pond_trophic_type_{s}")) for s in SCENARIOS},
    )


def _resolve(module: CoastalWetland, t2_field: str, scenario: str, default: float | None, needed: bool, label: str) -> float:
    t2 = getattr(module, f"{t2_field}_{scenario}")
    if t2 is not None:
        return t2
    if default is not None:
        return default
    if needed:
        raise ValueError(f"{label} for aquaculture ponds is missing. Please provide a tier 2 value for the '{scenario}' scenario.")
    return 0.0


def build(calculator, scenario: str) -> CoastalAquaculturePonds | None:
    """Pond CH4 and fish N2O phasing from the start values to the `scenario` ('w' or 'wo') values."""
    module: CoastalWetland = calculator.module
    if not has_ponds(module):
        return None

    factors: PondFactors = calculator.pond_factors
    kw = {}
    for side, s in (("start", "start"), ("end", scenario)):
        area = getattr(module, f"pond_area_{s}") or 0
        fish = getattr(module, f"fish_production_{s}") or 0
        kw[f"pond_area_{side}"] = area
        kw[f"fish_production_{side}"] = fish
        kw[f"ef_ch4_{side}"] = _resolve(module, "pond_ch4_ef_t2", s, factors.ch4_ef, area > 0, "CH4 emission factor")
        kw[f"alpha_{side}"] = _resolve(module, "pond_alpha_t2", s, factors.alpha[s], area > 0, "Trophic state adjustment factor")
        kw[f"ef_n2o_{side}"] = _resolve(module, "fish_n2o_ef_t2", s, factors.n2o_ef, area > 0 and fish > 0, "N2O emission factor")

    activity = calculator.activity
    math = CoastalAquaculturePonds(
        **kw,
        gwp_ch4=calculator.project.gwp.ch4,
        gwp_n2o=calculator.project.gwp.n2o,
        implementation_time=activity.implementation_years,
        capitalization_time=activity.capitalization_years,
        rate_type=calculator.change_rate.name,
        delay=activity.delay,
    )
    math.calculate_emissions()
    return math
