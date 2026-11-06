from django.db import migrations

# Every model registered in api/translation.py and ipcc/translation.py.
TRANSLATED_MODELS = (
    ("api", "InvitationStatusType"),
    ("api", "GasType"),
    ("api", "ForestType"),
    ("api", "ForestConditionType"),
    ("api", "SiteLocationType"),
    ("api", "VegetationType"),
    ("api", "ActivityType"),
    ("api", "StatusType"),
    ("api", "ProjectStatus"),
    ("api", "LandUseType"),
    ("api", "SettlementType"),
    ("api", "SoilType"),
    ("api", "ExtractionSoilType"),
    ("api", "OrganicInputType"),
    ("api", "ResidueManagementType"),
    ("api", "WaterRegimeType"),
    ("api", "PreSeasonWaterRegimeType"),
    ("api", "OrganicAmendmentType"),
    ("api", "TillageManagementType"),
    ("api", "GrasslandManagementType"),
    ("api", "LivestockCategoryType"),
    ("api", "LivestockProductionType"),
    ("api", "ManureManagementType"),
    ("api", "ModuleType"),
    ("api", "FireType"),
    ("api", "PeatType"),
    ("api", "WaterbodyType"),
    ("api", "TrophicType"),
    ("api", "FisheryType"),
    ("api", "LargeFisheryGearType"),
    ("api", "SmallFisheryGearType"),
    ("api", "FishType"),
    ("api", "MacroFuelType"),
    ("api", "FuelUseType"),
    ("api", "FuelType"),
    ("api", "CropType"),
    ("api", "DisturbanceType"),
    ("api", "MacroInputType"),
    ("api", "InputType"),
    ("api", "IrrigationSystemType"),
    ("api", "EnergySourceType"),
    ("api", "BuildingType"),
    ("api", "RoadType"),
    ("api", "Climate"),
    ("api", "Moisture"),
    ("api", "Region"),
    ("api", "FieldDefinition"),
    ("api", "WaterManagementTypeBeforeCultivation"),
    ("api", "WaterManagementTypeAfterCultivation"),
    ("api", "PackagingMaterialType"),
    ("ipcc", "GlobalWarmingPotential"),
)

TRANSLATED_FIELDS = ("name", "description")
LANGS = ("en", "fr", "es", "ru")


def strip_names(apps, schema_editor):
    """Strip the newlines and spaces several translations were imported with."""
    for app_label, model_name in TRANSLATED_MODELS:
        model = apps.get_model(app_label, model_name)
        concrete = {f.name for f in model._meta.concrete_fields}
        fields = [
            f for base in TRANSLATED_FIELDS for f in (base, *(f"{base}_{lang}" for lang in LANGS)) if f in concrete
        ]
        for row in model.objects.only("pk", *fields):
            changed = []
            for f in fields:
                value = getattr(row, f)
                if isinstance(value, str) and value != value.strip():
                    setattr(row, f, value.strip())
                    changed.append(f)
            if changed:
                row.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0298_translate_projectstatus_and_moduletype_names"),
        ("ipcc", "0067_globalwarmingpotential_ch4_fossil_reference_values"),
    ]

    operations = [
        migrations.RunPython(strip_names, migrations.RunPython.noop),
    ]
