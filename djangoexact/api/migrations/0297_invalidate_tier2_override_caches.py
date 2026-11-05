from django.db import migrations
from django.db.models import Q

FUEL_TIER_2_FIELDS = [f"energy_ef_{gas}_t2_{scenario}" for gas in ("co2", "ch4", "n2o") for scenario in ("start", "w", "wo")]
ANNUAL_FIELDS = [
    "minor_land_use_type_start",
    "minor_land_use_type_w",
    "minor_land_use_type_wo",
    "crop_yield_t2_w",
    "crop_yield_t2_wo",
]


def any_set(fields):
    q = Q()
    for field in fields:
        q |= Q(**{f"{field}__isnull": False})
    return q


def activity_prefix(fields):
    return "activity" if "activity" in fields else "parent__activity"


def invalidate_tier2_override_caches(apps, schema_editor):
    """Fuel tier 2 emission factors lost to the IPCC default, and annual cropland minor seasons were
    always booked as burned with their tier 2 yield ignored (start also read the w/wo main yield).
    Cached results of non-finalized activities that use any of these inputs are stale. Finalized
    projects are left alone: their results must not move."""
    models = [
        m
        for m in apps.get_app_config("api").get_models()
        if not m.__name__.startswith("Historical") and "last_cached_at" in {f.name for f in m._meta.get_fields()}
    ]

    activity_ids = set()
    for model in models:
        fields = {f.name for f in model._meta.get_fields()}
        if set(FUEL_TIER_2_FIELDS) <= fields:
            q = any_set(FUEL_TIER_2_FIELDS)
        elif model.__name__ == "AnnualCropland":
            q = any_set(ANNUAL_FIELDS)
        else:
            continue
        activity_ids.update(model.objects.filter(q).values_list(f"{activity_prefix(fields)}__id", flat=True))

    if not activity_ids:
        return

    for model in models:
        prefix = activity_prefix({f.name for f in model._meta.get_fields()})
        model.objects.filter(**{f"{prefix}__id__in": activity_ids, f"{prefix}__project__is_finalized": False}).update(
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
        migrations.RunPython(invalidate_tier2_override_caches, migrations.RunPython.noop),
    ]
