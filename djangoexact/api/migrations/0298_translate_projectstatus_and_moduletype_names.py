from django.db import migrations

LANGS = ("fr", "es", "ru")

# Keyed by value: unique and identical across environments, unlike the ids.
PROJECT_STATUSES = {
    0: ("Conception", "Diseño", "Разработка"),
    1: ("Mise en œuvre", "Ejecución", "Реализация"),
    2: ("Mi-parcours de la mise en œuvre", "Ejecución a medio término", "Среднесрочный этап реализации"),
    3: ("Évaluation finale", "Evaluación final", "Итоговая оценка"),
}

# Keyed by name_en. None leaves the language alone (already translated everywhere).
MODULE_TYPES = {
    "Annual Cropland": ("Cultures annuelles", "Cultivos anuales", "Однолетние посевы"),
    "Perennial Cropland": ("Cultures pérennes", "Cultivos perennes", "Многолетние сельскохозяйственные угодья"),
    "Flooded Rice": ("Riz inondé", "Arroz inundado", "Затопленный рис"),
    "Grassland": ("Prairies", "Pastizales", "Пастбищные угодья"),
    "Settlement": ("Établissements", "Asentamientos", "Поселения"),
    "Other Land": ("Autres terres", "Otras tierras", "Прочие земли"),
    "Set Aside": ("Terres mises en jachère", "Tierras en barbecho", "Земли под паром"),
    "Organic Soil": ("Sols organiques", "Suelos orgánicos", "Органические почвы"),
    "Plantation": ("Plantation", "Plantación", "Плантация"),
    "Transport": (None, None, "Транспорт"),
    "Packaging": (None, None, "Упаковка"),
    "Storage": (None, None, "Хранение"),
    "Processing": (None, "Procesamiento", "Переработка"),
    "Transport Entry": (None, "Entrada de Transporte", "Ввод данных: Транспорт"),
    "Packaging Entry": (None, "Entrada de Embalaje", "Ввод данных: Упаковка"),
    "Processing Entry": (None, "Entrada de Procesamiento", "Ввод данных: Переработка"),
    "Storage Entry": (None, "Entrada de Almacenamiento", "Ввод данных: Хранение"),
    "Energy Entry": (None, "Entrada de Energía", "Ввод данных: Энергия"),
    "Input Entry": (None, None, "Ввод данных: Входные ресурсы"),
}


def _fill(row, values):
    """Set a translation only where it is blank or a copy of the English name, so
    a translation someone already entered is never overwritten."""
    english = (row.name_en or "").strip()
    for lang, value in zip(LANGS, values):
        current = (getattr(row, f"name_{lang}") or "").strip()
        if value and (not current or current == english):
            setattr(row, f"name_{lang}", value)


def forwards(apps, schema_editor):
    ProjectStatus = apps.get_model("api", "ProjectStatus")
    for status in ProjectStatus.objects.all():
        status.name_en = status.name_en or status.name
        _fill(status, PROJECT_STATUSES.get(status.value, ()))
        status.save()

    ModuleType = apps.get_model("api", "ModuleType")
    for module_type in ModuleType.objects.all():
        _fill(module_type, MODULE_TYPES.get((module_type.name_en or "").strip(), ()))
        # Several French names were imported with a trailing newline.
        for lang in ("en",) + LANGS:
            field = f"name_{lang}"
            value = getattr(module_type, field)
            if value:
                setattr(module_type, field, value.strip())
        module_type.save()


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0297_projectstatus_translations"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
