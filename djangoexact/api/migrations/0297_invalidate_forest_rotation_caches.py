from django.db import migrations
from django.db.models import Q


def invalidate_forest_rotation_caches(apps, schema_editor):
    """Rotation emissions were booked twice in math_model, so cached results of non-finalized forest modules
    with a rotation are stale. Finalized projects are left alone: their results must not move."""
    ForestManagement = apps.get_model("api", "ForestManagement")
    has_rotation = Q(rotation_length_yrs_start__gt=0) | Q(rotation_length_yrs_w__gt=0) | Q(rotation_length_yrs_wo__gt=0)
    ForestManagement.objects.filter(has_rotation, activity__project__is_finalized=False).update(
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
        migrations.RunPython(invalidate_forest_rotation_caches, migrations.RunPython.noop),
    ]
