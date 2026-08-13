"""Database uniqueness behind the reference-data natural keys.

Backs `api/natural_keys.py`. Each constraint is on `name_en`, never `unique=True`
on the translated `name`: modeltranslation copies the wrapped field's __dict__
onto every language column, so `unique=True` would also constrain name_es,
name_fr and name_ru, and two rows sharing a translation would fail here.

`api.Unit` is deliberately absent. `manage.py check_reference_natural_keys` found
66 duplicate and 100 blank-named Unit rows in the shipped offline database, so no
uniqueness guarantee can be asserted for it without deleting reference data. See
.planning/quick/260813-fvj-when-import-exporting-from-online-tool-t/260813-fvj-DUPLICATES.md.

Run `manage.py check_reference_natural_keys` against the target database before
applying this migration. It has been validated against the committed fixtures and
the shipped offline snapshot only, never against production.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0289_asyncjob'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='climate',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_climate_name_en'),
        ),
        migrations.AddConstraint(
            model_name='firetype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_fire_type_name_en'),
        ),
        migrations.AddConstraint(
            model_name='foresttype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_forest_type_name_en'),
        ),
        migrations.AddConstraint(
            model_name='fueltype',
            constraint=models.UniqueConstraint(fields=('name_en', 'fuel_use_type', 'macro_fuel_type'), name='uniq_fuel_type_name_en_use_macro', nulls_distinct=False),
        ),
        migrations.AddConstraint(
            model_name='grasslandmanagementtype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_grassland_mgmt_name_en'),
        ),
        migrations.AddConstraint(
            model_name='landusetype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_land_use_type_name_en'),
        ),
        migrations.AddConstraint(
            model_name='livestockproductiontype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_livestock_prod_name_en'),
        ),
        migrations.AddConstraint(
            model_name='manuremanagementtype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_manure_mgmt_name_en'),
        ),
        migrations.AddConstraint(
            model_name='moisture',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_moisture_name_en'),
        ),
        migrations.AddConstraint(
            model_name='organicamendmenttype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_organic_amendment_name_en'),
        ),
        migrations.AddConstraint(
            model_name='projectstatus',
            constraint=models.UniqueConstraint(fields=('name',), name='uniq_project_status_name'),
        ),
        migrations.AddConstraint(
            model_name='residuemanagementtype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_residue_mgmt_type_name_en'),
        ),
        migrations.AddConstraint(
            model_name='settlementtype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_settlement_type_name_en'),
        ),
        migrations.AddConstraint(
            model_name='soiltype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_soil_type_name_en'),
        ),
        migrations.AddConstraint(
            model_name='trophictype',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_trophic_type_name_en'),
        ),
        migrations.AddConstraint(
            model_name='watermanagementtypeaftercultivation',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_water_mgmt_after_name_en'),
        ),
        migrations.AddConstraint(
            model_name='watermanagementtypebeforecultivation',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_water_mgmt_before_name_en'),
        ),
    ]
