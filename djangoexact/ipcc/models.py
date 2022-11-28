from django.db.models import *

class GlobalWarmingPotential(Model):
    name = CharField(max_length=100)
    co2 = FloatField()
    ch4 = FloatField()
    n2o = FloatField()

    def __str__(self):
        return self.name

class NitrousEmissionFactor(Model):
    name = CharField(max_length=100)
    moisture_type = ForeignKey('api.Moisture', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return self.name

class TotalBiomassAfterDefo(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    year = IntegerField(null=True)
    value = FloatField(null=True)

    def __str__(self):
        return f"Climate: {self.climate}, Moisture: {self.moisture}, Continent: {self.continent}, Land Use Type: {self.land_use_type}, Year: {self.year}, Value: {self.value}"

class DataOnMangroves(Model):
    # TODO: Merge this and deforestation table?
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
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
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    co2 = FloatField(null=True)
    ch4 = FloatField(null=True)
    n2o = FloatField(null=True)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.vegetation_type.name}, value: {self.value}"

class DefaultEmissionFactors(Model):
    input = ForeignKey('api.Input', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.moisture.name}, {self.input}, value: {self.value}"

class LitterDeadwoodCarbonStock(Model):
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    litter = FloatField()
    dw = FloatField()

    def __str__(self):
        return f"{self.vegetation_type.name}, litter: {self.litter}, dw: {self.dw}"

class LandUseStockExchangeFactor(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.climate.name} {self.moisture.name} {self.land_use_type.name}, value: {self.value}"

class SoilOrcanicCarbonCNRatio(Model):
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE, limit_choices_to={'parent': None})
    value = FloatField()

class AboveGroundBiomass(Model):
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, value: {self.value}"

class BelowGroundBiomass(Model):
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    threshold = FloatField(null=True, blank=True) # Maximum acceptable ag_biomass needed for this value to be chosen
    value = FloatField()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, threshold: {self.threshold}, value: {self.value}"

class SoilOrganicCarbon(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    soil_type = ForeignKey('api.SoilType', on_delete=CASCADE)
    value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.soil_type} soil, value {self.value}"