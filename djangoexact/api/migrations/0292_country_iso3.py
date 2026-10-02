"""Add Country.iso3 and populate it from api/data/country_iso3.csv.

The CSV is keyed by ISO-3166-1 alpha-3 code and maps to Country.name values
copied verbatim from api/fixtures/country.json, so this uses an exact name
match (not iexact). Countries with no ISO3 mapping keep iso3=None; NULL is
allowed to repeat under the unique constraint (unlike "").
"""

import csv
from pathlib import Path

from django.db import migrations, models


def populate_iso3(apps, schema_editor):
    Country = apps.get_model("api", "Country")
    csv_path = Path(__file__).resolve().parents[1] / "data" / "country_iso3.csv"
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            Country.objects.filter(name=row["name"]).update(iso3=row["iso3"])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0291_alter_fishery_ef_source_verbose_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='country',
            name='iso3',
            field=models.CharField(blank=True, max_length=3, null=True, unique=True),
        ),
        migrations.RunPython(populate_iso3, migrations.RunPython.noop),
    ]
