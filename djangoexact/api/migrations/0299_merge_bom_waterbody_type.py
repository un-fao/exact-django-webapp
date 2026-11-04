from django.db import migrations

BOM = "\ufeff"


def merge_bom_waterbody_types(apps, schema_editor):
    """A CSV import left a "\ufeffFreshwater Pond" row next to the clean one. It has no emission
    factors, so any module pointing at it failed Tier 1. Repoint every reference to the clean row
    before deleting it: the FKs cascade, so a plain delete would drop users' waterbody modules."""
    WaterbodyType = apps.get_model("api", "WaterbodyType")
    EmissionFactor = apps.get_model("ipcc", "OtherConstructedWaterbodiesEmissionFactor")
    for dup in WaterbodyType.objects.filter(name__startswith=BOM):
        clean = WaterbodyType.objects.filter(name=dup.name.lstrip(BOM)).first()
        if clean is None:
            dup.name = dup.name.lstrip(BOM)
            dup.name_en = (dup.name_en or "").lstrip(BOM) or dup.name
            dup.save()
            continue
        # The calculator does .get(climate, moisture, type): drop factors the clean row already has.
        for ef in EmissionFactor.objects.filter(waterbody_type=dup):
            if EmissionFactor.objects.filter(waterbody_type=clean, climate_id=ef.climate_id, moisture_id=ef.moisture_id).exists():
                ef.delete()
            else:
                ef.waterbody_type = clean
                ef.save(update_fields=["waterbody_type"])
        for model in apps.get_app_config("api").get_models():
            for field in model._meta.concrete_fields:
                if field.is_relation and field.related_model is WaterbodyType:
                    model.objects.filter(**{field.attname: dup.pk}).update(**{field.attname: clean.pk})
        dup.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0298_invalidate_waterbody_caches"),
        ("ipcc", "0069_trophicstatefactor_ipcc_recommended_values"),
    ]

    operations = [
        migrations.RunPython(merge_bom_waterbody_types, migrations.RunPython.noop),
    ]
