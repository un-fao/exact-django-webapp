"""Other constructed waterbodies (ponds, canals), IPCC 2019 Vol. 4 Ch. 7 Eq. 7.11 and Table 7.11."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.waterbodies import CoastalWaterbodies  # noqa: E402

EF_FRESHWATER_POND = 183.0
GWP_CH4 = 28


def pond(**kw):
    base = dict(
        implementation_time=5,
        capitalization_time=5,
        rate_type="linear",
        delay=0,
        area_start=10,
        area_end=10,
        trophic_state_default=3.0,
        methane_emission_factor_default=EF_FRESHWATER_POND,
        trophic_state_tier_2_start=None,
        trophic_state_tier_2_end=None,
        methane_emission_factor_start_tier_2=None,
        methane_emission_factor_end_tier_2=None,
        methane_constant=GWP_CH4,
        chlo_A_start=None,
        chlo_A_end=None,
    )
    base.update(kw)
    p = CoastalWaterbodies(**base)
    p.calculate_emissions()
    return p


def test_chlorophyll_a_drives_alpha():
    # 10 ha x (0.26 x 40 ug/L = 10.4) x 183 kg CH4/ha/yr / 1000 x 28 = 532.896 t CO2e/yr
    p = pond(chlo_A_start=40, chlo_A_end=40)
    assert p.emissions_yearly == pytest.approx([532.896] * 10)


def test_tier_2_alpha_wins_over_chlorophyll_a_and_default_is_last():
    assert pond(chlo_A_start=40, chlo_A_end=40, trophic_state_tier_2_start=1, trophic_state_tier_2_end=1).emissions_yearly[0] == pytest.approx(10 * 183 / 1000 * 28)
    assert pond().emissions_yearly[0] == pytest.approx(10 * 3 * 183 / 1000 * 28)
