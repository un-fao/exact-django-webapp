from django.db.models import *
from types import SimpleNamespace


class GlobalWarmingPotential(Model):
    name = CharField(max_length=100)
    co2 = FloatField()
    ch4 = FloatField()
    n2o = FloatField()

    def __str__(self):
        return self.name


class NitrousEmissionFactor(Model):
    name = CharField(max_length=100)
    moisture_type = ForeignKey("api.Moisture", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return self.name


class TotalBiomassAfterDefo(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    year = IntegerField(null=True)
    value = FloatField(null=True)

    def __str__(self):
        return f"Climate: {self.climate}, Moisture: {self.moisture}, Continent: {self.continent}, Land Use Type: {self.land_use_type}, Year: {self.year}, Value: {self.value}"


class DataOnMangrove(Model):
    # TODO: Merge this and deforestation table?
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    agb_dry_matter = FloatField()
    c_fraction = FloatField()
    agb_c = FloatField()
    agb_growth = FloatField()
    r = FloatField()
    bgb = FloatField()
    litter = FloatField()
    dw = FloatField()
    soc_ref = FloatField()

    def __str__(self):
        return f"{self.climate.name} {self.moisture.name}, dry_matter: {self.agb_dry_matter}, c_fraction: {self.c_fraction}, agb_c: {self.agb_c}, agb_growth: {self.agb_growth}, r: {self.r}, bgb: {self.bgb}, litter: {self.litter}, dw: {self.dw}, soc_ref: {self.soc_ref}"


class CombustionFactor(Model):
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    co2 = FloatField(null=True)
    ch4 = FloatField(null=True)
    n2o = FloatField(null=True)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.vegetation_type.name}, value: {self.value}"


class AfforestationCombustionFactor(Model):
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    co2 = FloatField(null=True)
    ch4 = FloatField(null=True)
    n2o = FloatField(null=True)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.land_use_type.name}, value: {self.value}"


class DefaultEmissionFactor(Model):
    organic_input_type = ForeignKey("api.OrganicInputType", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.moisture.name}, {self.organic_input_type}, value: {self.value}"


class LitterDeadwoodCarbonStock(Model):
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    litter = FloatField()
    dw = FloatField()

    def __str__(self):
        return f"{self.vegetation_type.name}, litter: {self.litter}, dw: {self.dw}"


class LandUseCarbonStockExchangeFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.climate.name} {self.moisture.name} {self.land_use_type.name}, value: {self.value}"


class SoilOrcanicCarbonCNRatio(Model):
    land_use_type = ForeignKey(
        "api.LandUseType", on_delete=CASCADE, limit_choices_to={"parent": None}
    )
    value = FloatField()


class AboveGroundBiomass(Model):
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, value: {self.value}"


class ForestAGB(Model):
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField()


class BelowGroundBiomassManager(Manager):
    def get_max_below_threshold(self, continent, vegetation_type, threshold):
        """
        Returns the highest value below the threshold.
        """
        return (
            self.filter(
                continent=continent,
                vegetation_type=vegetation_type,
            )
            .filter(Q(threshold__gt=threshold) | Q(threshold__isnull=True))
            .order_by("threshold")
            .first()
        )

    def get_highest_value(self, continent, vegetation_type):
        return (
            self.filter(
                continent=continent,
                vegetation_type=vegetation_type,
                threshold__isnull=True,
            )
            .order_by("threshold")
            .first()
        )

    def get_lowest_value(self, continent, vegetation_type):
        return (
            self.filter(
                continent=continent,
                vegetation_type=vegetation_type,
                threshold__isnull=False,
            )
            .order_by("-threshold")
            .first()
        )


class BelowGroundBiomass(Model):
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    threshold = FloatField(
        null=True, blank=True
    )  # Maximum acceptable ag_biomass needed for this value to be chosen
    value = FloatField()
    objects = BelowGroundBiomassManager()

    def __str__(self):
        return f"{self.continent.name} {self.vegetation_type.name}, threshold: {self.threshold}, value: {self.value}"


class SoilOrganicCarbon(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    soil_type = ForeignKey("api.SoilType", on_delete=CASCADE)
    value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.soil_type} soil, value {self.value}"


class ForestTotalBiomass(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.continent} {self.land_use_type}, value {self.value}"


class AfforestationLandUseStockExchangeFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.land_use_type}, value {self.value}"


class AboveGroundNetBiomassGrowth(Model):
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    value_after_20_years = FloatField()
    value_upto_20_years = FloatField()

    def __str__(self):
        return f"{self.continent} {self.vegetation_type}, value after 20 years: {self.value_after_20_years}, value upto 20 years: {self.value_upto_20_years}"


