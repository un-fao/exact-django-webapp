from django.db import migrations

# IPCC 2019 Refinement Vol. 4 Ch. 7 Table 7.11 recommended values; the old rows held range midpoints.
RECOMMENDED = {"Eutrophic": (9.9, 10.0), "Hypereutrophic": (26.95, 25.0)}


def set_recommended(apps, schema_editor):
    TrophicStateFactor = apps.get_model("ipcc", "TrophicStateFactor")
    for name, (old, new) in RECOMMENDED.items():
        # Only the shipped midpoint is replaced, so an admin-edited value survives.
        TrophicStateFactor.objects.filter(trophic_type__name_en=name, value=old).update(value=new)


def unset_recommended(apps, schema_editor):
    TrophicStateFactor = apps.get_model("ipcc", "TrophicStateFactor")
    for name, (old, new) in RECOMMENDED.items():
        TrophicStateFactor.objects.filter(trophic_type__name_en=name, value=new).update(value=old)


class Migration(migrations.Migration):

    dependencies = [
        ("ipcc", "0068_reservoir_emission_factors"),
        ("api", "0297_waterbody_reservoir"),
    ]

    operations = [
        migrations.RunPython(set_recommended, unset_recommended),
    ]
