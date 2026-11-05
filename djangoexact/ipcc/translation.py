from modeltranslation.translator import register, TranslationOptions
import ipcc.models as models


class NameOnlyTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(models.GlobalWarmingPotential)
class GlobalWarmingPotentialTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.FoodIndustryWastewater)
class FoodIndustryWastewaterTranslationOptions(NameOnlyTranslationOptions):
    pass


@register(models.WastewaterTreatmentSystem)
class WastewaterTreatmentSystemTranslationOptions(NameOnlyTranslationOptions):
    pass
