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
    """A settlement's results now include its other infrastructure, so the cached results of settlements that
    have any are stale. The other infrastructure's own results do not change. Finalized projects keep their
    results."""
    Settlement = apps.get_model("api", "Settlement")
    OtherInfrastructure = apps.get_model("api", "OtherInfrastructure")
    Settlement.objects.filter(
        activity__project__is_finalized=False, pk__in=OtherInfrastructure.objects.values("parent")
    ).update(**CLEARED)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0324_merge_20261112_1125"),
    ]

    operations = [
        migrations.RunPython(invalidate_caches, migrations.RunPython.noop),
    ]
