import polib
from djangoexact.settings import LANGUAGES
import datetime
from api.models import *
from django.apps import apps
from django.db import transaction
from ipcc.models import *

for language in LANGUAGES:
    print(f"Processing language {language[0]}")
    # Open the po file
    po = polib.pofile(f"locale/{language[0]}/LC_MESSAGES/types.po")

    types = [
        InvitationStatusType,
        GasType,
        ForestType,
        ForestConditionType,
        SiteLocationType,
        ActivityType,
        StatusType,
        LandUseType,
        SettlementType,
        SoilType,
        ExtractionSoilType,
        TillageType,
        OrganicInputType,
        ResidueManagementType,
        WaterRegimeType,
        PreSeasonWaterRegimeType,
        OrganicAmendmentType,
        TillageManagementType,
        GrasslandManagementType,
        LivestockCategoryType,
        LivestockProductionType,
        ManureManagementType,
        ModuleType,
        FireType,
        PeatType,
        WaterbodyType,
        TrophicType,
        FisheryType,
        LargeFisheryGearType,
        SmallFisheryGearType,
        FishType,
        MacroFuelType,
        FuelUseType,
        FuelType,
        CropType,
        DisturbanceType,
        MacroInputType,
        InputType,
        IrrigationSystemType,
        EnergySourceType,
        BuildingType,
        RoadType,
        Climate,
        Moisture,
        Region,
        GlobalWarmingPotential,
        WaterManagementTypeBeforeCultivation,
        WaterManagementTypeAfterCultivation,
        PackagingMaterialType,
    ]

    with transaction.atomic():
        for entry in po:
            print(f"Processing entry {entry}")
            if entry.obsolete:
                continue

            try:
                obj_type = apps.get_model("api", entry.comment)
            except LookupError:
                obj_type = apps.get_model("ipcc", entry.comment)

            try:
                objs = obj_type.objects.filter(name=entry.msgid).all()
            except obj_type.DoesNotExist:
                print(f"Object of type {obj_type} with name {entry.msgid} does not exist.")
                continue
            if entry.msgstr:
                for obj in objs:
                    setattr(obj, f"name_{language[0]}", entry.msgstr)
                    obj.save()
