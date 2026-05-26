# Generated for issue #133: Add ef_source_t2 and country_t2 to Small/Large Fisheries

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0285_annualcropland_faostat_year_t2'),
    ]

    operations = [
        migrations.RenameField(
            model_name='smallfishery',
            old_name='inshore_ice_production_country_t2',
            new_name='country_t2',
        ),
        migrations.RenameField(
            model_name='historicalsmallfishery',
            old_name='inshore_ice_production_country_t2',
            new_name='country_t2',
        ),
        migrations.RenameField(
            model_name='largefishery',
            old_name='inshore_ice_production_country_t2',
            new_name='country_t2',
        ),
        migrations.RenameField(
            model_name='historicallargefishery',
            old_name='inshore_ice_production_country_t2',
            new_name='country_t2',
        ),
        migrations.AlterField(
            model_name='smallfishery',
            name='country_t2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.country', verbose_name='country_t2'),
        ),
        migrations.AlterField(
            model_name='historicalsmallfishery',
            name='country_t2',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='api.country', verbose_name='country_t2'),
        ),
        migrations.AlterField(
            model_name='largefishery',
            name='country_t2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.country', verbose_name='country_t2'),
        ),
        migrations.AlterField(
            model_name='historicallargefishery',
            name='country_t2',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='api.country', verbose_name='country_t2'),
        ),
        migrations.AddField(
            model_name='smallfishery',
            name='ef_source_t2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.emissionfactorsource', verbose_name='ef_source_t2'),
        ),
        migrations.AddField(
            model_name='historicalsmallfishery',
            name='ef_source_t2',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='api.emissionfactorsource', verbose_name='ef_source_t2'),
        ),
        migrations.AddField(
            model_name='largefishery',
            name='ef_source_t2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.emissionfactorsource', verbose_name='ef_source_t2'),
        ),
        migrations.AddField(
            model_name='historicallargefishery',
            name='ef_source_t2',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='api.emissionfactorsource', verbose_name='ef_source_t2'),
        ),
    ]