class EmissionFactorCategory(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class BurningEmissionFactor(Model):
    category = ForeignKey("ipcc.EmissionFactorCategory", on_delete=CASCADE)
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
        Returns the factor for the given land_use_type or the factor for 'other' if the factor for land_use_type does not exists.
        """
        try:
            return self.get(land_use_type=land_use_type)
        except self.model.DoesNotExist:
            return self.get(land_use_type__name="Other")


class FiresCombustionFactor(Model):
    crop_type = ForeignKey("api.CropType", on_delete=CASCADE)
    value = FloatField()

    objects = FiresCombustionFactorManager()

    def __str__(self):
        return f"FiresCombustionFactor for {self.crop_type.name}, value {self.value}"


class CropNitrousEstimationDefaultFactorManager(Manager):
    def get_or_grains(self, crop_type):
        """
        Returns the factor for the given land_use_type or the factor for 'other' if it exists.
        """
        try:
            return self.get(crop_type=crop_type)
        except self.model.DoesNotExist:
            return self.get(crop_type__name="Grains")


class CropNitrousEstimationDefaultFactor(Model):
    crop_type = ForeignKey("api.CropType", on_delete=CASCADE)
    slope = FloatField(null=True, blank=True)
    intercept = FloatField(null=True, blank=True)
    n_ag_residues = FloatField()
    rs_t = FloatField()
    n_bg_t = FloatField()

    objects = CropNitrousEstimationDefaultFactorManager()

    def __str__(self):
        return f"CropNitrousEstimationDefaultFactor for {self.crop_type.name}"


class TillageCarbonStockExchangeFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    tillage_management_type = ForeignKey("api.TillageManagementType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) value {self.value} for {self.tillage_management_type.name}"


class OrganicInputCarbonStockExchangeFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    organic_input_type = ForeignKey("api.OrganicInputType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) value {self.value} for {self.organic_input_type.name}"


class CoastalAboveGroundBiomass(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.vegetation_type.name}"


class CoastalBGAGRatio(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField(default=0)


class CoastalLitter(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField(default=0)


class CoastalDeadwood(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField(default=0)


class RewettingCarbonFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField(default=0)


class RewettingMethaneFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField(default=0)
    salinity = ForeignKey("api.SalinityType", on_delete=CASCADE)


class OtherConstructedWaterbodiesEmissionFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    waterbody_type = ForeignKey("api.WaterbodyType", on_delete=CASCADE)
    value = FloatField(default=0)


class Atwood(Model):
    country = ForeignKey("api.Country", on_delete=CASCADE)
    n = FloatField(default=0)
    area_2014_km2 = FloatField(default=0)
    mg_c_ha = FloatField(default=0)
    sd = FloatField(default=None, null=True, blank=True)
    score = FloatField(default=None, null=True, blank=True)

    def __str__(self):
        return f"Atwood for {self.country.name}"


class DefaultSoilCarbonStock(Model):
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    soil_type = ForeignKey("api.SoilType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.vegetation_type.name} {self.soil_type.name}"


class DrainageEmissionFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    vegetation_type = ForeignKey("api.VegetationType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name}"


class PerennialAGBManager(Manager):
    def get_or_default(self, climate, moisture, continent, land_use_type):
        try:
            return self.get(
                climate=climate,
                moisture=moisture,
                continent=continent,
                land_use_type=land_use_type,
            )
        except PerennialAGB.DoesNotExist:
            return PerennialAGB.objects.get(
                climate=climate,
                moisture=moisture,
                continent=continent,
                land_use_type__name="Agroforestry",
            )


class PerennialAGB(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    crop_type = ForeignKey("api.CropType", on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    objects = PerennialAGBManager()

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} in {self.continent.name} {self.crop_type.name}"


class PerennialBGBManager(Manager):
    def get_or_default(self, climate, moisture, continent, land_use_type):
        try:
            return self.get(
                climate=climate,
                moisture=moisture,
                continent=continent,
                land_use_type=land_use_type,
            )
        except PerennialBGB.DoesNotExist:
            return PerennialBGB.objects.get(
                climate=climate,
                moisture=moisture,
                continent=continent,
                land_use_type__name="Agroforestry",
            )


class PerennialBGB(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    crop_type = ForeignKey("api.CropType", on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    objects = PerennialBGBManager()

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} in {self.continent.name} for {self.crop_type.name}"


class PerennialMaxAGB(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    crop_type = ForeignKey("api.CropType", on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.crop_type.name}"


class CroplandFLU(Model):
    """
    IPCC A57
    """

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    crop_type = ForeignKey("api.CropType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.crop_type.name}"


class CroplandFMG(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    tillage_management_type = ForeignKey("api.TillageManagementType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.tillage_management_type.name}"


class CroplandFI(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    organic_input_type = ForeignKey("api.OrganicInputType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.organic_input_type.name}"


class AfforestationFLU(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"


class GrasslandAGB(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name}"


class GrasslandSOC(Model):
    grassland_management_type = ForeignKey(
        "api.GrasslandManagementType", on_delete=CASCADE
    )
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.grassland_management_type.name}"


class GrasslandStockExchangeFactor(Model):
    grassland_management_type = ForeignKey(
        "api.GrasslandManagementType", on_delete=CASCADE
    )
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
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
    fuel_type = ForeignKey("api.FuelType", on_delete=CASCADE)
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


class SmallFisheryFUIManager(Manager):
    def get_value_or_average(request, fishery_type, gear_type):
        try:
            model = SmallFisheryFUI.objects.get(
                fishery_type=fishery_type, gear_type=gear_type
            )
            return model.value
        except SmallFisheryFUI.DoesNotExist:
            _all = SmallFisheryFUI.objects.filter(fishery_type=fishery_type)
            _all = _all.exclude(gear_type__name="Not Specified")
            _average = sum([x.value for x in _all]) / _all.count()
            return _average


# LargeFisheryFUIManager
class LargeFisheryFUIManager(Manager):
    def get_value_or_average(request, fish_type, gear_type):
        try:
            model = LargeFisheryFUI.objects.get(
                fish_type=fish_type, gear_type=gear_type
            )

            if model.median is None:
                raise LargeFisheryFUI.DoesNotExist

            return model.median
        except LargeFisheryFUI.DoesNotExist:
            _all = LargeFisheryFUI.objects.filter(fish_type=fish_type)
            not_specified = LargeFisheryFUI.objects.filter(
                gear_type__name="Not Specified"
            ).first()
            _all = _all.exclude(gear_type__name="Not Specified")

            _sum = sum([x.median * x.n for x in _all])
            return _sum / not_specified.n


class LargeFisheryFUI(Model):
    fish_type = ForeignKey("api.FishType", on_delete=CASCADE)
    gear_type = ForeignKey("api.LargeFisheryGearType", on_delete=CASCADE, null=True)
    median = FloatField(null=True)
    n = IntegerField(null=True)

    objects = LargeFisheryFUIManager()

    class Meta:
        unique_together = ("fish_type", "gear_type")

    def __str__(self):
        return f"{self.fish_type} - {self.gear_type} n: {self.n} median: {self.median}"


class SmallFisheryFUI(Model):
    class Meta:
        unique_together = ("fishery_type", "gear_type")

    fishery_type = ForeignKey("api.FisheryType", on_delete=CASCADE)
    gear_type = ForeignKey("api.SmallFisheryGearType", on_delete=CASCADE, null=True)
    value = FloatField()

    objects = SmallFisheryFUIManager()

    def __str__(self):
        return f"{self.fishery_type} - {self.gear_type} FUI: {self.value}"


class CropYieldStatsManager(Manager):
    def get_or_region_average(self, crop_type, continent):
        try:
            return CropYieldStats.objects.get(crop_type=crop_type, continent=continent)
        except CropYieldStats.DoesNotExist:
            _all = CropYieldStats.objects.filter(continent=continent).all()
            _average = sum([x.average for x in _all if x.average > 0]) / _all.count()
            return SimpleNamespace(average=_average)


class CropYieldStats(Model):
    crop_type = ForeignKey("api.CropType", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    year_2016 = FloatField(null=True, blank=True)
    year_2017 = FloatField(null=True, blank=True)
    year_2018 = FloatField(null=True, blank=True)
    year_2019 = FloatField(null=True, blank=True)
    year_2020 = FloatField(null=True, blank=True)
    average = FloatField()

    objects = CropYieldStatsManager()

    def save(self, *args, **kwargs):
        self.average = (
            sum(
                [
                    x
                    for x in [
                        self.year_2016,
                        self.year_2017,
                        self.year_2018,
                        self.year_2019,
                        self.year_2020,
                    ]
                ]
            )
            / 5
            / 10000
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"({self.pk}) - {self.continent} - {self.average}"


class InputReference(Model):
    # TODO: Maybe unify with InputEmissionFactor?
    gw_potential = ForeignKey(GlobalWarmingPotential, on_delete=CASCADE)
    input_type = ForeignKey("api.InputType", on_delete=CASCADE)
    co2_multiplier = FloatField(null=True, blank=True)
    co2_emissions_multiplier = FloatField(null=True, blank=True)
    n2o_quantity_multiplier = FloatField(null=True, blank=True)
    n2o_emissions_multiplier = FloatField(null=True, blank=True)
    production_quantity_multiplier = FloatField(null=True, blank=True)
    production_emissions_multiplier = FloatField(null=True, blank=True)

    def __str__(self):
        return (
            f"Input Reference for {self.input_type.name} and {self.gw_potential.name}"
        )


class InputEmissionFactor(Model):
    input_type = ForeignKey("api.InputType", on_delete=CASCADE)
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    water_regime_type = ForeignKey(
        "api.WaterRegimeType", on_delete=CASCADE, null=True, blank=True
    )
    co2_value = FloatField(null=True, blank=True)
    n2o_value = FloatField(null=True, blank=True)
    co2_eq_value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"Input Emission Factor for {self.input_type.name} {self.climate.name} {self.moisture.name} {self.water_regime_type.name if self.water_regime_type else ''} value: {self.co2_value} {self.n2o_value} {self.co2_eq_value}"


class BuildingEmissionFactor(Model):
    building_type = ForeignKey("api.BuildingType", on_delete=CASCADE)
    kg_co2_m2 = FloatField(null=True, blank=True)


class LivestockEntericEF(Model):
    """
    IPCC 2262:2313
    """

    production_type = ForeignKey("api.LivestockProductionType", on_delete=CASCADE)
    livestock_category = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    region = ForeignKey("api.Continent", on_delete=CASCADE)
    value = FloatField()


class EmissionType(Model):
    name = CharField(max_length=255)

    def __str__(self):
        return self.name


class LivestockManureEF(Model):
    """
    IPCC 2706:3010
    """

    emission_type = ForeignKey(EmissionType, on_delete=CASCADE)
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    livestock_production_type = ForeignKey(
        "api.LivestockProductionType", on_delete=CASCADE
    )
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    manure_management_type = ForeignKey("api.ManureManagementType", on_delete=CASCADE)
    value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"({self.id}) {self.emission_type.name} {self.livestock_production_type.name} {self.livestock_category_type.name} {self.climate.name} {self.moisture.name} {self.manure_management_type.name} {self.value}"


class LivestockTAM(Model):
    """
    IPCC 2315:2364
    """

    emission_type = ForeignKey(EmissionType, on_delete=CASCADE, null=True, blank=True)
    livestock_production_type = ForeignKey(
        "api.LivestockProductionType", on_delete=CASCADE
    )
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.id}) {self.livestock_category_type} {self.livestock_production_type} {self.ipcc_region.name} {self.value}"


class LivestockVSER(Model):
    """
    IPCC 2366:2415
    """

    emission_type = ForeignKey(EmissionType, on_delete=CASCADE, null=True, blank=True)
    livestock_production_type = ForeignKey(
        "api.LivestockProductionType", on_delete=CASCADE
    )
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    value = FloatField()

    @staticmethod
    def get_average_value(
        emission_type, production_type, livestock_category, ipcc_region
    ):
        values = LivestockVSER.objects.filter(
            emission_type=emission_type,
            livestock_production_type=production_type,
            livestock_category_type=livestock_category,
            ipcc_region=ipcc_region,
        ).values_list("value", flat=True)
        return sum(values) / len(values)

    def __str__(self):
        return f"({self.id}) {self.livestock_category_type} {self.livestock_production_type} {self.ipcc_region.name} {self.value}"


class LivestockNER(Model):
    """
    IPCC 3012:3061
    """

    emission_type = ForeignKey(EmissionType, on_delete=CASCADE)
    livestock_production_type = ForeignKey(
        "api.LivestockProductionType", on_delete=CASCADE
    )
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    continent = ForeignKey("api.Continent", on_delete=CASCADE)
    value = FloatField()


class LivestockAnimalWasteManagementSystem(Model):
    """
    IPCC 2417:2704

    Value is a percentage expressed as a decimal <= 1
    """

    livestock_production_type = ForeignKey(
        "api.LivestockProductionType", on_delete=CASCADE
    )
    manure_management_type = ForeignKey(
        "api.ManureManagementType", on_delete=CASCADE, null=True, blank=True
    )
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.livestock_production_type.name} {self.livestock_category_type.name} {self.manure_management_type.name} {self.ipcc_region.name} {self.value}"


class LivestockNER(Model):
    """
    IPCC3012:3061
    """

    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    livestock_production_type = ForeignKey(
        "api.LivestockProductionType", on_delete=CASCADE
    )
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    value = FloatField()
