"""Value-chain stage tag on energy entries.

Reference rows are only inserted into a database that already holds the fuel
reference data. A fresh database gets them from the fixtures instead
(load_reference_data runs after migrate), so the insert would only collide
with the fixture primary keys there.
"""

import django.db.models.deletion
from django.db import migrations, models

# (en, fr, es, ru). fr/es/ru are machine drafts.
VALUE_CHAIN_STAGES = [
    ("Upstream", "Amont", "Aguas arriba", "Начальное звено"),
    ("Fertilizers manufacturing", "Fabrication d'engrais", "Fabricación de fertilizantes", "Производство удобрений"),
    ("Pesticides manufacturing", "Fabrication de pesticides", "Fabricación de plaguicidas", "Производство пестицидов"),
    ("On-farm", "Sur l'exploitation", "En la explotación", "На ферме"),
    ("Downstream", "Aval", "Aguas abajo", "Конечное звено"),
    ("Food processing", "Transformation alimentaire", "Procesamiento de alimentos", "Переработка пищевых продуктов"),
    ("Food packaging", "Emballage alimentaire", "Envasado de alimentos", "Упаковка пищевых продуктов"),
    ("Food retail", "Commerce de détail alimentaire", "Venta minorista de alimentos", "Розничная торговля продуктами питания"),
    ("Household consumption", "Consommation des ménages", "Consumo de los hogares", "Потребление домохозяйств"),
]


def _names(translations):
    en, fr, es, ru = translations
    return {"name": en, "name_en": en, "name_fr": fr, "name_es": es, "name_ru": ru}


def add_value_chain_stages(apps, schema_editor):
    if not apps.get_model("api", "FuelUseType").objects.filter(name="Off-Road").exists():
        return
    ValueChainStage = apps.get_model("api", "ValueChainStage")
    for row in VALUE_CHAIN_STAGES:
        ValueChainStage.objects.get_or_create(name=row[0], defaults=_names(row))


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0296_projectmembership_unique_user_project'),
    ]

    operations = [
        migrations.CreateModel(
            name='ValueChainStage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('name_en', models.CharField(max_length=100, null=True, unique=True)),
                ('name_fr', models.CharField(max_length=100, null=True, unique=True)),
                ('name_es', models.CharField(max_length=100, null=True, unique=True)),
                ('name_ru', models.CharField(max_length=100, null=True, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='energyentry',
            name='value_chain_stage',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='energy_entries', to='api.valuechainstage'),
        ),
        migrations.AddField(
            model_name='historicalenergyentry',
            name='value_chain_stage',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='api.valuechainstage'),
        ),
        migrations.RunPython(add_value_chain_stages, migrations.RunPython.noop),
    ]
