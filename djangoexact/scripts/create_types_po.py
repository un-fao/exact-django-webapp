import polib
from djangoexact.settings import LANGUAGES
import datetime
from api.models import *
from ipcc.models import *

for language in LANGUAGES:
    po = polib.POFile(f"locale/{language[0]}/LC_MESSAGES/types.po")
    po.metadata = {
        "Project-Id-Version": "1.0",
        "Report-Msgid-Bugs-To": "support@example.com",
        "POT-Creation-Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M%z"),
        "PO-Revision-Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M%z"),
        "Last-Translator": "Your Name <your.email@example.com>",
        "Language-Team": "English <support@example.com>",
        "Language": "en",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }

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
    ]

    for _type in types:

        for obj in _type.objects.all():
            # Handle None values in both msgid and msgstr
            obj_name = str(obj.name) if obj.name else ""
            obj_translated_name = getattr(obj, f"name_{language[0]}", obj_name) or ""

            # Check if the object is already in the po file
            if po.find(obj_name):
                print(f"Object {obj_name} of type {_type.__name__} already exists in the po file")
                continue

            entry = polib.POEntry(
                msgid=obj_name,
                msgstr=obj_translated_name,
            )
            entry.comment = str(_type.__name__)
            po.append(entry)

    po.save(f"locale/{language[0]}/LC_MESSAGES/types.po")
