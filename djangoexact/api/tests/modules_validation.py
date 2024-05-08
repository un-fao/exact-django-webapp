organic_mandatory_fields = {
    "drainage_area_start": [
        "area_not_drained_start",
    ],
    "drainage_area_w": [
        "area_not_drained_w",
    ],
    "drainage_area_wo": [
        "area_not_drained_wo",
    ],
    "peat_type": [
        [
            {
                "peat_extraction_height_start": [
                    "peat_area_start",
                    "peat_ditches_area_start",
                ],
            },
            {
                "peat_extraction_height_w": [
                    "peat_area_w",
                    "peat_ditches_area_w",
                ],
            },
            {
                "peat_extraction_height_wo": [
                    "peat_area_wo",
                    "peat_ditches_area_wo",
                ],
            },
        ],
    ],
}

building_mandatory_fields = {
    "building_type": [
        ["area_m2_start", "area_m2_w", "area_m2_wo"],
    ],
}

grassland_mandatory_fields = {
    "grassland_management_type_start": [
        "yield_start",
        {
            "is_fire_used_start": [
                "fire_periodicity_start",
                "fire_impact_start",
            ]
        },
    ],
    "grassland_management_type_w": [
        "yield_w",
        {
            "is_fire_used_w": [
                "fire_periodicity_w",
                "fire_impact_w",
            ]
        },
    ],
    "grassland_management_type_wo": [
        "yield_wo",
        {
            "is_fire_used_wo": [
                "fire_periodicity_wo",
                "fire_impact_wo",
            ]
        },
    ],
}


def is_ready(data, mandatory_fields: dict, first=True):

    if isinstance(mandatory_fields, list):
        print("List ", mandatory_fields)
        for field in mandatory_fields:
            if data.get(field) in (None, False):
                return False

    if isinstance(mandatory_fields, dict):

        # If mandatory_fields is empty, return True
        if first and mandatory_fields == {}:
            return True

        # If this is the first call and no mandatory fields are present, return False
        if not any(data.get(f) for f in mandatory_fields.keys()) and first:
            return False

        for field, items in mandatory_fields.items():

            # If the main field is None or False, skip validation for this field
            if data.get(field) in (None, False):
                continue

            # If items is a list, iterate over its elements
            if isinstance(items, list):
                for sub_field in items:
                    if isinstance(sub_field, list):
                        # If sub_field is a list of dictionaries, validate all of them
                        if all(isinstance(f, dict) for f in sub_field):

                            # If none of the main fields were provided, return False
                            main_fields = [list(f.keys())[0] for f in sub_field]
                            if not any(data.get(f) for f in main_fields):
                                return False

                            # Only validate the main fields that were provided
                            available_main_fields = [f for f in sub_field if data.get(list(f.keys())[0])]
                            for main_field in available_main_fields:
                                for f, v in main_field.items():
                                    if data.get(f) is None or not is_ready(data, v, first=False):
                                        return False

                        # If sub_field is a list of strings, validate all of them
                        elif all(isinstance(f, str) for f in sub_field):
                            if not any(data.get(f) for f in sub_field):
                                return False

                    # If sub_field is a dictionary, validate nested data recursively
                    elif isinstance(sub_field, dict):
                        if not is_ready(data, sub_field, first=False):
                            return False

                    # If sub_field is a string, validate the field
                    elif data.get(sub_field) in (None, False):
                        return False

            # If items is a dictionary, recursively validate nested data
            elif isinstance(items, dict):
                if not is_ready(data, items, first=False):
                    return False

    return True


def main():
    data = {
        "drainage_area_start": 1,
        "area_not_drained_start": 1,
        #
        "drainage_area_w": None,
        "area_not_drained_w": None,
        #
        "drainage_area_wo": None,
        "area_not_drained_wo": None,
        #
        "peat_type": 1,
        #
        "peat_extraction_height_start": 1,
        "peat_area_start": 1,
        "peat_ditches_area_start": 1,
        #
        "peat_extraction_height_w": None,
        "peat_area_w": None,
        "peat_ditches_area_w": None,
        #
        "peat_extraction_height_wo": None,
        "peat_area_wo": None,
        "peat_ditches_area_wo": None,
    }
    print("Organic Soil Valid: ", is_ready(data, organic_mandatory_fields))

    data = {
        "building_type": 1,
        "area_m2_start": 1,
        "area_m2_w": None,
        "area_m2_wo": None,
    }
    print("Building Valid: ", is_ready(data, building_mandatory_fields))

    data = {
        "grassland_management_type_start": 1,
        "yield_start": 1,
        "is_fire_used_start": False,
        "fire_periodicity_start": 1,
        "fire_impact_start": None,
        #
        "grassland_management_type_w": None,
        "yield_w": None,
        "is_fire_used_w": None,
        "fire_periodicity_w": None,
        "fire_impact_w": None,
        #
        "grassland_management_type_wo": None,
        "yield_wo": None,
        "is_fire_used_wo": None,
        "fire_periodicity_wo": None,
        "fire_impact_wo": None,
    }
    print("Grassland Valid: ", is_ready(data, grassland_mandatory_fields))

    empty_mandatory_fields = {}
    data = {}
    print("Empty Valid: ", is_ready(data, empty_mandatory_fields))


main()
