"""Realign the fishery `ef_source` field state with the models.

Pre-existing drift: migration 0286 created the field as `ef_source_t2` with
`verbose_name='ef_source_t2'`, and 0288 renamed the field without touching the
verbose_name. These operations are verbatim `makemigrations` output. They
carry no SQL: `verbose_name` is model metadata only.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0289_asyncjob'),
    ]

    operations = [

        migrations.AlterField(
            model_name='historicallargefishery',
            name='ef_source',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='api.emissionfactorsource'),
        ),
        migrations.AlterField(
            model_name='historicalsmallfishery',
            name='ef_source',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='api.emissionfactorsource'),
        ),
        migrations.AlterField(
            model_name='largefishery',
            name='ef_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.emissionfactorsource'),
        ),
        migrations.AlterField(
            model_name='smallfishery',
            name='ef_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.emissionfactorsource'),
        ),
    ]
