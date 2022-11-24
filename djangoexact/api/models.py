from django.db.models import *
from django.contrib.auth import models as auth_models

# Create your models here.
class User(auth_models.User):
    class Meta:
        proxy = True

    def __str__(self):
        return f"{self.username}"

##############################
############# ELSE ###########
##############################

class VegetationType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class LandUseType(Model):
    name = CharField(max_length=100)
    parent = ForeignKey(
        "self", 
        on_delete=CASCADE, 
        null=True, 
        blank=True, 
        related_name="children", 
        limit_choices_to={'parent': None}
    )

    def __str__(self):
        return self.name

class ChangeDynamic(Model):
    name = CharField(max_length=25)
    value = IntegerField(unique=True)

    def __str__(self):
        return self.name

class ProjectStatus(Model):
    name = CharField(max_length=25)
    value = IntegerField(unique=True)

    class Meta:
        verbose_name_plural = "Project statuses"

    def __str__(self):
        return self.name

class Continent(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class Country(Model):
    name = CharField(max_length=100)
    continent = ForeignKey(Continent, on_delete=CASCADE)

    class Meta:
        verbose_name_plural = "Countries"

    def __str__(self):
        return self.name

class Climate(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class Moisture(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class SoilType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class Input(Model):
    name = CharField(max_length=100)

class TillageType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class OrganicInputType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class ResidueManagementType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class WaterRegimeType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class PreSeasonWaterRegimeType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

class OrganicAmendmentType(Model):
    name = CharField(max_length=100)

    def __str__(self):
        return self.name

##############################
############# IPCC ###########
##############################

class IPCCGlobalWarmingPotential(Model):
    name = CharField(max_length=100)
    co2 = FloatField()
    ch4 = FloatField()
    n2o = FloatField()

    def __str__(self):
        return self.name

class IPCCNitrousEmissionFactor(Model):
    name = CharField(max_length=100)
    moisture_type = ForeignKey(Moisture, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return self.name

class IPCCTotalBiomassAfterDefo(Model):
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    continent = ForeignKey(Continent, on_delete=CASCADE)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    value = FloatField()

class IPCCDataOnMangroves(Model):
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

class IPCCCombustionFactorValues(Model):
    # TODO: Merge Forest and AgroforestrySystemType into one model?
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    co2 = FloatField()
    ch4 = FloatField()
    n2o = FloatField()
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.vegetation_type.name}, value: {self.value}"

class IPCCDefaultEmissionFactors(Model):
    input = ForeignKey(Input, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.moisture.name}, value: {self.value}"

class IPCCLitterDeadwoodCarbonStock(Model):
    forest = ForeignKey(VegetationType, on_delete=CASCADE)
    litter = FloatField()
    dw = FloatField()

    def __str__(self):
        return f"{self.forest.name}, litter: {self.litter}, dw: {self.dw}"

class IPCCLandUseStockExchangeFactor(Model):
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    agroforestry_system = ForeignKey(LandUseType, on_delete=CASCADE)
    value = FloatField()

class IPCCSoilOrcanicCarbonCNRatio(Model):
    land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, limit_choices_to={'parent': None})
    value = FloatField()

class IPCCAboveGroundBiomass(Model):
    continent = ForeignKey(Continent, on_delete=CASCADE)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, value: {self.value}"

class IPCCBelowGroundBiomass(Model):
    continent = ForeignKey(Continent, on_delete=CASCADE)
    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    threshold = FloatField(null=True, blank=True) # Maximum acceptable ag_biomass needed for this value to be chosen
    value = FloatField()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, threshold: {self.threshold}, value: {self.value}"

class IPCCSoilOrganicCarbon(Model):
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    soil = ForeignKey(SoilType, on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.soil} soil"

##############################
############ FORMS ###########
##############################

class Project(Model):
    # TODO: Implement uuid instead of BigAutoField?
    # id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = ForeignKey(User, on_delete=CASCADE)
    date = DateTimeField(auto_now_add=True)
    name = CharField(max_length=100)
    code = CharField(max_length=100)
    cost = FloatField()
    funding_agency = CharField(max_length=100)
    executing_agency = CharField(max_length=100)
    status = ForeignKey(ProjectStatus, on_delete=CASCADE)

    implementation_duration_yrs = FloatField()
    capitalization_duration_yrs = FloatField()

    continent = ForeignKey(Continent, on_delete=CASCADE)
    country = ForeignKey(Country, on_delete=CASCADE)
    climate = ForeignKey(Climate, on_delete=CASCADE)
    moisture = ForeignKey(Moisture, on_delete=CASCADE)
    soil_type = ForeignKey(SoilType, on_delete=CASCADE)

    gw_potential = ForeignKey(IPCCGlobalWarmingPotential, on_delete=CASCADE)

    soc_ref = ForeignKey(IPCCSoilOrganicCarbon, on_delete=CASCADE)

    def __str__(self):
        return self.name

class LandUseInput(Model):

    class Meta:
        abstract = True

    project_id = ForeignKey(Project, on_delete=CASCADE)

    vegetation_type = ForeignKey(VegetationType, on_delete=CASCADE)
    land_use_type = ForeignKey(LandUseType, on_delete=CASCADE)
    is_fire_used = BooleanField(default=False)
    ha_w  = IntegerField()
    ha_w_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_w_rate")
    ha_wo = IntegerField()
    ha_wo_rate = ForeignKey(ChangeDynamic, on_delete=CASCADE, related_name="%(class)s_ha_wo_rate+")

class DeforestationInput(LandUseInput):

    hwp = FloatField()
    ha_start = IntegerField()

    rcs_ag_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for above-ground biomass (in tC/ha)")
    rcs_bg_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for below-ground biomass (in tC/ha)")
    rcs_litter_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for litter (in tC/ha)")
    rcs_deadwood_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for deadwood (in tC/ha)")
    rcs_soil_c_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for soil carbon (in tC/ha)") 
    final_rcs_biomass_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for biomass in final land use (in tC/ha)")
    final_rcs_soil_c_t2 = FloatField(null=True, blank=True, help_text="Custom reference carbon stock for soil carbon in final land use (in tC/ha)")

    def __str__(self):
        return f"{self.vegetation_type.name} with {self.ha_w_rate}"

class AfforestationInput(LandUseInput):
    # TODO: Add T2 values
    
    def __str__(self):
        return f"AfforestationInput for {self.vegetation_type.name}"

class OtherLandUseChangeInput(LandUseInput):
    # TODO: Add T2 values

    notes = TextField(null=True, blank=True)
    final_land_use_type = ForeignKey(LandUseType, on_delete=CASCADE, related_name="%(class)s_final_land_use_type")

    def __str__(self):
        return f"OtherLandUseChangeInput for {self.vegetation_type.name}"