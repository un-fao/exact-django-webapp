# Generated migration for ModuleTestRun + ComputationJob.max_rows
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('admin_scripts', '0003_add_cancellation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='computationjob',
            name='max_rows',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Row cap for compute_module_slice. Null means runner default (10000).',
                null=True,
            ),
        ),
        migrations.CreateModel(
            name='ModuleTestRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('skipped', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('jobs', models.ManyToManyField(blank=True, related_name='test_runs', to='admin_scripts.computationjob')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_test_runs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
