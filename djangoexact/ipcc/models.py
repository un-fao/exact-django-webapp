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

class AfforestationCombustionFactorValues(Model):
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    co2 = FloatField(null=True)
    ch4 = FloatField(null=True)
    n2o = FloatField(null=True)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.land_use_type.name}, value: {self.value}"

class DefaultEmissionFactors(Model):
    input = ForeignKey('api.OrganicInputType', on_delete=CASCADE)
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

class LandUseCarbonStockExchangeFactor(Model):
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

class ForestAGB(Model):
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField()

class BelowGroundBiomassManager(Manager):
    def get_max_below_threshold(self, continent, vegetation_type, threshold):
        """
        Returns the highest value below the threshold.
        """
        return self.filter(
            continent = continent,
            vegetation_type = vegetation_type,
        ).filter(
            Q(threshold__gt=threshold) 
          | Q(threshold__isnull=True)
        ).order_by('threshold').first()
    
    def get_highest_value(self, continent, vegetation_type):
        return self.filter(
            continent = continent,
            vegetation_type = vegetation_type,
            threshold__isnull=True
        ).order_by('threshold').first()
    
    def get_lowest_value(self, continent, vegetation_type):
        return self.filter(
            continent = continent,
            vegetation_type = vegetation_type,
            threshold__isnull=False
        ).order_by('-threshold').first()

class BelowGroundBiomass(Model):
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    threshold = FloatField(null=True, blank=True) # Maximum acceptable ag_biomass needed for this value to be chosen
    value = FloatField()
    objects = BelowGroundBiomassManager()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, threshold: {self.threshold}, value: {self.value}"

class SoilOrganicCarbon(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    soil_type = ForeignKey('api.SoilType', on_delete=CASCADE)
    value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.soil_type} soil, value {self.value}"

class ForestTotalBiomass(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.continent} {self.land_use_type}, value {self.value}"

class AfforestationLandUseStockExchangeFactor(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.land_use_type}, value {self.value}"

class AboveGroundNetBiomassGrowth(Model):
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    value_after_20_years = FloatField()
    value_upto_20_years = FloatField()

    def __str__(self):
        return f"{self.continent} {self.vegetation_type}, value after 20 years: {self.value_after_20_years}, value upto 20 years: {self.value_upto_20_years}"

