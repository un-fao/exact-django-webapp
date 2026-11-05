import pytest

from math_model.no_time_dependency_final.food_wastewater import (
    BO_COD,
    EF_N2O_EFFLUENT,
    FoodWastewater,
    ScenarioInputs,
    TreatmentShare,
    annual_emissions,
)
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes

DEEP_LAGOON = TreatmentShare(share=1.0, mcf=0.8, ef_n2o_plant=0.0, n_removal=0.0)
AEROBIC = TreatmentShare(share=1.0, mcf=0.0, ef_n2o_plant=0.016, n_removal=0.4)


def meat(**overrides) -> ScenarioInputs:
    values = dict(production=1000.0, wastewater=13.0, cod=4.1, total_n=0.19, treatment=[DEEP_LAGOON])
    values.update(overrides)
    return ScenarioInputs(**values)


def test_ipcc_constants():
    assert BO_COD == 0.25
    assert EF_N2O_EFFLUENT == 0.005


def test_ch4_hand_calculation_deep_lagoon():
    # TOW = 1000 t * 13 m3/t * 4.1 kg/m3 = 53,300 kg COD; CH4 = 53,300 * 0.25 * 0.8 = 10,660 kg
    ch4, _ = annual_emissions(meat())
    assert ch4 == pytest.approx(10.66)


def test_sludge_and_recovery_are_subtracted():
    ch4, _ = annual_emissions(meat(sludge_removed=3300.0, ch4_recovered=1000.0))
    assert ch4 == pytest.approx(((53300 - 3300) * 0.25 * 0.8 - 1000) / 1000)


def test_recovery_cannot_make_emissions_negative():
    ch4, _ = annual_emissions(meat(ch4_recovered=1e9, sludge_removed=1e9))
    assert ch4 == 0.0


def test_mix_is_share_weighted():
    mix = [TreatmentShare(0.5, 0.8, 0.0, 0.0), TreatmentShare(0.5, 0.0, 0.016, 0.4)]
    ch4, n2o = annual_emissions(meat(treatment=mix))
    assert ch4 == pytest.approx(10.66 / 2)
    tn = 1000 * 13 * 0.19
    plant = tn * 0.5 * 0.016
    effluent = tn * (0.5 * 1 + 0.5 * 0.6) * 0.005
    assert n2o == pytest.approx((plant + effluent) * 44 / 28 / 1000)


def test_n2o_aerobic_plant_and_effluent():
    _, n2o = annual_emissions(meat(treatment=[AEROBIC]))
    tn = 1000 * 13 * 0.19
    assert n2o == pytest.approx(tn * (0.016 + 0.6 * 0.005) * 44 / 28 / 1000)


def test_no_nitrogen_default_means_no_n2o():
    _, n2o = annual_emissions(meat(total_n=None))
    assert n2o == 0.0


def test_series_follows_change_rate_and_gwp():
    math = FoodWastewater(
        implementation_time=2,
        capitalization_time=1,
        rate_type="linear",
        delay=0,
        start=meat(),
        end=meat(production=0.0),
        gwp_ch4=28.0,
        gwp_n2o=265.0,
    )
    math.calculate_emissions()
    by_activity = {s.activity: s for s in math.result.yearly_emissions_by_sector_by_gas}
    ch4 = [e.value for e in by_activity[ActivityTypes.FOOD_WASTEWATER_CH4].emissions]
    start = 10.66 * 28
    # Linear 1 -> 0 over two years, then constant, as half-year averages.
    assert ch4 == pytest.approx([start * 0.75, start * 0.25, 0.0])
    assert by_activity[ActivityTypes.FOOD_WASTEWATER_CH4].gas_type == GasTypes.CH4
    assert by_activity[ActivityTypes.FOOD_WASTEWATER_N2O].gas_type == GasTypes.N2O
    inventory = {row.activity: row.value for row in math.inventory.emissions_by_sector_by_gas}
    assert inventory[ActivityTypes.FOOD_WASTEWATER_CH4] == pytest.approx(start)
