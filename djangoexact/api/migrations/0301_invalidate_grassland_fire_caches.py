from django.db import migrations
from django.db.models import Q


def invalidate_grassland_caches(apps, schema_editor):
    """Grassland fire used IPCC total biomass as its AGB default, so cached results of
    non-finalized projects are stale. That covers standalone grassland modules and land-use
    changes with grassland in any scenario. Finalized projects are left alone: their results
    must not move."""
    cache_reset = {
        "last_cached_at": None,
        "cached_results_total": None,
        "cached_results_by_activity": None,
        "cached_results_by_gas": None,
        "cached_results_by_activity_by_gas": None,
        "cached_units_breakdown": None,
    }
    apps.get_model("api", "Grassland").objects.filter(
        Q(activity__project__is_finalized=False) | Q(land_use_change__activity__project__is_finalized=False)
    ).update(**cache_reset)
    apps.get_model("api", "LandUseChange").objects.filter(activity__project__is_finalized=False).filter(
        Q(module_type_start__class_name="Grassland")
        | Q(module_type_w__class_name="Grassland")
        | Q(module_type_wo__class_name="Grassland")
    ).update(**cache_reset)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0300_invalidate_energy_gross_total_caches"),
    ]

    operations = [
        migrations.RunPython(invalidate_grassland_caches, migrations.RunPython.noop),
    ]
