from django.db import migrations

# Replaces the 0 placeholder from 0066 with the values in the GWP_Refrigerants
# reference sheet (IPCC AR5 WG1 Table 8.7 note b for AR5). SAR and AR4 do not
# split CH4 by origin, so their fossil value equals ch4.
CH4_FOSSIL = {
    "IPCC Second Assessment Report (SAR)": 21.0,
    "IPCC Fourth Assessment Report (AR4)": 25.0,
    "IPCC Fifth Assessment Report (AR5) without Climate Change Feedback": 30.0,
    "IPCC Fifth Assessment Report (AR5) with Climate Change Feedback": 36.0,
}

CACHE_FIELDS = (
    "last_cached_at",
    "cached_results_total",
    "cached_results_by_activity",
    "cached_results_by_gas",
    "cached_results_by_activity_by_gas",
    "cached_units_breakdown",
)


def set_ch4_fossil(apps, schema_editor):
    GlobalWarmingPotential = apps.get_model("ipcc", "GlobalWarmingPotential")
    changed_ids = []
    for name, value in CH4_FOSSIL.items():
        # .get() fails loudly if a set was renamed on this DB; filter().update() would skip it silently.
        gwp = GlobalWarmingPotential.objects.get(name=name)
        if gwp.ch4_fossil != value:
            gwp.ch4_fossil = value
            gwp.save(update_fields=["ch4_fossil"])
            changed_ids.append(gwp.pk)
    if changed_ids:
        invalidate_caches(apps, changed_ids)


def invalidate_caches(apps, gwp_ids):
    """Null cached results of open projects on the changed GWP sets.

    Cached results do not expire on a reference-data change. Finalized projects
    are left alone, as in scripts/invalidate_results_cache.py. Projects with a
    Tier 2 fossil CH4 override are unaffected by the change.
    """
    Project = apps.get_model("api", "Project")
    project_ids = list(
        Project.objects.filter(gw_potential_id__in=gwp_ids, is_finalized=False, gwp_ch4_fossil_t2__isnull=True).values_list("pk", flat=True)
    )
    if not project_ids:
        return
    for model in apps.get_app_config("api").get_models():
        field_names = {f.name for f in model._meta.get_fields()}
        if "last_cached_at" not in field_names or model.__name__.startswith("Historical"):
            continue
        lookup = "activity__project_id__in" if "activity" in field_names else "parent__activity__project_id__in"
        model.objects.filter(**{lookup: project_ids}).update(**{f: None for f in CACHE_FIELDS if f in field_names})


class Migration(migrations.Migration):

    dependencies = [
        ("ipcc", "0066_globalwarmingpotential_fill_null_ch4_fossil"),
        ("api", "0295_project_guided_step"),
    ]

    operations = [
        migrations.RunPython(set_ch4_fossil, migrations.RunPython.noop),
    ]
