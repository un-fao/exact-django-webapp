from modeltranslation.translator import register, TranslationOptions
import ipcc.models as models


class NameOnlyTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(models.GlobalWarmingPotential)
class GlobalWarmingPotentialTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.WasteComponent)
class WasteComponentTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.SolidWasteDisposalSiteType)
class SolidWasteDisposalSiteTypeTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.WasteTreatmentEmissionFactor)
class WasteTreatmentEmissionFactorTranslationOptions(NameOnlyTranslationOptions):
    pass
