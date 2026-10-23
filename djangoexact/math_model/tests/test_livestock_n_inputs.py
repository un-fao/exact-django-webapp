"""Co-digestate and co-bedding N in livestock manure management, IPCC 2019 Refinement Vol. 4 Ch. 10.

DB-free: python -m pytest djangoexact/math_model/tests/test_livestock_n_inputs.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.general_functions import compute_yearly_or_half_year_cumulative  # noqa: E402
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes  # noqa: E402
from math_model.no_time_dependency_final.livestock import Livestock  # noqa: E402

GWP_N2O = 273
EF4, EF5 = 0.01, 0.011
NAMES = ["Digester", "Lagoon", "Solid Storage"]
SHARES = [30, 10, 20]  # % of N excreted; PRP takes the other 40
EF3 = [0.0006, 0.0, 0.0075]  # Table 10.21
FRAC_GAS = [0.275, 0.35, 0.2325]  # Table 10.22
FRAC_LEACH = [0.0, 0.0, 0.015]
HEADS, TAM, NER = 100, 500, 0.5
NEX = TAM / 1000 * NER * 365  # 91.25 kg N/head/yr
TO_T_CO2E = 1 / 1000 * 44 / 28 * GWP_N2O


def _livestock(**overrides):
    kwargs = dict(
        implementation_time=5,
        capitalization_time=5,
        rate_type="linear",
        delay=0,
        methane_constant=27,
        head_number_start=HEADS,
        head_number_end=HEADS,
        specific_factor_default_start=60,
        specific_factor_default_end=60,
        ef_prp_methane_start=0.6,
        ef_prp_methane_end=0.6,
        percentage_prp_default_start=40,
        percentage_prp_default_end=40,
        ef_system_methane_start=[3.2, 107.07, 3.2],
        ef_system_methane_end=[3.2, 107.07, 3.2],
        ch4_system_default_start=None,
        ch4_system_default_end=None,
        percentage_system_default_start=SHARES,
        percentage_system_default_end=SHARES,
        tam_start=TAM,
        tam_end=TAM,
        vser_start=5,
        vser_end=5,
        ef_prp_nitrous_direct_start=0.002,
        ef_prp_nitrous_direct_end=0.002,
        ef_system_nitrous_direct_start=EF3,
        ef_system_nitrous_direct_end=EF3,
        n2o_system_direct_default_start=None,
        n2o_system_direct_default_end=None,
        ner_start=NER,
        ner_end=NER,
        ef_prp_nitrous_indirect_volatization_start=0.21,
        ef_prp_nitrous_indirect_volatization_end=0.21,
        ef_system_nitrous_indirect_volatization_start=FRAC_GAS,
        ef_system_nitrous_indirect_volatization_end=FRAC_GAS,
        n20_system_indirect_volatization_default_start=None,
        n20_system_indirect_volatization_default_end=None,
        ef_prp_nitrous_indirect_leaching_start=0.0,
        ef_prp_nitrous_indirect_leaching_end=0.0,
        ef_system_nitrous_indirect_leaching_start=FRAC_LEACH,
        ef_system_nitrous_indirect_leaching_end=FRAC_LEACH,
        n20_system_indirect_leaching_default_start=None,
        n20_system_indirect_leaching_default_end=None,
        nitrous_constant=GWP_N2O,
        volatilization_multiplier=EF4,
        leaching_multiplier=EF5,
        manure_system_names_start=NAMES,
        manure_system_names_end=NAMES,
    )
    livestock = Livestock(**{**kwargs, **overrides})
    livestock.calculate_emissions()
    return livestock


def _yearly(livestock, activity):
    (emission_set,) = [s for s in livestock.result.yearly_emissions_by_sector_by_gas if s.activity == activity]
    return [e.value for e in emission_set.emissions]


def _ramp(start, end):
    return compute_yearly_or_half_year_cumulative(start, end, 5, 5, "linear")


def _all_yearly(livestock):
    return [(s.activity, [e.value for e in s.emissions]) for s in livestock.result.yearly_emissions_by_sector_by_gas]


def test_codigestate_adds_digester_n2o_per_eq_10_25_to_10_29():
    base = _livestock()
    with_cdg = _livestock(codigestate_n_end=1000)

    # Eq. 10.25: 1000 kg N x EF3(digester) 0.0006 = 0.6 kg N2O-N/yr at full implementation.
    direct = 1000 * 0.0006 * TO_T_CO2E
    # Eq. 10.26 + 10.28: 1000 x FracGas 0.275 x EF4 0.01 = 2.75 kg N2O-N/yr.
    volatilised = 1000 * 0.275 * EF4 * TO_T_CO2E
    cases = [
        (ActivityTypes.NITROUS_MANURE_MANAGEMENT_SYSTEM, direct),
        (ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_VOLATILIZATION_SYSTEM, volatilised),
        # Eq. 10.27 + 10.29: FracLeach for digesters is 0 in Table 10.22.
        (ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM, 0.0),
    ]
    for activity, annual_at_end in cases:
        delta = [a - b for a, b in zip(_yearly(with_cdg, activity), _yearly(base, activity))]
        assert delta == pytest.approx(_ramp(0, annual_at_end), abs=1e-12), activity

    assert _yearly(with_cdg, ActivityTypes.NITROUS_MANURE_MANAGEMENT_PRP) == _yearly(base, ActivityTypes.NITROUS_MANURE_MANAGEMENT_PRP)


def test_codigestate_leaching_uses_ef5():
    leaching = [0.02, 0.0, 0.015]  # hypothetical leaky digester, Table 10.22 has 0
    base = _livestock(ef_system_nitrous_indirect_leaching_start=leaching, ef_system_nitrous_indirect_leaching_end=leaching)
    with_cdg = _livestock(codigestate_n_start=500, codigestate_n_end=500, ef_system_nitrous_indirect_leaching_start=leaching, ef_system_nitrous_indirect_leaching_end=leaching)
    activity = ActivityTypes.NITROUS_MANURE_MANAGEMENT_INDIRECT_LEACHING_SYSTEM
    delta = [a - b for a, b in zip(_yearly(with_cdg, activity), _yearly(base, activity))]
    annual = 500 * 0.02 * EF5 * TO_T_CO2E
    assert delta == pytest.approx(_ramp(annual, annual), abs=1e-12)


def test_bedding_adds_no_n2o():
    assert _all_yearly(_livestock(bedding_n_start=7, bedding_n_end=7)) == _all_yearly(_livestock())


def test_managed_manure_n_available_eq_10_34():
    def frac_loss(i):
        return FRAC_GAS[i] + FRAC_LEACH[i] + 4 * EF3[i]  # Eq. 10.34a/b, R_N2(N2O) = 3

    managed = sum(HEADS * NEX * share / 100 * (1 - frac_loss(i)) for i, share in enumerate(SHARES))
    assert managed == pytest.approx(3889.805)
    assert _livestock().managed_manure_n_available_end == pytest.approx(managed)

    livestock = _livestock(codigestate_n_end=1000, bedding_n_end=7)
    cdg = 1000 * (1 - frac_loss(0))
    bedding = HEADS * 0.20 * 7  # solid storage share only, no loss on bedding
    assert livestock.managed_manure_n_available_end == pytest.approx(managed + cdg + bedding)
    assert livestock.managed_manure_n_available_start == pytest.approx(managed)


def test_managed_manure_n_follows_tier_2_prp_share():
    # PRP 70% instead of 40%: managed shares scale by 30/60.
    livestock = _livestock(percentage_prp_tier_2_end=70)
    assert livestock.managed_manure_n_available_end == pytest.approx(livestock.managed_manure_n_available_start / 2)


def test_single_complementary_system_takes_the_non_prp_share():
    livestock = _livestock(
        percentage_system_default_end=[5],
        ef_system_nitrous_direct_end=[0.0006],
        ef_system_nitrous_indirect_volatization_end=[0.275],
        ef_system_nitrous_indirect_leaching_end=[0.0],
        ef_system_methane_end=[3.2],
        manure_system_names_end=["Digester"],
        codigestate_n_end=100,
    )
    expected = (HEADS * NEX * 0.60 + 100) * (1 - (0.275 + 4 * 0.0006))
    assert livestock.managed_manure_n_available_end == pytest.approx(expected)


@pytest.mark.parametrize(
    "overrides",
    [
        {"codigestate_n_end": 10, "manure_system_names_end": ["Pit<1Month", "Lagoon", "Solid Storage"]},
        {"codigestate_n_start": 10, "percentage_system_default_start": [0, 40, 20]},
        {"bedding_n_end": 2, "manure_system_names_end": ["Digester", "Lagoon", "Pit<1Month"]},
        {"bedding_n_start": 2, "percentage_system_default_start": [30, 30, 0]},
    ],
)
def test_inputs_rejected_without_the_relevant_system_share(overrides):
    with pytest.raises(ValueError):
        _livestock(**overrides)


def test_null_and_zero_inputs_keep_current_results():
    reference = _all_yearly(_livestock(manure_system_names_start=None, manure_system_names_end=None))
    assert _all_yearly(_livestock()) == reference
    assert _all_yearly(_livestock(codigestate_n_start=0, codigestate_n_end=0, bedding_n_start=0, bedding_n_end=0)) == reference
