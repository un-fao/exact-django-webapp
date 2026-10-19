from django.db import migrations


def invalidate_waterbody_caches(apps, schema_editor):
    """Pond Chl-a now drives the trophic factor and the Table 7.11 defaults changed, so cached
    waterbody results of non-finalized projects are stale. Finalized projects keep their results."""
    apps.get_model("api", "Waterbody").objects.filter(activity__project__is_finalized=False).update(
        last_cached_at=None,
        cached_results_total=None,
        cached_results_by_activity=None,
        cached_results_by_gas=None,
        cached_results_by_activity_by_gas=None,
        cached_units_breakdown=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0297_waterbody_reservoir"),
    ]

    operations = [
        migrations.RunPython(invalidate_waterbody_caches, migrations.RunPython.noop),
    ]
