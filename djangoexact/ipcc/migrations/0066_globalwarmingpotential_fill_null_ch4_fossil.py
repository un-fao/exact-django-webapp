from django.db import migrations

# ipcc_dump.py matched GWP rows by the "(AR5)" token, so both AR5 CSV rows
# updated the same row and "AR5 with Climate Change Feedback" kept a NULL
# ch4_fossil. Charcoal and peat then crashed the energy, fuel and irrigation
# math. 0 mirrors scripts/ipcc_data/GlobalWarmingPotential.csv; the IPCC value
# (36, AR5 WG1 Table 8.7 note b) is pending domain confirmation.
# Only NULLs are touched, so a value set by hand is never overwritten.


def fill_null_ch4_fossil(apps, schema_editor):
    GlobalWarmingPotential = apps.get_model("ipcc", "GlobalWarmingPotential")
    GlobalWarmingPotential.objects.filter(ch4_fossil__isnull=True).update(ch4_fossil=0.0)


class Migration(migrations.Migration):

    dependencies = [
        ("ipcc", "0065_uncertainty_ranges"),
    ]

    operations = [
        migrations.RunPython(fill_null_ch4_fossil, migrations.RunPython.noop),
    ]
