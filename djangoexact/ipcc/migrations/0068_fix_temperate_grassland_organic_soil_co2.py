from django.db import migrations

# IPCC 2013 Wetlands Supplement, Table 2.1, grassland, temperate. EX-ACT does not split
# deep/shallow drained, so nutrient-rich is the mean of deep (6.1) and shallow (3.6) = 4.85,
# matching how its CH4 (27.5) and N2O (4.9) were averaged. Nutrient-poor drained is 5.3.
# The two CO2 values had been swapped.
CO2 = {"Nutrient Rich": (5.3, 4.85), "Nutrient Poor": (4.85, 5.3)}

CACHE_FIELDS = (
    "last_cached_at",
    "cached_results_total",
    "cached_results_by_activity",
    "cached_results_by_gas",
    "cached_results_by_activity_by_gas",
    "cached_units_breakdown",
)


def swap_co2(apps, schema_editor):
    EF = apps.get_model("ipcc", "OrganicSoilDrainageEmissionFactor")
    changed = 0
    for peat_type, (old, new) in CO2.items():
        # Filtering on the old value leaves rows an admin has already corrected untouched.
        changed += EF.objects.filter(
            module_type__name="Grassland",
            site_location_type__name="On-Site",
            climate__name__in=("Cool Temperate", "Warm Temperate"),
            peat_type__name=peat_type,
            co2=old,
        ).update(co2=new)
    if not changed:
        return
    # Over-invalidates organic soils outside temperate grassland; they just recompute on next read.
    # Finalized projects keep their results.
    OrganicSoil = apps.get_model("api", "OrganicSoil")
    OrganicSoil.objects.filter(activity__project__is_finalized=False).update(**{f: None for f in CACHE_FIELDS})


class Migration(migrations.Migration):

    dependencies = [
        ("ipcc", "0067_globalwarmingpotential_ch4_fossil_reference_values"),
        ("api", "0297_organic_soil_peat_quantity_water_table"),
    ]

    operations = [
        migrations.RunPython(swap_co2, migrations.RunPython.noop),
    ]
