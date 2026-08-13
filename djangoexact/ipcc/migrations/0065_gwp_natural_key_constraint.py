"""Database uniqueness behind the GlobalWarmingPotential natural key.

Backs `api/natural_keys.py`. This is the highest-impact entry in that registry:
GWP primary key ranges are fully disjoint between installations (committed
fixtures 8-12, shipped offline database 1-5) and `Project.gw_potential` is NOT
NULL, so it is what makes every online-to-offline `.exactproject` import fail at
the first row.

Constrained on `name_en`, never `unique=True` on the translated `name`, which
modeltranslation would propagate to name_es, name_fr and name_ru.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ipcc', '0064_cropnitrousestimationdefaultfactor_comment'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='globalwarmingpotential',
            constraint=models.UniqueConstraint(fields=('name_en',), name='uniq_gwp_name_en'),
        ),
    ]
