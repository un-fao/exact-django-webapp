from django.db import migrations


def invalidate_exponential_caches(apps, schema_editor):
    """The exponential change-rate curve was fixed in math_model, so cached results of non-finalized
    activities using it are stale. Finalized projects are left alone: their results must not move."""
    for model in apps.get_app_config("api").get_models():
        fields = {f.name for f in model._meta.get_fields()}
        if model.__name__.startswith("Historical") or "last_cached_at" not in fields:
            continue
        prefix = "activity__" if "activity" in fields else "parent__activity__"
        model.objects.filter(
            **{f"{prefix}change_rate__name": "exponential", f"{prefix}project__is_finalized": False}
        ).update(
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
        migrations.RunPython(invalidate_exponential_caches, migrations.RunPython.noop),
    ]
