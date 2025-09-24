from itertools import product
import api.models as models
from .minitool import ClimateMoistureValidator, SoilOrganicCarbonValidator


def domains_from_fields(fields: dict):
    # pair *_start with *_w and get their (same) domain
    pairs = []
    singles = []

    # Track which fields are already processed as pairs
    processed_fields = set()

    for k in sorted(fields):
        if k.endswith("_start"):
            base = k[:-6]
            s = f"{base}_start"
            w = f"{base}_w"
            if w in fields:
                dom = list(fields[s])  # materialize QuerySet once
                pairs.append((base, s, w, dom))
                processed_fields.add(s)
                processed_fields.add(w)

    # Handle single fields that don't have _start/_w pairs
    for k in sorted(fields):
        if k not in processed_fields and not k.endswith("_w"):
            dom = list(fields[k])  # materialize QuerySet once
            singles.append((k, dom))

    return pairs, singles  # (paired_fields, single_fields)


def hamming_shell_rows(fields: dict):
    """
    fields: your dict of columns -> iterable/QuerySet
    Yields dict rows where exactly one *_w differs from *_start,
    all others have w == start (same chosen baseline value).
    Single fields (without _start/_w pairs) are included in every combination.
    """
    pairs, singles = domains_from_fields(fields)

    # Domains for paired fields and single fields
    paired_bases = [dom for (_, _, _, dom) in pairs]
    single_bases = [dom for (_, dom) in singles]

    # All combinations: paired field baselines × single field values
    all_bases = paired_bases + single_bases

    # iterate baseline assignment (choose ONE value per field)
    for baseline_vals in product(*all_bases):
        # Split baseline values between paired and single fields
        paired_vals = baseline_vals[: len(pairs)]
        single_vals = baseline_vals[len(pairs) :]

        # map: paired field -> chosen baseline value
        base_map = {pairs[i][0]: paired_vals[i] for i in range(len(pairs))}

        # map: single field -> chosen value
        single_map = {singles[i][0]: single_vals[i] for i in range(len(singles))}

        # for each paired field, flip its _w to an alternative value
        for i, (base, s_col, w_col, dom) in enumerate(pairs):
            s_val = base_map[base]
            for alt in dom:
                if alt == s_val:
                    continue  # must differ
                row = {}
                # fill all paired fields: start = baseline, w = baseline (same)
                for b, s, w, _ in pairs:
                    row[s] = base_map[b]
                    row[w] = base_map[b]
                # flip exactly one paired field
                row[w_col] = alt
                # add all single fields
                for field_name, value in single_map.items():
                    row[field_name] = value
                yield row


def expected_count(fields: dict) -> int:
    pairs, singles = domains_from_fields(fields)
    paired_sizes = [len(dom) for (_, _, _, dom) in pairs]
    single_sizes = [len(dom) for (_, dom) in singles]

    # Calculate baseline combinations (all paired + single fields)
    baseline_combinations = 1
    for s in paired_sizes + single_sizes:
        baseline_combinations *= s

    # For each baseline, we generate (sum of (size-1) for paired fields) variations
    if paired_sizes:
        variations_per_baseline = sum(s - 1 for s in paired_sizes)
        return baseline_combinations * variations_per_baseline
    else:
        # If no paired fields, just return single field combinations
        return baseline_combinations


annual_cropland_climate_moistures = ClimateMoistureValidator.get_valid_combinations([models.LandUseType.objects.get(name="Default")], models)
annual_cropland_soil_types = SoilOrganicCarbonValidator.get_valid_combinations(annual_cropland_climate_moistures, models.SoilType.objects.filter(is_coastal=False, active=True).all(), models)
annual_cropland_regions = models.Region.objects.filter(countries__isnull=False).all()
annual_cropland_climates = list(set((cm[0], cm[1]) for cm in annual_cropland_soil_types))
annual_cropland_moistures = list(set(cm[1] for cm in annual_cropland_soil_types))

