import polib
from djangoexact.settings import LANGUAGES
import datetime
from api.models import *
from django.apps import apps
from django.db import transaction

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
        EnergySourceType,  # TODO: Remove from database
        BuildingType,
        RoadType,
    ]

    # for _type in types:
    #     print(f"Processing type {_type}")
    #     for obj in _type.objects.all():
    #         obj_name = str(obj.name) if obj.name else ""
    #         print(f"Processing object {obj_name}")

    #         entry = po.find(obj_name)
    #         print(f"Found entry {entry}")
    #         if entry:
    #             print(f"Found entry with {language[0]} translation {entry.msgstr}")
    #             setattr(obj, f"name_{language[0]}", entry.msgstr)
    #             obj.save()

    with transaction.atomic():
        for entry in po:
            print(f"Processing entry {entry}")
            if entry.obsolete:
                continue

            obj_type = apps.get_model("api", entry.comment)
            obj = obj_type.objects.get(name=entry.msgid)
            if entry.msgstr:
                setattr(obj, f"name_{language[0]}", entry.msgstr)
                obj.save()
