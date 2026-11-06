from django.db import migrations, models


class Migration(migrations.Migration):
    """IPCC 2006 Table 6.4 lists AGB and total (above + below ground) biomass; the "bgb" columns held the total."""

    dependencies = [
        ("ipcc", "0067_globalwarmingpotential_ch4_fossil_reference_values"),
    ]

    operations = [
        migrations.RenameField(model_name="grasslandbiomass", old_name="bgb_t_dm_ha", new_name="total_biomass_t_dm_ha"),
        migrations.RenameField(model_name="grasslandbiomass", old_name="bgb_t_c_ha", new_name="total_biomass_t_c_ha"),
        migrations.AlterField(
            model_name="grasslandbiomass",
            name="total_biomass_t_dm_ha",
            field=models.FloatField(verbose_name="Total biomass tdm/ha"),
        ),
        migrations.AlterField(
            model_name="grasslandbiomass",
            name="total_biomass_t_c_ha",
            field=models.FloatField(verbose_name="Total biomass tC/ha"),
        ),
    ]
