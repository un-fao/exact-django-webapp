# Hand-written to avoid folding in the pre-existing, unrelated ef_source AlterField drift
# that makemigrations reports for largefishery/smallfishery and their historical models.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0289_asyncjob'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalproject',
            name='results_stamp',
            field=models.BigIntegerField(default=0, verbose_name='results_stamp'),
        ),
        migrations.AddField(
            model_name='project',
            name='results_stamp',
            field=models.BigIntegerField(default=0, verbose_name='results_stamp'),
        ),
        migrations.CreateModel(
            name='ProjectResultCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cache_key', models.CharField(max_length=64)),
                ('results_stamp', models.BigIntegerField()),
                ('schema_version', models.PositiveIntegerField()),
                ('payload', models.JSONField()),
                ('computed_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='result_caches', to='api.project')),
            ],
            options={
                'unique_together': {('project', 'cache_key')},
            },
        ),
    ]
