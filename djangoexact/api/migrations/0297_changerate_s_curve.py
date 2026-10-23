"""Add the "s-curve" change rate to databases that were seeded before it existed.

Fresh databases get it from api/fixtures/changerate.json (pk 4). Deployed databases never
reload fixtures, so without this row the new dynamic would not appear in the dropdown.
"""

from django.db import migrations


def add_s_curve(apps, schema_editor):
    ChangeRate = apps.get_model("api", "ChangeRate")
    if not ChangeRate.objects.filter(name="s-curve").exists():
        ChangeRate.objects.create(name="s-curve", value=0.5001)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0296_projectmembership_unique_user_project"),
    ]

    # No reverse delete: Activity.change_rate cascades, so removing the row would delete activities.
    operations = [
        migrations.RunPython(add_s_curve, migrations.RunPython.noop),
    ]
