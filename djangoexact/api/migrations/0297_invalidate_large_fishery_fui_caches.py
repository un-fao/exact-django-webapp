from django.db import migrations


def invalidate_large_fishery_caches(apps, schema_editor):
    """The large fishery FUI lookup now skips the matrix's no-data (0) rows, so cached results of
    non-finalized large fisheries may be stale. Finalized projects are left alone: their results must not move."""
    apps.get_model("api", "LargeFishery").objects.filter(activity__project__is_finalized=False).update(
        last_cached_at=None,
        cached_results_total=None,
        cached_results_by_activity=None,
        cached_results_by_gas=None,
        cached_results_by_activity_by_gas=None,
        cached_units_breakdown=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0296_projectmembership_unique_user_project"),
    ]

    operations = [
        migrations.RunPython(invalidate_large_fishery_caches, migrations.RunPython.noop),
    ]
