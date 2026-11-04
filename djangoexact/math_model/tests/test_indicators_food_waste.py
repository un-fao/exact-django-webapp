from math_model.indicators_food_waste import food_waste_series, sum_by_route


def _block(w, wo):
    return {"w": w, "wo": wo}


def test_sum_by_route_pads_and_cuts_to_duration():
    blocks = [
        _block({"swds": [1.0, 2.0]}, {"swds": [3.0, 3.0, 3.0, 3.0]}),
        _block({"swds": [1.0, 1.0, 1.0], "composting": [5.0]}, {}),
    ]
    out = sum_by_route(blocks, 3)
    assert out["w"]["swds"] == [2.0, 3.0, 1.0]
    assert out["w"]["composting"] == [5.0, 0.0, 0.0]
    assert out["wo"]["swds"] == [3.0, 3.0, 3.0]
    assert out["wo"]["anaerobic_digestion"] == [0.0, 0.0, 0.0]


def test_food_waste_series():
    blocks = [
        _block(
            {"swds": [80.0, 30.0], "composting": [10.0, 30.0], "anaerobic_digestion": [0.0, 0.0]},
            {"swds": [100.0, 100.0]},
        ),
        _block({"anaerobic_digestion": [50.0, 50.0], "other": [0.0, 0.0]}, {"swds": [50.0, 50.0]}),
    ]
    s = food_waste_series(sum_by_route(blocks, 2))
    assert s["generated_wo"] == [150.0, 150.0]
    assert s["generated_w"] == [140.0, 110.0]
    assert s["reduction"] == [10.0, 40.0]
    assert s["landfill_reduction"] == [70.0, 120.0]
    assert (s["composting_w"], s["composting_wo"]) == ([10.0, 30.0], [0.0, 0.0])
    assert s["anaerobic_digestion_w"] == [50.0, 50.0]


def test_no_blocks_is_all_zero():
    s = food_waste_series(sum_by_route([], 2))
    assert s["generated_w"] == s["reduction"] == [0.0, 0.0]
