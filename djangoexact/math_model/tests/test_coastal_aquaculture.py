"""Hand-checked coastal aquaculture pond CH4 and fish N2O."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from math_model.no_time_dependency_final.coastal_aquaculture import CoastalAquaculturePonds  # noqa: E402
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes  # noqa: E402

BRACKISH_EF = 183  # IPCC 2019 Table 7.12, freshwater and brackish ponds
N2O_EF = 0.00169  # 2013 Wetlands Supplement Table 4.15
GWP_CH4, GWP_N2O = 28, 265
MESOTROPHIC, EUTROPHIC = 3.0, 9.9


def ponds(**kw):
    base = dict(
        implementation_time=5,
        capitalization_time=15,
        rate_type="linear",
        delay=0,
        pond_area_start=0,
        pond_area_end=0,
        ef_ch4_start=BRACKISH_EF,
        ef_ch4_end=BRACKISH_EF,
        alpha_start=1.0,
        alpha_end=1.0,
        fish_production_start=0,
        fish_production_end=0,
        ef_n2o_start=N2O_EF,
        ef_n2o_end=N2O_EF,
        gwp_ch4=GWP_CH4,
        gwp_n2o=GWP_N2O,
    )
    base.update(kw)
    m = CoastalAquaculturePonds(**base)
    m.calculate_emissions()
    return m


def total(m, gas, activity):
    return sum(e.value for s in m.result.yearly_emissions_by_sector_by_gas if s.gas_type == gas and s.activity == activity for e in s.emissions)


def test_mangrove_converted_to_brackish_pond():
    # 40 ha of mangrove dug into a mesotrophic brackish pond producing 2 t fish/ha/yr, linear over 5 years.
    m = ponds(pond_area_end=40, alpha_end=MESOTROPHIC, fish_production_end=2000)

    # 40 ha x 183 kg CH4/ha/yr x 3 = 21.96 t CH4/yr = 614.88 tCO2-eq/yr at full adoption
    # 40 ha x 2000 kg/ha/yr x 0.00169 = 135.2 kg N2O-N/yr x 44/28 x 265 = 56.3011 tCO2-eq/yr
    # Linear phase-in: yearly shares 0.1, 0.3, 0.5, 0.7, 0.9, then 15 full years = 17.5 years equivalent.
    assert total(m, GasTypes.CH4, ActivityTypes.COASTAL_WATERBODIES) == pytest.approx(614.88 * 17.5)
    assert total(m, GasTypes.N2O, ActivityTypes.N20_FIELD) == pytest.approx(56.30114 * 17.5, rel=1e-6)


def test_water_quality_improvement_reduces_ch4():
    existing = dict(pond_area_start=40, pond_area_end=40, alpha_start=EUTROPHIC, fish_production_start=2000, fish_production_end=2000)
    without = ponds(**existing, alpha_end=EUTROPHIC)
    with_ = ponds(**existing, alpha_end=MESOTROPHIC)

    ch4_wo = total(without, GasTypes.CH4, ActivityTypes.COASTAL_WATERBODIES)
    ch4_w = total(with_, GasTypes.CH4, ActivityTypes.COASTAL_WATERBODIES)
    assert ch4_wo == pytest.approx(40 * 183 * 9.9 / 1000 * 28 * 20)
    # Eutrophic -> mesotrophic over 5 years: alpha falls by 6.9, the same 17.5 years equivalent as above.
    assert ch4_wo - ch4_w == pytest.approx(40 * 183 * 6.9 / 1000 * 28 * 17.5)
    assert total(without, GasTypes.N2O, ActivityTypes.N20_FIELD) == pytest.approx(total(with_, GasTypes.N2O, ActivityTypes.N20_FIELD))


def test_inventory_holds_start_year_values():
    m = ponds(pond_area_start=10, pond_area_end=40, fish_production_start=1000)
    rows = {(r.gas_type, r.activity): r.value for r in m.inventory.emissions_by_sector_by_gas}
    assert rows[(GasTypes.CH4, ActivityTypes.COASTAL_WATERBODIES)] == pytest.approx(10 * 183 / 1000 * 28)
    assert rows[(GasTypes.N2O, ActivityTypes.N20_FIELD)] == pytest.approx(10 * 1000 * N2O_EF / 1000 * 44 / 28 * 265)
