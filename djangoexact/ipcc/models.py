from django.db.models import *
from api.models import Continent, VegetationType, LandUseType, Moisture, Climate, Input, SoilType

# Create your models here.

class GlobalWarmingPotential(Model):
    name = CharField(max_length=100)
    co2 = FloatField()
    ch4 = FloatField()
    n2o = FloatField()

    def __str__(self):
        return self.name

class NitrousEmissionFactor(Model):
    name = CharField(max_length=100)
    moisture_type = ForeignKey(Moisture, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return self.name

class TotalBiomassAfterDefo(Model):
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    continent = ForeignKey(Continent, on_delete=CASCADE)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    value = FloatField()

class DataOnMangroves(Model):
    # TODO: Merge this and deforestation table?
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    agb_dry_matter = FloatField()
    c_fraction = FloatField()
    agb_c = FloatField()
    agb_growth = FloatField()
    r = FloatField()
    bgb = FloatField()
    litter  = FloatField()
    dw = FloatField()
    soc_ref = FloatField()

    def __str__(self):
        return f"{self.climate.name} {self.moisture.name}, dry_matter: {self.agb_dry_matter}, c_fraction: {self.c_fraction}, agb_c: {self.agb_c}, agb_growth: {self.agb_growth}, r: {self.r}, bgb: {self.bgb}, litter: {self.litter}, dw: {self.dw}, soc_ref: {self.soc_ref}"

class CombustionFactorValues(Model):
    # TODO: Merge Forest and AgroforestrySystemType into one model?
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    co2 = FloatField()
    ch4 = FloatField()
    n2o = FloatField()
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.vegetation_type.name}, value: {self.value}"

class DefaultEmissionFactors(Model):
    input = ForeignKey(Input, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.moisture.name}, value: {self.value}"

class LitterDeadwoodCarbonStock(Model):
    forest = ForeignKey(VegetationType, on_delete=CASCADE)
    litter = FloatField()
    dw = FloatField()

    def __str__(self):
        return f"{self.forest.name}, litter: {self.litter}, dw: {self.dw}"

class LandUseStockExchangeFactor(Model):
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    agroforestry_system = ForeignKey(LandUseType, on_delete=CASCADE)
    value = FloatField()

class SoilOrcanicCarbonCNRatio(Model):
    land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, limit_choices_to={'parent': None})
    value = FloatField()

class AboveGroundBiomass(Model):
    continent = ForeignKey(Continent, on_delete=CASCADE)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, value: {self.value}"

class BelowGroundBiomass(Model):
    continent = ForeignKey(Continent, on_delete=CASCADE)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    threshold = FloatField(null=True, blank=True) # Maximum acceptable ag_biomass needed for this value to be chosen
    value = FloatField()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, threshold: {self.threshold}, value: {self.value}"

class SoilOrganicCarbon(Model):
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    soil = ForeignKey(SoilType, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.soil} soil"