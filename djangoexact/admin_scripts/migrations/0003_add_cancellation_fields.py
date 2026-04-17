from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_scripts', '0002_add_progress_to_computationjob'),
    ]

    operations = [
        migrations.AddField(
            model_name='computationjob',
            name='pid',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='computationjob',
            name='cloud_run_execution_name',
            field=models.CharField(blank=True, default='', max_length=512),
        ),
        migrations.AlterField(
            model_name='computationjob',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('running', 'Running'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
