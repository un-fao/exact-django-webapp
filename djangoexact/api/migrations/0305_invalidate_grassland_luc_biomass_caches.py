from django.db import migrations
from django.db.models import Q


def invalidate_grassland_luc_caches(apps, schema_editor):
    """Grassland's Tier 2 LUC stock now fills a missing AGB or BGB from IPCC instead of using the
    entered half alone, so cached results of land-use changes with grassland are stale.
    Standalone grassland never computes a biomass stock. Finalized projects are left alone."""
    cache_reset = {
        "last_cached_at": None,
        "cached_results_total": None,
        "cached_results_by_activity": None,
        "cached_results_by_gas": None,
        "cached_results_by_activity_by_gas": None,
        "cached_units_breakdown": None,
    }
    apps.get_model("api", "Grassland").objects.filter(
        land_use_change__isnull=False, land_use_change__activity__project__is_finalized=False
    ).update(**cache_reset)
    apps.get_model("api", "LandUseChange").objects.filter(activity__project__is_finalized=False).filter(
        Q(module_type_start__class_name="Grassland")
        | Q(module_type_w__class_name="Grassland")
        | Q(module_type_wo__class_name="Grassland")
    ).update(**cache_reset)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0304_finalizedreportdata"),
    ]

    operations = [
        migrations.RunPython(invalidate_grassland_luc_caches, migrations.RunPython.noop),
    ]