# Module configurations
MODULE_CONFIGS = {
    "Grassland": {  # Compute # DONE
        "fields": {
            "grassland_management_type_start": models.GrasslandManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "grassland_management_type_w": models.GrasslandManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "is_fire_used_start": [True, False],
            "is_fire_used_w": [True, False],
            "fire_periodicity_start": [1],
            "fire_periodicity_w": [1],
            "fire_impact_start": [1, 0],
            "fire_impact_w": [1, 0],
        },
        "config_name": "grassland",
    },
    "Livestock": {  # Compute # DONE
        "fields": {
            "livestock_category_types": models.LivestockCategoryType.objects.all(),
            "livestock_production_type_start": models.LivestockProductionType.objects.all(),
            "livestock_production_type_w": models.LivestockProductionType.objects.all(),
            "heads_number_start": [1],
            "heads_number_w": [1],
        },
        "config_name": "livestock",
    },
    "AnnualCropland": {  # DONE
        "fields": {
            "region": annual_cropland_regions,
            "climate": annual_cropland_climates,
            "moisture": annual_cropland_moistures,
            "soil_types": annual_cropland_soil_types,
            "land_use_type_start": [models.LandUseType.objects.get(name="Default")],
            "land_use_type_w": [models.LandUseType.objects.get(name="Default")],
            "tillage_management_type_start": models.TillageManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "tillage_management_type_w": models.TillageManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "organic_input_type_start": models.OrganicInputType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "organic_input_type_w": models.OrganicInputType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "residue_management_type_start": models.ResidueManagementType.objects.all(),
            "residue_management_type_w": models.ResidueManagementType.objects.all(),
        },
        "config_name": "annual_cropland",
    },
    "FloodedRice": {  # Skip
        "fields": {
            "water_management_type_before_cultivation_start": models.WaterManagementTypeBeforeCultivation.objects.all(),
            "water_management_type_before_cultivation_w": models.WaterManagementTypeBeforeCultivation.objects.all(),
            "water_management_type_after_cultivation_start": models.WaterManagementTypeAfterCultivation.objects.all(),
            "water_management_type_after_cultivation_w": models.WaterManagementTypeAfterCultivation.objects.all(),
            "organic_amendment_type_start": models.OrganicAmendmentType.objects.all(),
            "organic_amendment_type_w": models.OrganicAmendmentType.objects.all(),
        },
        "config_name": "flooded_rice",
    },
    "PerennialCropland": {  # Skip
        "fields": {
            "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Perennial Cropland").all(),
            "land_use_type_w": models.LandUseType.objects.filter(module_types__name="Perennial Cropland").all(),
            "organic_input_type_start": models.OrganicInputType.objects.filter(is_active=True).all(),
            "organic_input_type_w": models.OrganicInputType.objects.filter(is_active=True).all(),
            "tillage_management_type_start": models.TillageManagementType.objects.all(),
            "tillage_management_type_w": models.TillageManagementType.objects.all(),
            "is_biomass_burned_start": [True, False],
            "is_biomass_burned_w": [True, False],
            "fire_periodicity_t2_start": [1],
            "fire_periodicity_t2_w": [1],
        },
        "config_name": "perennial_cropland",
    },
    "ForestManagement": {  # Compute
        "fields": {
            "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Forest Management").all(),
            "forest_type": models.ForestType.objects.all(),
            "forest_condition_type": models.ForestConditionType.objects.all(),
            "average_yearly_degradation_percentage_start": [0],
            "average_yearly_degradation_percentage_w": [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5],  # 1% to 5% and then 10% to 50%
        },
        "config_name": "forest_management",
    },
    "SmallFishery": {  # Compute # DONE
        "fields": {
            "gear_type_start": models.SmallFisheryGearType.objects.all(),
            "gear_type_w": models.SmallFisheryGearType.objects.all(),
            "fishery_type": models.FisheryType.objects.all(),
        },
        "config_name": "small_fishery",
    },
    "LargeFishery": {  # Skip # DONE
        "fields": {
            "gear_type_start": models.LargeFisheryGearType.objects.all(),
            "gear_type_w": models.LargeFisheryGearType.objects.all(),
            "fish_type": models.FishType.objects.all(),
        },
        "config_name": "large_fishery",
    },
    "CoastalWetland": {  # Skip
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland").all(),
            "area_under_drainage_start": [1, 0],
            "area_under_drainage_w": [1, 0],
            "drained_area_excavated_start": [1, 0],
            "drained_area_excavated_w": [1, 0],
            "area_not_drained_or_rewetted_start": [0],
            "area_not_drained_or_rewetted_w": [0],
            "area_w_restored_vegetation_start": [0],
            "area_w_restored_vegetation_w": [0],
        },
        "config_name": "coastal_wetland",
    },
    "CoastalWetland2": {  # Skip
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland").all(),
            "area_under_drainage_start": [0],
            "area_under_drainage_w": [0],
            "drained_area_excavated_start": [0],
            "drained_area_excavated_w": [0],
            "area_not_drained_or_rewetted_start": [1, 0],
            "area_not_drained_or_rewetted_w": [1, 0],
            "area_w_restored_vegetation_start": [1, 0],
            "area_w_restored_vegetation_w": [1, 0],
        },
        "config_name": "coastal_wetland",
    },
    "Input": {  # Compute # BUG: ZERO RESULTS
        "fields": {
            "input_type": models.InputType.objects.all(),
            "value_start": [1, 0],
            "value_w": [1, 0],
        },
        "config_name": "input",
    },
    "Waterbody": {  # Compute # DONE
        "fields": {
            "waterbody_type": models.WaterbodyType.objects.all(),
            "trophic_type_start": models.TrophicType.objects.all(),
            "trophic_type_w": models.TrophicType.objects.all(),
        },
        "config_name": "waterbody",
    },
}


def run():
    annual_cropland = MODULE_CONFIGS["AnnualCropland"]

    rows = hamming_shell_rows(annual_cropland["fields"])
    n = expected_count(annual_cropland["fields"])
    print(f"Hamming shell count: {n}")
    print(f"Hamming shell rows: {len(list(rows))}")
