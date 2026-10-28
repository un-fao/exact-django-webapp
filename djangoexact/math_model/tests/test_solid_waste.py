import math

import pytest

from math_model.no_time_dependency_final.general_functions import compute_yearly_or_half_year_cumulative
from math_model.no_time_dependency_final.ghg_emissions_classes import ActivityTypes, GasTypes
from math_model.no_time_dependency_final.solid_waste import (
    ROUTES,
    SWDS_ROUTES,
    WASTE_TYPES,
    SolidWaste,
    TreatmentFactors,
    WasteComponentFactors,
    first_order_decay,
)

# 2006 IPCC Vol. 5 Table 2.4 (dm, DOC wet, CF, FCF) and Table 3.3 k for boreal / temperate wet climate.
COMPONENTS = {
    "food": WasteComponentFactors(doc=0.15, dry_matter=0.40, carbon=0.38, fossil_carbon=0.0, k=0.185),
    "garden": WasteComponentFactors(doc=0.20, dry_matter=0.40, carbon=0.49, fossil_carbon=0.0, k=0.10),
    "paper": WasteComponentFactors(doc=0.40, dry_matter=0.90, carbon=0.46, fossil_carbon=0.01, k=0.06),
    "wood": WasteComponentFactors(doc=0.43, dry_matter=0.85, carbon=0.50, fossil_carbon=0.0, k=0.03),
    "textiles": WasteComponentFactors(doc=0.24, dry_matter=0.80, carbon=0.50, fossil_carbon=0.20, k=0.06),
    "nappies": WasteComponentFactors(doc=0.24, dry_matter=0.40, carbon=0.70, fossil_carbon=0.10, k=0.06),
    "rubber_leather": WasteComponentFactors(doc=0.39, dry_matter=0.84, carbon=0.67, fossil_carbon=0.20, k=0.0),
    "plastics": WasteComponentFactors(doc=0.0, dry_matter=1.0, carbon=0.75, fossil_carbon=1.0, k=0.0),
    "metal": WasteComponentFactors(doc=0.0, dry_matter=1.0, carbon=0.0, fossil_carbon=0.0, k=0.0),
    "glass": WasteComponentFactors(doc=0.0, dry_matter=1.0, carbon=0.0, fossil_carbon=0.0, k=0.0),
    "other": WasteComponentFactors(doc=0.0, dry_matter=0.90, carbon=0.03, fossil_carbon=1.0, k=0.0),
}
MCF = {
    "swds_managed_anaerobic": 1.0,
    "swds_managed_semi_aerobic": 0.5,
    "swds_unmanaged_deep": 0.8,
    "swds_unmanaged_shallow": 0.4,
    "swds_uncategorised": 0.6,
    "open_dumping": 0.6,
}
OX = {route: 0.1 if route in ("swds_managed_anaerobic", "swds_managed_semi_aerobic") else 0.0 for route in SWDS_ROUTES}
TIER1 = TreatmentFactors(
    composting_ch4=4.0,
    composting_n2o=0.24,
    ad_ch4=0.8,
    incineration_ch4=0.2,
    incineration_n2o=50.0,
    incineration_of=1.0,
    open_burning_ch4=6500.0,
    open_burning_n2o=150.0,
    open_burning_of=0.71,
)
GWP_CH4, GWP_N2O = 28.0, 265.0


def only(key, keys):
    return {k: (1.0 if k == key else 0.0) for k in keys}


def make(amount_start=100.0, amount_end=100.0, composition=None, routes=None, impl=5, cap=15, rate="linear", **overrides):
    composition = composition or only("food", WASTE_TYPES)
    routes = routes or only("swds_uncategorised", ROUTES)
    kwargs = dict(
        amount_start=amount_start,
        amount_end=amount_end,
        composition_start=composition,
        composition_end=composition,
        routes_start=routes,
        routes_end=routes,
        components=COMPONENTS,
        mcf=MCF,
        ox=OX,
        factors_start=TIER1,
        factors_end=TIER1,
        gwp_ch4=GWP_CH4,
        gwp_n2o=GWP_N2O,
        implementation_time=impl,
        capitalization_time=cap,
        rate_type=rate,
        delay=0,
    )
    kwargs.update(overrides)
    module = SolidWaste(**kwargs)
    module.calculate_emissions()
    return module


