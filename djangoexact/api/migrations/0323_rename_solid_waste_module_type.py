from django.db import migrations

OLD = {
    "name": "Solid Waste",
    "name_en": "Solid Waste",
    "name_fr": "Déchets solides",
    "name_es": "Residuos sólidos",
    "name_ru": "Твёрдые отходы",
}
NEW = {
    "name": "Food Loss and Waste",
    "name_en": "Food Loss and Waste",
    "name_fr": "Pertes et gaspillages alimentaires",
    "name_es": "Pérdida y desperdicio de alimentos",
    "name_ru": "Продовольственные потери и пищевые отходы",
}


def rename(names):
    def apply(apps, schema_editor):
        apps.get_model("api", "ModuleType").objects.filter(class_name="SolidWaste").update(**names)

    return apply


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0322_invalidate_hwp_source_caches"),
    ]

    operations = [
        migrations.RunPython(rename(NEW), rename(OLD)),
    ]
