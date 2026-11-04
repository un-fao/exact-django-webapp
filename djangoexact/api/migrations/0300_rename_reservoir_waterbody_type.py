from django.db import migrations

# fr / es / ru are machine drafts.
OLD_NAME_EN = "Flooded Land (Reservoir)"
NEW = {
    "name": "Reservoir (flooded land)",
    "name_en": "Reservoir (flooded land)",
    "name_fr": "Réservoir (terres inondées)",
    "name_es": "Embalse (tierras inundadas)",
    "name_ru": "Водохранилище (затопленные земли)",
}
OLD = {
    "name": OLD_NAME_EN,
    "name_en": OLD_NAME_EN,
    "name_fr": "Terres inondées (réservoir)",
    "name_es": "Tierras inundadas (embalse)",
    "name_ru": "Затопленные земли (водохранилище)",
}


def rename(apps, schema_editor):
    apps.get_model("api", "WaterbodyType").objects.filter(is_reservoir=True, name_en=OLD_NAME_EN).update(**NEW)


def unrename(apps, schema_editor):
    apps.get_model("api", "WaterbodyType").objects.filter(is_reservoir=True, name_en=NEW["name_en"]).update(**OLD)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0299_merge_bom_waterbody_type"),
    ]

    operations = [
        migrations.RunPython(rename, unrename),
    ]