def series(module, activity, gas):
    sets = [s for s in module.result.yearly_emissions_by_sector_by_gas if s.activity == activity and s.gas_type == gas]
    assert len(sets) == 1
    return [e.value for e in sets[0].emissions]


def inventory(module, activity, gas):
    return next(i.value for i in module.inventory.emissions_by_sector_by_gas if i.activity == activity and i.gas_type == gas)


def test_fod_single_pulse_starts_decaying_the_year_after_disposal():
    k = 0.185
    decomposed = first_order_decay([10.0, 0.0, 0.0, 0.0], k)
    assert decomposed[0] == 0.0
    assert decomposed[1] == pytest.approx(10.0 * (1 - math.exp(-k)))
    assert decomposed[2] == pytest.approx(10.0 * math.exp(-k) * (1 - math.exp(-k)))
    assert sum(first_order_decay([10.0] + [0.0] * 400, k)) == pytest.approx(10.0)


def test_swds_constant_deposit_approaches_ipcc_mass_balance():
    # Once the FOD stock is in equilibrium, yearly CH4 = W * DOC * DOCf * MCF * F * 16/12 (eq. 3.2, 3.6).
    module = make(impl=1, cap=199, routes=only("swds_unmanaged_deep", ROUTES))
    expected = 100.0 * 0.15 * 0.5 * 0.8 * 0.5 * 16 / 12 * GWP_CH4
    ch4 = series(module, ActivityTypes.SOLID_WASTE_DISPOSAL, GasTypes.CH4)
    assert ch4[0] == pytest.approx(0.0)
    assert ch4[-1] == pytest.approx(expected, rel=1e-9)
    assert inventory(module, ActivityTypes.SOLID_WASTE_DISPOSAL, GasTypes.CH4) == pytest.approx(expected)


def test_swds_oxidation_and_recovery():
    plain = make(routes=only("swds_managed_anaerobic", ROUTES))
    recovered = make(routes=only("swds_managed_anaerobic", ROUTES), swds_recovery_start=0.5, swds_recovery_end=0.5)
    base = make(routes=only("swds_uncategorised", ROUTES))
    p = series(plain, ActivityTypes.SOLID_WASTE_DISPOSAL, GasTypes.CH4)
    r = series(recovered, ActivityTypes.SOLID_WASTE_DISPOSAL, GasTypes.CH4)
    b = series(base, ActivityTypes.SOLID_WASTE_DISPOSAL, GasTypes.CH4)
    # Managed anaerobic: MCF 1.0 vs 0.6, OX 0.1 vs 0.
    assert p[-1] == pytest.approx(b[-1] / 0.6 * 0.9)
    assert r[-1] == pytest.approx(p[-1] * 0.5)


def test_inert_and_non_degrading_waste_emits_nothing_in_swds():
    for waste in ("plastics", "metal", "glass", "rubber_leather", "other"):
        module = make(composition=only(waste, WASTE_TYPES))
        assert sum(series(module, ActivityTypes.SOLID_WASTE_DISPOSAL, GasTypes.CH4)) == 0.0


def test_composting_and_anaerobic_digestion_table_4_1():
    compost = make(routes=only("composting", ROUTES))
    assert series(compost, ActivityTypes.COMPOSTING, GasTypes.CH4)[0] == pytest.approx(100.0 * 4.0 * 1e-3 * GWP_CH4)
    assert series(compost, ActivityTypes.COMPOSTING, GasTypes.N2O)[0] == pytest.approx(100.0 * 0.24 * 1e-3 * GWP_N2O)
    ad = make(routes=only("anaerobic_digestion", ROUTES), ad_recovery_start=0.25, ad_recovery_end=0.25)
    assert series(ad, ActivityTypes.ANAEROBIC_DIGESTION, GasTypes.CH4)[0] == pytest.approx(100.0 * 0.8 * 1e-3 * 0.75 * GWP_CH4)


