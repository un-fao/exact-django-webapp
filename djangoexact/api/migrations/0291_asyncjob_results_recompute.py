# Hand-written, matching the style of 0289_asyncjob.py and 0290_projectresultcache.py.
# No-op at the database level (kind is a CharField, not backed by a Postgres enum), but
# Django requires the AlterField for migration state consistency with the new choice.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0290_projectresultcache'),
    ]

    operations = [
        migrations.AlterField(
            model_name='asyncjob',
            name='kind',
            field=models.CharField(choices=[('report', 'Report generation'), ('project_copy', 'Project copy'), ('results_recompute', 'Results recompute')], max_length=32),
        ),
    ]