class EmissionFactorCategory(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class BurningEmissionFactor(Model):
    category = ForeignKey('ipcc.EmissionFactorCategory', on_delete=CASCADE)
    co2 = FloatField()
    co = FloatField()
    ch4 = FloatField()
    n2o = FloatField()
    nox = FloatField()

    def __str__(self):
        return f"BurningEmissionFactor for {self.category.name}"

class FiresCombustionFactorManager(Manager):
    def get_or_other(self, land_use_type):
        """
        Returns the factor for the given land_use_type or the factor for 'other' if it exists.
        """
        try:
            return self.get(land_use_type=land_use_type)
        except self.model.DoesNotExist:
            return self.get(land_use_type__name='Other')

class FiresCombustionFactor(Model):
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"FiresCombustionFactor for {self.land_use_type.name}"

class CropNitrousEstimationDefaultFactorManager(Manager):
    def get_or_grains(self, land_use_type):
        """
        Returns the factor for the given land_use_type or the factor for 'other' if it exists.
        """
        try:
            return self.get(land_use_type=land_use_type)
        except self.model.DoesNotExist:
            return self.get(land_use_type__name='Grains')

class CropNitrousEstimationDefaultFactor(Model):
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    slope = FloatField(null=True, blank=True)
    intercept = FloatField(null=True, blank=True)
    n_ag_residues = FloatField()
    rs_t = FloatField()
    n_bg_t = FloatField()

    objects = CropNitrousEstimationDefaultFactorManager()

    def __str__(self):
        return f"CropNitrousEstimationDefaultFactor for {self.land_use_type.name}"

class TillageCarbonStockExchangeFactor(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    tillage_management_type = ForeignKey('api.TillageManagementType', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) value {self.value} for {self.tillage_management_type.name}"

class OrganicInputCarbonStockExchangeFactor(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    organic_input_type = ForeignKey('api.OrganicInputType', on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) value {self.value} for {self.organic_input_type.name}"

class CoastalAboveGroundBiomass(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.vegetation_type.name}"

class CoastalBGAGRatio(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField(default=0)

class CoastalLitter(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField(default=0)

class CoastalDeadwood(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField(default=0)

class RewettingCarbonFactor(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField(default=0)

class RewettingMethaneFactor(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField(default=0)
    salinity = ForeignKey('api.SalinityType', on_delete=CASCADE)

class OtherConstructedWaterbodiesEmissionFactor(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    waterbody_type = ForeignKey('api.WaterbodyType', on_delete=CASCADE)
    value = FloatField(default=0)

class Atwood(Model):
    country = ForeignKey('api.Country', on_delete=CASCADE)
    n = FloatField(default=0)
    area_2014_km2 = FloatField(default=0)
    mg_c_ha = FloatField(default=0)
    sd = FloatField(default=None, null=True, blank=True)
    score = FloatField(default=None, null=True, blank=True)

class DefaultSoilCarbonStock(Model):
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    soil_type = ForeignKey('api.SoilType', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.vegetation_type.name} {self.soil_type.name}"
    
class DrainageEmissionFactor(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    vegetation_type = ForeignKey('api.VegetationType', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name}"
    
class PerennialAGB(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"

class PerennialBGB(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    continent = ForeignKey('api.Continent', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"

class PerennialMaxAGB(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.land_use_type.name}"
    
class CroplandFLU(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"
    
class CroplandFMG(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    tillage_management_type = ForeignKey('api.TillageManagementType', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.tillage_management_type.name}"
    
class CroplandFI(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    organic_input_type = ForeignKey('api.OrganicInputType', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.organic_input_type.name}"
    
class AfforestationFLU(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    land_use_type = ForeignKey('api.LandUseType', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"
    
class GrasslandAGB(Model):
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    moisture = ForeignKey('api.Moisture', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name}"

class GrasslandSOC(Model):
    grassland_management_type = ForeignKey('api.GrasslandManagementType', on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.grassland_management_type.name}"

class GrasslandStockExchangeFactor(Model):
    grassland_management_type = ForeignKey('api.GrasslandManagementType', on_delete=CASCADE)
    climate = ForeignKey('api.Climate', on_delete=CASCADE)
    fmg = FloatField(default=1)
    flu = FloatField(default=1)
    fi = FloatField(default=1)

    def __str__(self):
        return f"{self.fmg} {self.flu} {self.fi} for {self.grassland_management_type.name} {self.climate.name}"

class ElectricityEmission(Model):
    country = ForeignKey("api.Country", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    year = IntegerField(null=True, blank=True)

    ef_grid = FloatField(null=True, blank=True)
    final_ef_grid = FloatField(null=True, blank=True)
    operating_margin = FloatField(null=True, blank=True)

    # TODO: In the Excel file this is calculated in Elec G5, but here I'm putting it as static. Ask about this.
    combined_margin = FloatField(null=True, blank=True)

    # TODO: What is this exactly?
    for_formulas = FloatField(null=True, blank=True)

    def __str__(self):
        return f"Electricity Emissions for {self.country}"

class EnergyDefaultEmissionFactor(Model):
    fuel_type = ForeignKey('api.FuelType', on_delete=CASCADE)
    t_co2_eq_m3 = FloatField(blank=True, null=True)
    tj_gg = FloatField(blank=True, null=True)
    kg_ch4_tj = FloatField(blank=True, null=True)
    kg_n2o_tj = FloatField(blank=True, null=True)
    density_kg_m3 = FloatField(blank=True, null=True)
    co2_emissions = FloatField(blank=True, null=True)
    ch4_emissions = FloatField(blank=True, null=True)
    n2o_emissions = FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.fuel_type.name} {self.t_co2_eq_m3} {self.tj_gg} {self.kg_ch4_tj} {self.kg_n2o_tj} {self.density_kg_m3} {self.co2_emissions} {self.ch4_emissions} {self.n2o_emissions}"

class LargeFisheryFUI(Model):
    fish_type = ForeignKey("api.FishType", on_delete=CASCADE)
    gear_type = ForeignKey("api.GearType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.fish_type} - {self.gear_type} FUI: {self.value}"

class SmallFisheryFUI(Model):
    fishery_type = ForeignKey("api.FisheryType", on_delete=CASCADE)
    gear_type = ForeignKey("api.GearType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.fishery_type} - {self.gear_type} FUI: {self.value}"

class CropYieldStats(Model):
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    year_2016 = FloatField(null=True, blank=True)
    year_2017 = FloatField(null=True, blank=True)
    year_2018 = FloatField(null=True, blank=True)
    year_2019 = FloatField(null=True, blank=True)
    year_2020 = FloatField(null=True, blank=True)
    average = FloatField()