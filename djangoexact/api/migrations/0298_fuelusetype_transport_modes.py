"""Off-road sectors, railways, water-borne navigation and civil aviation as fuel use types (NEXT, List sheet H107:O118).

Emission factors for these fuel types are added in ipcc 0068. Rows are only
inserted into a database that already holds the fuel reference data; a fresh
database gets them from the fixtures (load_reference_data runs after migrate),
where an insert would collide with the fixture primary keys.
"""

from django.db import migrations

FUEL_USE_TYPES = [
    ("Off-Road Forestry", "Hors-route - Foresterie", "Fuera de carretera - Silvicultura", "Внедорожная техника - лесное хозяйство"),
    ("Off-Road Industry", "Hors-route - Industrie", "Fuera de carretera - Industria", "Внедорожная техника - промышленность"),
    ("Off-Road Household", "Hors-route - Ménages", "Fuera de carretera - Hogares", "Внедорожная техника - домохозяйства"),
    ("Railways", "Chemins de fer", "Ferrocarriles", "Железнодорожный транспорт"),
    ("Water-Borne Navigation", "Navigation", "Navegación", "Водный транспорт"),
    ("Civil Aviation", "Aviation civile", "Aviación civil", "Гражданская авиация"),
]

TONNE_UNIT = "t/yr"

# (fuel use type, (en, fr, es, ru), unit). "m3:<existing fuel>" reuses the unit row
# of that existing off-road or mobile fuel type, "t/yr" is the new tonne unit.
FUEL_TYPES = [
    ("Off-Road Forestry", ("Diesel", "Diesel", "Diesel", "Дизель"), "m3:Diesel"),
    ("Off-Road Forestry", ("Gasoline (2-stroke)", "Essence (2 temps)", "Gasolina (2-tiempos)", "Бензин (2-тактный)"), "m3:Gasoline (2-stroke)"),
    ("Off-Road Industry", ("Diesel", "Diesel", "Diesel", "Дизель"), "m3:Diesel"),
    ("Off-Road Industry", ("Gasoline (4-stroke)", "Essence (4 temps)", "Gasolina (4-tiempos)", "Бензин (4-тактный)"), "m3:Gasoline (4-stroke)"),
    ("Off-Road Industry", ("Gasoline (2-stroke)", "Essence (2 temps)", "Gasolina (2-tiempos)", "Бензин (2-тактный)"), "m3:Gasoline (2-stroke)"),
    ("Off-Road Household", ("Diesel", "Diesel", "Diesel", "Дизель"), "m3:Diesel"),
    ("Off-Road Household", ("Gasoline (4-stroke)", "Essence (4 temps)", "Gasolina (4-tiempos)", "Бензин (4-тактный)"), "m3:Gasoline (4-stroke)"),
    ("Off-Road Household", ("Gasoline (2-stroke)", "Essence (2 temps)", "Gasolina (2-tiempos)", "Бензин (2-тактный)"), "m3:Gasoline (2-stroke)"),
    ("Railways", ("Diesel", "Diesel", "Diesel", "Дизель"), "m3:Diesel"),
    ("Water-Borne Navigation", ("Gasoil/Diesel Oil", "Gasoil / huile diesel", "Gasóleo/Diésel", "Газойль/дизельное топливо"), "m3:Gasoil/Diesel Oil"),
    ("Water-Borne Navigation", ("Residual Fuel Oil", "Fioul résiduel", "Fuelóleo residual", "Остаточное жидкое топливо"), TONNE_UNIT),
    ("Civil Aviation", ("Aviation Gasoline", "Essence aviation", "Gasolina de aviación", "Авиационный бензин"), TONNE_UNIT),
    ("Civil Aviation", ("Jet Kerosene", "Kérosène carburéacteur", "Queroseno para motores a reacción", "Керосин для реактивных двигателей"), TONNE_UNIT),
]

# The unit rows the existing per-fuel units point to: off-road for Diesel and
# gasoline, road (Mobile) for Gasoil/Diesel Oil.
UNIT_SOURCE_USE_TYPE = {"Diesel": "Off-Road", "Gasoline (2-stroke)": "Off-Road", "Gasoline (4-stroke)": "Off-Road", "Gasoil/Diesel Oil": "Mobile"}


def _names(translations):
    en, fr, es, ru = translations
    return {"name": en, "name_en": en, "name_fr": fr, "name_es": es, "name_ru": ru}


def add_transport_modes(apps, schema_editor):
    FuelUseType = apps.get_model("api", "FuelUseType")
    if not FuelUseType.objects.filter(name="Off-Road").exists():
        return

    Unit = apps.get_model("api", "Unit")
    FuelType = apps.get_model("api", "FuelType")
    ParentFuelType = apps.get_model("api", "ParentFuelType")
    ModuleType = apps.get_model("api", "ModuleType")

    use_types = {}
    for row in FUEL_USE_TYPES:
        use_types[row[0]], _ = FuelUseType.objects.get_or_create(name=row[0], defaults=_names(row))

    tonne_unit = Unit.objects.filter(name=TONNE_UNIT).first() or Unit.objects.create(name=TONNE_UNIT)
    fuel_parent = ParentFuelType.objects.get(name="Fuel")
    transport_entry = ModuleType.objects.filter(class_name="TransportEntry").first()

    for use_type_name, translations, unit_ref in FUEL_TYPES:
        if unit_ref == TONNE_UNIT:
            unit = tonne_unit
        else:
            source_name = unit_ref.split(":", 1)[1]
            unit = FuelType.objects.get(name=source_name, fuel_use_type__name=UNIT_SOURCE_USE_TYPE[source_name]).unit
        fuel_type, created = FuelType.objects.get_or_create(
            name=translations[0],
            fuel_use_type=use_types[use_type_name],
            macro_fuel_type=None,
            defaults={**_names(translations), "parent_fuel_type": fuel_parent, "unit": unit},
        )
        if created and transport_entry:
            fuel_type.module_types.add(transport_entry)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0297_energyentry_value_chain_stage"),
    ]

    operations = [
        migrations.RunPython(add_transport_modes, migrations.RunPython.noop),
    ]
