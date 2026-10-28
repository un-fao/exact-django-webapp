from django.db import migrations
from django.db.models import Q

CACHE_FIELDS = (
    "last_cached_at",
    "cached_results_total",
    "cached_results_by_activity",
    "cached_results_by_gas",
    "cached_results_by_activity_by_gas",
    "cached_units_breakdown",
)


def invalidate_input_caches(apps, schema_editor):
    """Inputs N2O now uses the project's GWP instead of a fixed 265, so cached results of non-finalized
    projects whose effective N2O GWP is not 265 are stale. Finalized projects are left alone: their results
    must not move."""
    Project = apps.get_model("api", "Project")
    effective_n2o_is_265 = Q(gwp_n2o_t2=265) | Q(gwp_n2o_t2__isnull=True, gw_potential__n2o=265)
    project_ids = list(Project.objects.filter(is_finalized=False).exclude(effective_n2o_is_265).values_list("pk", flat=True))
    if not project_ids:
        return
    cleared = {f: None for f in CACHE_FIELDS}
    apps.get_model("api", "Input").objects.filter(activity__project_id__in=project_ids).update(**cleared)
    apps.get_model("api", "InputEntry").objects.filter(parent__activity__project_id__in=project_ids).update(**cleared)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0298_translate_projectstatus_and_moduletype_names"),
        ("ipcc", "0067_globalwarmingpotential_ch4_fossil_reference_values"),
    ]

    operations = [
        migrations.RunPython(invalidate_input_caches, migrations.RunPython.noop),
    ]
