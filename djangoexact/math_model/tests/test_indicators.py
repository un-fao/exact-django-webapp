import pytest

from math_model.indicators import (
    C_PER_CO2,
    ActivityLand,
    LandParcel,
    classify_soc,
    converted_area,
    forest_cover,
    forest_soc_loss,
    four_per_1000,
    land_use_matrix,
    net_zero_deforestation,
    soc_stock_change_series,
    soil_carbon_summary,
)


def _activity(id, start, w, wo, area, *, soil_w=(), soil_wo=(), soc_ref=None, start_year=2025, impl=5):
    return ActivityLand(
        id=id,
        name=f"a{id}",
        parcels=[LandParcel(start, w, wo, area)],
        start_year=start_year,
        implementation_years=impl,
        soil_co2_w=list(soil_w),
        soil_co2_wo=list(soil_wo),
        soc_ref=soc_ref,
        has_soil_results=bool(soil_w or soil_wo),
    )


def test_matrix_rows_are_start_columns_are_end():
    acts = [
        _activity(1, "forest", "cropland", "forest", 10),
        _activity(2, "cropland", "cropland", "cropland", 4),
    ]
    m = land_use_matrix(acts)
    assert m["with"][0][1] == 10
    assert m["without"][0][0] == 10
    assert m["with"][1][1] == 4
    assert converted_area(m["with"]) == 10
    assert converted_area(m["without"]) == 0


@pytest.mark.parametrize(
    "w, wo, expected",
    [
        (-20, -10, "enhanced"),   # both sinks, project sinks more (NEXT rule)
        (5, 10, "preserved"),     # both sources, project emits less (NEXT rule)
        (10, 5, "lost"),          # both sources, project emits more (NEXT rule)
        (-5, 10, "enhanced"),     # mixed sign, NEXT skips it
        (-5, -10, "lost"),        # weaker sink, NEXT skips it
        (3, 3, None),
    ],
)
def test_classify_soc(w, wo, expected):
    cls, tc = classify_soc(w, wo)
    assert cls == expected
    assert tc == pytest.approx(abs(w - wo) * C_PER_CO2)


def test_soil_summary_counts_area_once_per_activity():
    acts = [
        _activity(1, "cropland", "cropland", "cropland", 10, soil_w=[-11, -11], soil_wo=[0, 0]),
        _activity(2, "grassland", "grassland", "grassland", 5, soil_w=[11], soil_wo=[22]),
        _activity(3, "cropland", "cropland", "cropland", 7),
    ]
    s = soil_carbon_summary(acts)["totals"]
    assert s["enhanced"] == {"area": 10, "tc": pytest.approx(6)}
    assert s["preserved"] == {"area": 5, "tc": pytest.approx(3)}
    assert s["lost"] == {"area": 0, "tc": 0}


def test_soc_series_is_cumulative_gain_in_tc():
    acts = [_activity(1, "cropland", "cropland", "cropland", 1, soil_w=[-44, -44], soil_wo=[44, 0])]
    s = soc_stock_change_series(acts)
    assert s["with"] == pytest.approx([12, 24])
    assert s["without"] == pytest.approx([-12, -12])


def test_four_per_1000_relative_to_socref():
    # 100 ha, 50 tC/ha stock, gaining 20 tC/yr = 0.2 tC/ha/yr = 0.4 %/yr
    acts = [_activity(1, "cropland", "cropland", "cropland", 100, soil_w=[-20 / C_PER_CO2] * 10, soc_ref=50)]
    r = four_per_1000(acts, years=10)
    assert r["rate_tc_ha_yr"] == pytest.approx(0.2)
    assert r["relative_pct_yr"] == pytest.approx(0.4)
    assert r["activities"][0]["meets_target"] is True


def test_four_per_1000_without_socref_has_no_relative_rate():
    acts = [_activity(1, "cropland", "cropland", "cropland", 100, soil_w=[-1])]
    r = four_per_1000(acts, years=1)
    assert r["relative_pct_yr"] is None
    assert r["activities"][0]["meets_target"] is False


def test_forest_cover_and_soc_loss():
    acts = [
        _activity(1, "forest", "cropland", "forest", 10, soil_w=[44], soil_wo=[0]),
        _activity(2, "grassland", "forest", "grassland", 3),
    ]
    assert forest_cover(acts) == {"start": 10, "with": 3, "without": 10}
    assert forest_soc_loss(acts) == pytest.approx(12)


def test_net_zero_year_when_project_still_deforests():
    acts = [_activity(1, "forest", "cropland", "cropland", 10, start_year=2025, impl=5)]
    r = net_zero_deforestation(acts)
    assert r == {"year": 2030, "deforested_with": 10, "deforested_without": 10}


def test_net_zero_year_when_project_stops_deforestation():
    acts = [_activity(1, "forest", "forest", "cropland", 10, start_year=2026)]
    assert net_zero_deforestation(acts)["year"] == 2026


def test_net_zero_year_is_none_without_deforestation():
    acts = [_activity(1, "cropland", "forest", "cropland", 10)]
    assert net_zero_deforestation(acts)["year"] is None
