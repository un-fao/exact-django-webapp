from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0289_asyncjob'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='historicalcustomuser',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
