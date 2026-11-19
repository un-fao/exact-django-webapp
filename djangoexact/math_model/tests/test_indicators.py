from math_model.indicators import ActivityLand, LandParcel, converted_area, land_use_matrix


def _activity(id, start, w, wo, area):
    return ActivityLand(id=id, name=f"a{id}", parcels=[LandParcel(start, w, wo, area)])


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
