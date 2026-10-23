"""Default CO2, CH4 and N2O emission factors for the transport modes added in api 0298.

Sources (IPCC 2006 Guidelines, Volume 2):
- Off-road by sector: chapter 3, Table 3.3.1 (motor gasoline 4-stroke has no
  forestry value there, so that combination is not offered).
- Railways: chapter 3, Table 3.4.1 (diesel).
- Water-borne navigation: chapter 3, Table 3.5.2 (CO2) and Table 3.5.3
  (CH4/N2O, ocean-going ships).
- Civil aviation: chapter 3, Table 3.6.4 (CO2) and Table 3.6.5 (CH4/N2O).
- Net calorific values: chapter 1, Table 1.2.

Values are per unit of the fuel type: kg/TJ x NCV (TJ/Gg) / 1e6 gives t/t, and
the m3 rows also multiply by the densities EX-ACT already uses for the same
fuels (diesel 0.837 t/m3, gasoline 0.741 t/m3), so they line up with the
existing off-road and mobile rows. Fuels with no EX-ACT density (residual
fuel oil, aviation gasoline, jet kerosene) are entered in tonnes.
CO2 for 2-stroke gasoline uses the Table 3.3.1 default of 69 300 kg/TJ.
"""

from django.db import migrations

D = 43.0 * 0.837 / 1e6
G = 44.3 * 0.741 / 1e6

# (fuel use type, fuel type, co2, ch4, n2o), per unit of the fuel type.
FACTORS = [
    ("Off-Road Forestry", "Diesel", 74100 * D, 4.15 * D, 28.6 * D),
    ("Off-Road Forestry", "Gasoline (2-stroke)", 69300 * G, 170 * G, 0.4 * G),
    ("Off-Road Industry", "Diesel", 74100 * D, 4.15 * D, 28.6 * D),
    ("Off-Road Industry", "Gasoline (4-stroke)", 69300 * G, 50 * G, 2 * G),
    ("Off-Road Industry", "Gasoline (2-stroke)", 69300 * G, 130 * G, 0.4 * G),
    ("Off-Road Household", "Diesel", 74100 * D, 4.15 * D, 28.6 * D),
    ("Off-Road Household", "Gasoline (4-stroke)", 69300 * G, 120 * G, 2 * G),
    ("Off-Road Household", "Gasoline (2-stroke)", 69300 * G, 180 * G, 0.4 * G),
    ("Railways", "Diesel", 74100 * D, 4.15 * D, 28.6 * D),
    ("Water-Borne Navigation", "Gasoil/Diesel Oil", 74100 * D, 7 * D, 2 * D),
    ("Water-Borne Navigation", "Residual Fuel Oil", 77400 * 40.4 / 1e6, 7 * 40.4 / 1e6, 2 * 40.4 / 1e6),
    ("Civil Aviation", "Aviation Gasoline", 70000 * 44.3 / 1e6, 0.5 * 44.3 / 1e6, 2 * 44.3 / 1e6),
    ("Civil Aviation", "Jet Kerosene", 71500 * 44.1 / 1e6, 0.5 * 44.1 / 1e6, 2 * 44.1 / 1e6),
]


def add_factors(apps, schema_editor):
    FuelType = apps.get_model("api", "FuelType")
    EnergyDefaultEmissionFactor = apps.get_model("ipcc", "EnergyDefaultEmissionFactor")

    for use_type_name, fuel_name, co2, ch4, n2o in FACTORS:
        fuel_type = FuelType.objects.filter(name=fuel_name, fuel_use_type__name=use_type_name).first()
        if fuel_type is None:
            continue
        EnergyDefaultEmissionFactor.objects.get_or_create(
            fuel_type=fuel_type,
            fuel_use_type=fuel_type.fuel_use_type,
            defaults={"co2": round(co2, 12), "ch4": round(ch4, 12), "n2o": round(n2o, 12)},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("ipcc", "0067_globalwarmingpotential_ch4_fossil_reference_values"),
        ("api", "0298_fuelusetype_transport_modes"),
    ]

    operations = [
        migrations.RunPython(add_factors, migrations.RunPython.noop),
    ]
