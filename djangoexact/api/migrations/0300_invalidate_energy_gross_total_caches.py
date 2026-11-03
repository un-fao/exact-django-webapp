from django.db import migrations


def invalidate_energy_caches(apps, schema_editor):
    """Energy with/without totals were inflated by the start series, so cached results of
    non-finalized projects are stale. The deploy-time cache script is not relied on here (see
    #353). Finalized projects are left alone: their results must not move."""
    cache_reset = {
        "last_cached_at": None,
        "cached_results_total": None,
        "cached_results_by_activity": None,
        "cached_results_by_gas": None,
        "cached_results_by_activity_by_gas": None,
        "cached_units_breakdown": None,
    }
    apps.get_model("api", "Energy").objects.filter(activity__project__is_finalized=False).update(**cache_reset)
    apps.get_model("api", "EnergyEntry").objects.filter(parent__activity__project__is_finalized=False).update(
        **cache_reset
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0299_strip_translated_reference_names"),
    ]

    operations = [
        migrations.RunPython(invalidate_energy_caches, migrations.RunPython.noop),
    ]
