from modeltranslation.translator import register, TranslationOptions
import api.models as models


class NameOnlyTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(models.InvitationStatusType)
class InvitationStatusTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.GasType)
class GasTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.ForestType)
class ForestTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.ForestConditionType)
class ForestConditionTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.SiteLocationType)
class SiteLocationTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.VegetationType)
class VegetationTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.ActivityType)
class ActivityTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.StatusType)
class StatusTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.LandUseType)
class LandUseTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.SettlementType)
class SettlementTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.SoilType)
class SoilTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.ExtractionSoilType)
class ExtractionSoilTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.TillageType)
class TillageTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.OrganicInputType)
class OrganicInputTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.ResidueManagementType)
class ResidueManagementTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.WaterRegimeType)
class WaterRegimeTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.PreSeasonWaterRegimeType)
class PreSeasonWaterRegimeTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.OrganicAmendmentType)
class OrganicAmendmentTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.TillageManagementType)
class TillageManagementTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.GrasslandManagementType)
class GrasslandManagementTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.LivestockCategoryType)
class LivestockCategoryTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.LivestockProductionType)
class LivestockProductionTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.ManureManagementType)
class ManureManagementTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.ModuleType)
class ModuleTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.FireType)
class FireTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.PeatType)
class PeatTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.WaterbodyType)
class WaterbodyTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.TrophicType)
class TrophicTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.FisheryType)
class FisheryTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.LargeFisheryGearType)
class LargeFisheryGearTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.SmallFisheryGearType)
class SmallFisheryGearTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.FishType)
class FishTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.MacroFuelType)
class MacroFuelTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.FuelUseType)
class FuelUseTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.FuelType)
class FuelTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.CropType)
class CropTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.DisturbanceType)
class DisturbanceTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.MacroInputType)
class MacroInputTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.InputType)
class InputTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.IrrigationSystemType)
class IrrigationSystemTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.EnergySourceType)
class EnergySourceTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.BuildingType)
class BuildingTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.RoadType)
class RoadTypeTranslationOptions(NameOnlyTranslationOptions):
    pass
