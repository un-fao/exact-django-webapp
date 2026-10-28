from django.db import migrations

CLEARED = {
    "last_cached_at": None,
    "cached_results_total": None,
    "cached_results_by_activity": None,
    "cached_results_by_gas": None,
    "cached_results_by_activity_by_gas": None,
    "cached_units_breakdown": None,
}


def invalidate_caches(apps, schema_editor):
    """The dry matter harvested before conversion is now ignored unless the land use change starts from forest or
    perennial cropland. Perennial cropland feeds the HWP pool on complete renewal and change of system, but its own
    results do not change (the pool recomputes its sources), so only the pools are cleared. Finalized projects keep
    their results."""
    LandUseChange = apps.get_model("api", "LandUseChange")
    HarvestedWoodProducts = apps.get_model("api", "HarvestedWoodProducts")
    LandUseChange.objects.filter(activity__project__is_finalized=False).exclude(
        module_type_start__class_name__in=("ForestManagement", "PerennialCropland")
    ).update(**CLEARED)
    HarvestedWoodProducts.objects.filter(activity__project__is_finalized=False).update(**CLEARED)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0297_harvested_wood_products"),
    ]

    operations = [
        migrations.RunPython(invalidate_caches, migrations.RunPython.noop),
    ]