def test_incineration_counts_fossil_co2_only():
    food = make(routes=only("incineration", ROUTES))
    assert sum(series(food, ActivityTypes.WASTE_INCINERATION, GasTypes.CO2)) == 0.0
    plastics = make(composition=only("plastics", WASTE_TYPES), routes=only("incineration", ROUTES))
    # eq. 5.2: 100 t * dm 1.0 * CF 0.75 * FCF 1.0 * OF 1.0 * 44/12.
    assert series(plastics, ActivityTypes.WASTE_INCINERATION, GasTypes.CO2)[0] == pytest.approx(100.0 * 0.75 * 44 / 12)
    assert series(plastics, ActivityTypes.WASTE_INCINERATION, GasTypes.CH4)[0] == pytest.approx(100.0 * 0.2e-6 * GWP_CH4)
    assert series(plastics, ActivityTypes.WASTE_INCINERATION, GasTypes.N2O)[0] == pytest.approx(100.0 * 50e-6 * GWP_N2O)


def test_open_burning_oxidation_factor_and_dry_matter_n2o():
    textiles = make(composition=only("textiles", WASTE_TYPES), routes=only("open_burning", ROUTES))
    assert series(textiles, ActivityTypes.WASTE_OPEN_BURNING, GasTypes.CO2)[0] == pytest.approx(100.0 * 0.8 * 0.5 * 0.2 * 0.71 * 44 / 12)
    assert series(textiles, ActivityTypes.WASTE_OPEN_BURNING, GasTypes.CH4)[0] == pytest.approx(100.0 * 6500e-6 * GWP_CH4)
    assert series(textiles, ActivityTypes.WASTE_OPEN_BURNING, GasTypes.N2O)[0] == pytest.approx(100.0 * 0.8 * 150e-6 * GWP_N2O)


def test_dynamics_follow_the_activity_change_rate():
    compost = make(amount_start=0.0, amount_end=100.0, routes=only("composting", ROUTES), impl=4, cap=2)
    expected = [v * 4.0 * 1e-3 * GWP_CH4 for v in compute_yearly_or_half_year_cumulative(0.0, 100.0, 4, 2, "linear")]
    assert series(compost, ActivityTypes.COMPOSTING, GasTypes.CH4) == pytest.approx(expected)


def test_food_waste_by_route_block():
    composition = {**only("food", WASTE_TYPES), "food": 0.5, "paper": 0.5}
    routes = {**only("other", ROUTES), "swds_uncategorised": 0.2, "open_dumping": 0.1, "composting": 0.3, "incineration": 0.25, "other": 0.15}
    module = make(composition=composition, routes=routes, impl=2, cap=1, delay=1)
    block = module.food_waste_by_route
    assert set(block) == {"swds", "composting", "anaerobic_digestion", "incineration", "open_burning", "other"}
    assert block["swds"] == pytest.approx([0.0, 15.0, 15.0, 15.0])
    assert block["composting"] == pytest.approx([0.0, 15.0, 15.0, 15.0])
    assert sum(block[g][1] for g in block) == pytest.approx(50.0)


def test_zero_amount_gives_zero_everywhere():
    module = make(amount_start=0.0, amount_end=0.0)
    assert all(e.value == 0.0 for s in module.result.yearly_emissions_by_sector_by_gas for e in s.emissions)


def recurrence_swds_ch4(activity: list[float], food_share: float, swd_share: float, doc: float, docf: float, mcf: float, k: float, gwp: float) -> list[float]:
    """IPCC Vol. 5 eq. 3.4 and 3.5 written as a plain year-by-year stock recurrence; returns the yearly CH4 (not cumulative)."""
    stock_prev = 0.0
    out = []
    for value in activity:
        deposit = value * food_share * swd_share * doc * docf * mcf
        out.append(stock_prev * (1 - math.exp(-k)) * 16 / 12 * 0.5 * gwp)
        stock_prev = deposit + stock_prev * math.exp(-k)
    return out


def test_swds_fod_matches_stock_recurrence():
    activity = [1000.0 + 50.0 * t for t in range(30)]
    k = 0.4
    expected = recurrence_swds_ch4(activity, food_share=0.6, swd_share=0.7, doc=0.15, docf=0.5, mcf=0.6, k=k, gwp=GWP_CH4)
    deposits = [a * 0.6 * 0.7 * 0.15 * 0.5 * 0.6 for a in activity]
    actual = [d * 0.5 * 16 / 12 * GWP_CH4 for d in first_order_decay(deposits, k)]
    assert actual == pytest.approx(expected, rel=1e-12)
