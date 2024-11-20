from types import SimpleNamespace

from django.db.models import *


class GlobalWarmingPotential(Model):

    class Meta:
        verbose_name = "Global Warming Potential"
        verbose_name_plural = "Global Warming Potentials"

    name = CharField(max_length=100)
    co2 = FloatField()
    ch4 = FloatField()
    n2o = FloatField()
    ch4_fossil = FloatField(null=True, blank=True)

    def __str__(self):
        return f"({self.id}) {self.name} - CO2: {self.co2}, CH4: {self.ch4}, N2O: {self.n2o}, CH4 Fossil: {self.ch4_fossil}"


class TotalBiomassAfterDefoManager(Manager):
    def get_or_default(self, climate, moisture, continent, land_use_type):
        try:
            return self.get(
                climate=climate,
                moisture=moisture,
                continent=continent,
                land_use_type=land_use_type,
            )
        except TotalBiomassAfterDefo.DoesNotExist:
            return TotalBiomassAfterDefo.objects.get(
                climate=climate,
                moisture=moisture,
                continent=continent,
                land_use_type__name="Agroforestry - Default",
            )


class TotalBiomassAfterDefo(Model):
    """
    IPCC:1515
    """

    class Meta:
        verbose_name = "Total Biomass for Final Land Use"
        verbose_name_plural = "Total Biomass for Final Land Uses"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    continent = ForeignKey("api.Region", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    year = IntegerField(null=True)
    value = FloatField(null=True)

    objects = TotalBiomassAfterDefoManager()

    def __str__(self):
        return f"Climate: {self.climate}, Moisture: {self.moisture}, Continent: {self.continent}, Land Use Type: {self.land_use_type}, Year: {self.year}, Value: {self.value}"


class DataOnMangrove(Model):
    class Meta:
        verbose_name = "Data on Mangrove"
        verbose_name_plural = "Data on Mangroves"

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


class ForestCombustionFactor(Model):
    class Meta:
        verbose_name = "Forest Combustion Factor"
        verbose_name_plural = "Forest Combustion Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    forest_type = ForeignKey("api.ForestType", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    co2 = FloatField(null=True)
    ch4 = FloatField(null=True)
    n2o = FloatField(null=True)
    value = FloatField()

    def __str__(self):
        return f"Factor for {self.land_use_type.name}, value: {self.value}"


class AfforestationCombustionFactorManager(Manager):
    def get_or_default(self, land_use_type):
        try:
            return self.get(land_use_type=land_use_type)
        except AfforestationCombustionFactor.DoesNotExist:
            return self.get(land_use_type__name__icontains="Default")


class AfforestationCombustionFactor(Model):

    class Meta:
        verbose_name = "Afforestation Combustion Factor"
        verbose_name_plural = "Afforestation Combustion Factors"

    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    co2 = FloatField(null=True)
    ch4 = FloatField(null=True)
    n2o = FloatField(null=True)
    value = FloatField()

    objects = AfforestationCombustionFactorManager()

    def __str__(self):
        return f"Factor for {self.land_use_type.name}, value: {self.value}"


class LitterDeadwoodCarbonStock(Model):

    class Meta:
        verbose_name = "Litter/Deadwood Carbon Stock"
        verbose_name_plural = "Litter/Deadwood Carbon Stock"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    forest_type = ForeignKey("api.ForestType", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    litter = FloatField()
    dw = FloatField()

    def __str__(self):
        return f"{self.forest_type.name} {self.land_use_type.name}, {self.climate.name} - litter: {self.litter}, dw: {self.dw}"


class LandUseCarbonStockExchangeFactorManager(Manager):
    def get_or_default(self, climate, moisture, land_use_type):
        try:
            return self.get(
                climate=climate,
                moisture=moisture,
                land_use_type=land_use_type,
            )
        except LandUseCarbonStockExchangeFactor.DoesNotExist:
            return LandUseCarbonStockExchangeFactor.objects.get(
                climate=climate,
                moisture=moisture,
                land_use_type__name__icontains="Default",
            )


class LandUseCarbonStockExchangeFactor(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField()

    objects = LandUseCarbonStockExchangeFactorManager()

    class Meta:
        verbose_name = "Land Use Carbon Stock Exchange Factor"
        verbose_name_plural = "Land Use Carbon Stock Exchange Factors"
        unique_together = ("climate", "moisture", "land_use_type")

    def __str__(self):
        return f"{self.climate.name} {self.moisture.name} {self.land_use_type.name}, value: {self.value}"


class SoilOrcanicCarbonCNRatio(Model):
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField()


class ForestManagementBGBManager(Manager):
    def get_max_below_threshold(self, climate, forest_type, region, land_use_type, threshold):
        """
        Returns the highest value below the threshold.
        NOTE: If a new, highest threshold is added to the db, this can return the wrong value unless the old highest threshold is set to a proper value
        """
        return (
            self.filter(
                forest_type=forest_type,
                climate=climate,
                region=region,
                land_use_type=land_use_type,
            )
            .filter(Q(threshold__gt=threshold) | Q(threshold__isnull=True))
            .order_by("threshold")
            .first()
        )

    def get_first_above_threshold(self, climate, forest_type, region, land_use_type, threshold) -> "ForestManagementBGB":
        """
        Returns the first value above the threshold.
        """
        return (
            self.filter(
                forest_type=forest_type,
                climate=climate,
                region=region,
                land_use_type=land_use_type,
            )
            .filter(Q(threshold__lt=threshold) | Q(threshold__isnull=True))
            .order_by("-threshold")
            .first()
        )

    def get_highest_value(self, climate, forest_type, region, land_use_type):
        return (
            self.filter(
                forest_type=forest_type,
                climate=climate,
                region=region,
                land_use_type=land_use_type,
                threshold__isnull=True,
            )
            .order_by("threshold")
            .first()
        )

    def get_lowest_value(self, climate, forest_type, region, land_use_type):
        return (
            self.filter(
                forest_type=forest_type,
                climate=climate,
                region=region,
                land_use_type=land_use_type,
                threshold__isnull=False,
            )
            .order_by("-threshold")
            .first()
        )


class ForestManagementBGB(Model):

    class Meta:
        verbose_name = "Forest Management BGB"
        verbose_name_plural = "Forest Management BGB"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    region = ForeignKey("api.Region", on_delete=CASCADE)
    forest_type = ForeignKey("api.ForestType", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    threshold = FloatField(null=True, blank=True)  # Maximum acceptable ag_biomass needed for this value to be chosen
    value = FloatField()
    objects = ForestManagementBGBManager()

    def __str__(self):
        return f"({self.forest_type.name}) {self.land_use_type.name} {self.climate.name} {self.region.name}, threshold: {self.threshold}, value: {self.value}"


class SoilOrganicCarbon(Model):

    class Meta:
        verbose_name = "Soil Organic Carbon"
        verbose_name_plural = "Soil Organic Carbon"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    soil_type = ForeignKey("api.SoilType", on_delete=CASCADE)
    value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.soil_type} soil, value {self.value}"


class ForestTotalBiomassManager(Manager):
    def get_or_default(self, climate, moisture, continent, land_use_type):
        try:
            return self.get(
                climate=climate,
                moisture=moisture,
                continent=continent,
                land_use_type=land_use_type,
            )
        except ForestTotalBiomass.DoesNotExist:
            return ForestTotalBiomass.objects.get(
                climate=climate,
                moisture=moisture,
                continent=continent,
                land_use_type__name__icontains="Agroforestry - Default",
            )


class ForestTotalBiomass(Model):

    class Meta:
        verbose_name = "Forest Biomass for Initial Land Use"
        verbose_name_plural = "Forest Biomass for Initial Land Use"
        unique_together = ("climate", "moisture", "continent", "land_use_type")

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    continent = ForeignKey("api.Region", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField()

    objects = ForestTotalBiomassManager()

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.continent} {self.land_use_type}, value {self.value}"


class AfforestationLandUseStockExchangeFactorManager(Manager):
    def get_or_default(self, climate, moisture, land_use_type):
        try:
            return self.get(
                climate=climate,
                moisture=moisture,
                land_use_type=land_use_type,
            )
        except AfforestationLandUseStockExchangeFactor.DoesNotExist:
            return AfforestationLandUseStockExchangeFactor.objects.get(
                climate=climate,
                moisture=moisture,
                land_use_type__name__icontains="Default",
            )


class AfforestationLandUseStockExchangeFactor(Model):

    class Meta:
        verbose_name = "Afforestation Land Use Stock Exchange Factor"
        verbose_name_plural = "Afforestation Land Use Stock Exchange Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField()

    objects = AfforestationLandUseStockExchangeFactorManager()

    def __str__(self):
        return f"{self.climate} {self.moisture} for {self.land_use_type}, value {self.value}"


class ForestManagementAGBGrowth(Model):

    class Meta:
        verbose_name = "Forest Management AGB Growth"
        verbose_name_plural = "Forest Management AGB Growth"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    forest_type = ForeignKey("api.ForestType", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    region = ForeignKey("api.Region", on_delete=CASCADE)
    value_after_20_years = FloatField()
    value_upto_20_years = FloatField()

    def __str__(self):
        return f"{self.region} {self.land_use_type}, value after 20 years: {self.value_after_20_years}, value upto 20 years: {self.value_upto_20_years}"


class EmissionFactorCategory(Model):
    name = CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class BurningEmissionFactor(Model):
    """
    IPCC:A75
    """

    class Meta:
        verbose_name = "Burning Emission Factor"
        verbose_name_plural = "Burning Emission Factors"

    category = ForeignKey("ipcc.EmissionFactorCategory", on_delete=CASCADE)
    co2 = FloatField()
    co = FloatField()
    ch4 = FloatField()
    n2o = FloatField()
    nox = FloatField()

    def __str__(self):
        return f"BurningEmissionFactor for {self.category.name}"


class FiresCombustionFactorManager(Manager):
    def get_or_default(self, land_use_type):
        """
        Returns the factor for the given land_use_type or the factor for 'other' if the factor for land_use_type does not exists.
        """
        try:
            return self.get(land_use_type=land_use_type)
        except self.model.DoesNotExist:
            return self.get(land_use_type__name="Default")


class FiresCombustionFactor(Model):
    """
    IPCC:A84
    """

    class Meta:
        verbose_name = "Fires Combustion Factor"
        verbose_name_plural = "Fires Combustion Factors"

    land_use_type = OneToOneField("api.LandUseType", on_delete=CASCADE)
    value = FloatField()

    objects = FiresCombustionFactorManager()

    def __str__(self):
        return f"FiresCombustionFactor for {self.land_use_type.name}, value {self.value}"


class CropNitrousEstimationDefaultFactorManager(Manager):
    def get_or_grains(self, land_use_type):
        """
        Returns the factor for the given land_use_type or the factor for 'other' if it exists.
        """
        try:
            return self.get(land_use_type=land_use_type)
        except self.model.DoesNotExist:
            return self.get(land_use_type__name="Grains")


class CropNitrousEstimationDefaultFactor(Model):
    """
    IPCC:A8
    """

    class Meta:
        verbose_name = "Crop Nitrous Estimation Factor"
        verbose_name_plural = "Crop Nitrous Estimation Factors"

    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    slope = FloatField(null=True, blank=True)
    intercept = FloatField(null=True, blank=True)
    n_ag_residues = FloatField()
    rs_t = FloatField()
    n_bg_t = FloatField()

    objects = CropNitrousEstimationDefaultFactorManager()

    def __str__(self):
        return f"CropNitrousEstimationDefaultFactor for {self.land_use_type.name}"


class TillageCarbonStockExchangeFactor(Model):

    class Meta:
        verbose_name = "Tillage Carbon Stock Exchange Factor"
        verbose_name_plural = "Tillage Carbon Stock Exchange Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    tillage_management_type = ForeignKey("api.TillageManagementType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) value {self.value} for {self.tillage_management_type.name}"


class OrganicInputCarbonStockExchangeFactor(Model):

    class Meta:
        verbose_name = "Organic Input Carbon Stock Exchange Factor"
        verbose_name_plural = "Organic Input Carbon Stock Exchange Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    organic_input_type = ForeignKey("api.OrganicInputType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) value {self.value} for {self.organic_input_type.name}"


class CoastalAGB(Model):
    """
    IPCC 2094
    """

    class Meta:
        verbose_name = "Coastal AGB"
        verbose_name_plural = "Coastal AGB"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)
    unit = CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"


class CoastalBGB(Model):
    """
    IPCC 2113
    """

    class Meta:
        verbose_name = "Coastal BGB"
        verbose_name_plural = "Coastal BGB"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)
    unit = CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"


class CoastalLitter(Model):
    """
    IPCC 2128
    """

    class Meta:
        verbose_name = "Coastal Litter"
        verbose_name_plural = "Coastal Litter"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)


class CoastalDeadwood(Model):
    """
    IPCC 2145
    """

    class Meta:
        verbose_name = "Coastal Deadwood"
        verbose_name_plural = "Coastal Deadwood"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self) -> str:
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"


class RewettingCarbonFactor(Model):
    """
    IPCC 2228
    """

    class Meta:
        verbose_name = "Rewetting Carbon Factor"
        verbose_name_plural = "Rewetting Carbon Factors"
        unique_together = ("climate", "moisture", "soil_type", "land_use_type")

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    soil_type = ForeignKey("api.SoilType", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.soil_type.name} {self.land_use_type.name}"


class RewettingMethaneFactor(Model):
    """
    IPCC 2245
    """

    class Meta:
        verbose_name = "Rewetting Methane Factor"
        verbose_name_plural = "Rewetting Methane Factors"
        unique_together = ("climate", "moisture", "land_use_type", "salinity")

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)
    salinity = ForeignKey("api.SalinityType", on_delete=CASCADE)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name} {self.salinity.value}"


class OtherConstructedWaterbodiesEmissionFactor(Model):

    class Meta:
        verbose_name = "Other Constructed Waterbodies Emission Factor"
        verbose_name_plural = "Other Constructed Waterbodies Emission Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    waterbody_type = ForeignKey("api.WaterbodyType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.waterbody_type.name}"


class Atwood(Model):

    class Meta:
        verbose_name = "Atwood"
        verbose_name_plural = "Atwood"

    country = ForeignKey("api.Country", on_delete=CASCADE)
    n = FloatField(default=0)
    area_2014_km2 = FloatField(default=0)
    mg_c_ha = FloatField(default=0)
    sd = FloatField(default=None, null=True, blank=True)
    score = FloatField(default=None, null=True, blank=True)

    def __str__(self):
        return f"Atwood for {self.country.name}"


class DefaultSoilCarbonStock(Model):

    class Meta:
        verbose_name = "Default Soil Carbon Stock"
        verbose_name_plural = "Default Soil Carbon Stock"

    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    soil_type = ForeignKey("api.SoilType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name} {self.soil_type.name}"


class DrainageEmissionFactor(Model):
    """
    IPCC 2111
    """

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.land_use_type} {self.climate} {self.moisture}"

    class Meta:
        unique_together = ("climate", "moisture", "land_use_type")
        verbose_name = "Drainage Emission Factor"
        verbose_name_plural = "Drainage Emission Factors"


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
                land_use_type__name="Agroforestry - Default",
            )


class PerennialAGB(Model):
    """
    IPCC A107
    """

    class Meta:
        verbose_name = "Perennial AGB"
        verbose_name_plural = "Perennial AGB"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    continent = ForeignKey("api.Region", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    objects = PerennialAGBManager()

    def __str__(self):
        return f"{self.land_use_type.name} = {self.value} for {self.climate.name} {self.moisture.name} in {self.continent.name}"


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
                land_use_type__name="Agroforestry - Default",
            )


class PerennialBGB(Model):

    class Meta:
        verbose_name = "Perennial BGB"
        verbose_name_plural = "Perennial BGB"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    continent = ForeignKey("api.Region", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    objects = PerennialBGBManager()

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} in {self.continent.name} for {self.land_use_type.name}"


class PerennialMaxAGBManager(Manager):
    def get_or_default(self, climate, land_use_type):
        try:
            return self.get(
                climate=climate,
                land_use_type=land_use_type,
            )
        except PerennialMaxAGB.DoesNotExist:
            return PerennialMaxAGB.objects.get(
                climate=climate,
                land_use_type__name="Agroforestry - Default",
            )


class PerennialMaxAGB(Model):
    """
    IPCC A3237
    """

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0, null=True, blank=True)

    objects = PerennialMaxAGBManager()

    class Meta:
        unique_together = ("climate", "land_use_type")
        verbose_name = "Perennial Max AGB"
        verbose_name_plural = "Perennial Max AGB"

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.land_use_type.name}"


class CroplandFLU(Model):
    """
    IPCC A57
    """

    class Meta:
        verbose_name = "Cropland FLU"
        verbose_name_plural = "Cropland FLUs"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"


class CroplandFMG(Model):

    class Meta:
        verbose_name = "Cropland FMG"
        verbose_name_plural = "Cropland FMGs"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    tillage_management_type = ForeignKey("api.TillageManagementType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.tillage_management_type.name}"


class CroplandFI(Model):

    class Meta:
        verbose_name = "Cropland FI"
        verbose_name_plural = "Cropland FIs"

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

    class Meta:
        unique_together = ("climate", "moisture", "land_use_type")
        verbose_name = "Afforestation FLU"
        verbose_name_plural = "Afforestation FLUs"

    def __str__(self):
        return f"{self.value} for {self.climate.name} {self.moisture.name} {self.land_use_type.name}"


class GrasslandBiomass(Model):
    """
    Table, 6.4, page 6.27  in IPCC 2006
    """

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    agb_t_dm_ha = FloatField()
    agb_t_c_ha = FloatField()
    bgb_t_dm_ha = FloatField()
    bgb_t_c_ha = FloatField()

    class Meta:
        unique_together = ("climate", "moisture")
        verbose_name = "Grassland Biomass"
        verbose_name_plural = "Grassland Biomass"

    def __str__(self):
        return f"{self.climate} {self.moisture} {self.agb_t_dm_ha} {self.agb_t_c_ha} {self.bgb_t_dm_ha} {self.bgb_t_c_ha}"


class GrasslandSOC(Model):

    class Meta:
        verbose_name = "Grassland SOC"
        verbose_name_plural = "Grassland SOC"

    grassland_management_type = ForeignKey("api.GrasslandManagementType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"{self.value} for {self.grassland_management_type.name}"


class GrasslandStockExchangeFactorManager(Manager):
    # get or default: try getting it, otherwise return the default value (all values are 1)
    def get_or_default(self, grassland_management_type, climate):
        try:
            return self.get(grassland_management_type=grassland_management_type, climate=climate)
        except GrasslandStockExchangeFactor.DoesNotExist:
            return SimpleNamespace(fmg=1, flu=1, fi=1, grassland_management_type=grassland_management_type, climate=climate)


class GrasslandStockExchangeFactor(Model):

    class Meta:
        verbose_name = "Grassland Stock Exchange Factor"
        verbose_name_plural = "Grassland Stock Exchange Factors"

    grassland_management_type = ForeignKey("api.GrasslandManagementType", on_delete=CASCADE)
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    fmg = FloatField(default=1)
    flu = FloatField(default=1)
    fi = FloatField(default=1)

    objects = GrasslandStockExchangeFactorManager()

    def __str__(self):
        return f"{self.fmg} {self.flu} {self.fi} for {self.grassland_management_type.name} {self.climate.name}"


class ElectricityEmission(Model):

    class Meta:
        verbose_name = "Electricity Emission"
        verbose_name_plural = "Electricity Emissions"

    country = ForeignKey("api.Country", on_delete=CASCADE, unique=True)
    operating_margin = FloatField(null=True, blank=True)
    combined_margin = FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.country} {self.operating_margin} {self.combined_margin}"


class SmallFisheryFUIManager(Manager):
    def get_value_or_average(request, fishery_type, gear_type):
        try:
            model = SmallFisheryFUI.objects.get(fishery_type=fishery_type, gear_type=gear_type)
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
            model = LargeFisheryFUI.objects.get(fish_type=fish_type, gear_type=gear_type)
            return model.value
        except LargeFisheryFUI.DoesNotExist:
            if fish_type.name_en == "Not Specified" and gear_type.name_en == "Not Specified":
                _all = LargeFisheryFUI.objects.exclude(fish_type__name="Not Specified")
                _all = _all.exclude(gear_type__name="Not Specified").values_list("value", flat=True)
                return sum(_all) / len(_all)

            if fish_type.name_en == "Not Specified":
                fuis = LargeFisheryFUI.objects.filter(gear_type=gear_type).values_list("value", flat=True)
                return sum(fuis) / len(fuis)

            if gear_type.name_en == "Not Specified":
                fuis = LargeFisheryFUI.objects.filter(fish_type=fish_type).values_list("value", flat=True)
                return sum(fuis) / len(fuis)

            _all = LargeFisheryFUI.objects.filter(fish_type=fish_type)
            _all = _all.exclude(Q(gear_type__name="Not Specified") | Q(fish_type__name="Not Specified")).values_list("value", flat=True)
            return sum(_all) / len(_all)


class LargeFisheryFUI(Model):

    fish_type = ForeignKey("api.FishType", on_delete=CASCADE)
    gear_type = ForeignKey("api.LargeFisheryGearType", on_delete=CASCADE, null=True)
    value = FloatField()

    objects = LargeFisheryFUIManager()

    class Meta:
        verbose_name = "Large Fishery FUI"
        verbose_name_plural = "Large Fishery FUIs"
        unique_together = ("fish_type", "gear_type")

    def __str__(self):
        return f"{self.fish_type} - {self.gear_type} value: {self.value}"


class SmallFisheryFUI(Model):
    class Meta:
        verbose_name = "Small Fishery FUI"
        verbose_name_plural = "Small Fishery FUIs"
        unique_together = ("fishery_type", "gear_type")

    fishery_type = ForeignKey("api.FisheryType", on_delete=CASCADE)
    gear_type = ForeignKey("api.SmallFisheryGearType", on_delete=CASCADE, null=True)
    value = FloatField()

    objects = SmallFisheryFUIManager()

    def __str__(self):
        return f"{self.fishery_type} - {self.gear_type} FUI: {self.value}"


class CropYieldStatsManager(Manager):
    def get_or_region_average(self, land_use_type, continent):
        try:
            return CropYieldStats.objects.get(land_use_type=land_use_type, continent=continent)
        except CropYieldStats.DoesNotExist:
            _all = CropYieldStats.objects.filter(Q(average__gt=0), continent=continent).values_list("average", flat=True)
            _average = sum(_all) / _all.count()
            return SimpleNamespace(average=_average)


class CropYieldStats(Model):
    """
    Stats_yield_ton_per_ha:A1
    """

    class Meta:
        verbose_name = "Crop Yield Stats"
        verbose_name_plural = "Crop Yield Stats"

    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    continent = ForeignKey("api.Region", on_delete=CASCADE)
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
        return f"({self.pk}) - {self.land_use_type.name} - {self.continent} - {self.average}"


class InputReference(Model):

    class Meta:
        verbose_name = "Input Reference"
        verbose_name_plural = "Input References"

    # TODO: Maybe unify with InputEmissionFactor?
    input_type = ForeignKey("api.InputType", on_delete=CASCADE)
    co2_multiplier = FloatField(null=True, blank=True)
    co2_emissions_multiplier = FloatField(null=True, blank=True)
    n2o_quantity_multiplier = FloatField(null=True, blank=True)
    n2o_emissions_multiplier = FloatField(null=True, blank=True)
    production_quantity_multiplier = FloatField(null=True, blank=True)
    production_emissions_multiplier = FloatField(null=True, blank=True)

    def __str__(self):
        return f"Input Reference for {self.input_type.name}"


class InputEmissionFactor(Model):

    class Meta:
        verbose_name = "Input Emission Factor"
        verbose_name_plural = "Input Emission Factors"

    input_type = ForeignKey("api.InputType", on_delete=CASCADE)
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    water_regime_type = ForeignKey("api.WaterRegimeType", on_delete=CASCADE, null=True, blank=True)
    co2_value = FloatField(null=True, blank=True)
    n2o_value = FloatField(null=True, blank=True)
    co2_eq_value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"Input Emission Factor for {self.input_type.name} {self.climate.name} {self.moisture.name} {self.water_regime_type.name if self.water_regime_type else ''} value: {self.co2_value} {self.n2o_value} {self.co2_eq_value}"


class BuildingEmissionFactor(Model):

    class Meta:
        verbose_name = "Building Emission Factor"
        verbose_name_plural = "Building Emission Factors"

    building_type = ForeignKey("api.BuildingType", on_delete=CASCADE)
    value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.building_type.name} {self.value}"


class RoadEmissionFactor(Model):

    class Meta:
        verbose_name = "Road Emission Factor"
        verbose_name_plural = "Road Emission Factors"

    road_type = ForeignKey("api.RoadType", on_delete=CASCADE)
    value = FloatField(null=True, blank=True)

    def __str__(self):
        return f"({self.pk}) {self.road_type.name} {self.value}"


class LivestockEntericEF(Model):
    """
    IPCC 2262:2313
    """

    class Meta:
        verbose_name = "Livestock Enteric Emission Factor"
        verbose_name_plural = "Livestock Enteric Emission Factors"

    production_type = ForeignKey("api.LivestockProductionType", on_delete=CASCADE)
    livestock_category = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    region = ForeignKey("api.Region", on_delete=CASCADE)
    value = FloatField()


class EmissionType(Model):
    name = CharField(max_length=255)

    def __str__(self):
        return f"({self.id}) {self.name}"


class LivestockManureEF(Model):
    """
    IPCC 2706:3010
    """

    class Meta:
        verbose_name = "Livestock Manure Emission Factor"
        verbose_name_plural = "Livestock Manure Emission Factors"
        unique_together = ("emission_type", "livestock_production_type", "livestock_category_type", "climate", "moisture", "manure_management_type")

    emission_type = ForeignKey(EmissionType, on_delete=CASCADE)
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    livestock_production_type = ForeignKey("api.LivestockProductionType", on_delete=CASCADE)
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

    class Meta:
        verbose_name = "Livestock TAM"
        verbose_name_plural = "Livestock TAMs"

    livestock_production_type = ForeignKey("api.LivestockProductionType", on_delete=CASCADE)
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.id}) {self.livestock_category_type} {self.livestock_production_type} {self.ipcc_region.name} {self.value}"


class LivestockVSER(Model):
    """
    IPCC 2366:2415
    """

    class Meta:
        verbose_name = "Livestock VSER"
        verbose_name_plural = "Livestock VSERs"
        unique_together = ("livestock_production_type", "livestock_category_type", "ipcc_region")

    livestock_production_type = ForeignKey("api.LivestockProductionType", on_delete=CASCADE)
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    value = FloatField()

    @staticmethod
    def get_average_value(emission_type, production_type, livestock_category, ipcc_region):
        values = LivestockVSER.objects.filter(
            livestock_production_type=production_type,
            livestock_category_type=livestock_category,
            ipcc_region=ipcc_region,
        ).values_list("value", flat=True)
        return sum(values) / len(values)

    def __str__(self):
        return f"({self.id}) {self.livestock_category_type} {self.livestock_production_type} {self.ipcc_region.name} {self.value}"


class LivestockAWMS(Model):
    """
    IPCC 2417:2704

    Value is a percentage expressed as a decimal <= 100
    """

    livestock_production_type = ForeignKey("api.LivestockProductionType", on_delete=CASCADE)
    manure_management_type = ForeignKey("api.ManureManagementType", on_delete=CASCADE, null=True, blank=True)
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.livestock_production_type} {self.livestock_category_type} {self.manure_management_type} {self.ipcc_region} {self.value}"

    class Meta:
        unique_together = ("livestock_production_type", "manure_management_type", "livestock_category_type", "ipcc_region")
        verbose_name_plural = "Livestock Animal Waste Management Systems"


class LivestockNER(Model):
    """
    IPCC3012:3061
    """

    class Meta:
        verbose_name = "Livestock NER"
        verbose_name_plural = "Livestock NERs"

    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    livestock_production_type = ForeignKey("api.LivestockProductionType", on_delete=CASCADE)
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    value = FloatField()


class MethaneEntericFermentationFactor(Model):
    """
    IPCC:2262:2301
    """

    class Meta:
        verbose_name = "Methane Enteric Fermentation Factor"
        verbose_name_plural = "Methane Enteric Fermentation Factors"

    ipcc_region = ForeignKey("api.IPCCRegion", on_delete=CASCADE)
    livestock_production_type = ForeignKey("api.LivestockProductionType", on_delete=CASCADE)
    livestock_category_type = ForeignKey("api.LivestockCategoryType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.ipcc_region.name} {self.livestock_production_type.name} {self.livestock_category_type.name} {self.value}"


class ManureManagementVolatilizationMultiplier(Model):

    class Meta:
        verbose_name = "Manure Management Volatilization Multiplier"
        verbose_name_plural = "Manure Management Volatilization Multipliers"

    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.moisture.name} {self.value}"


class EnergyDefaultEmissionFactor(Model):
    """
    IPCC 1724:1753
    """

    fuel_use_type = ForeignKey("api.FuelUseType", on_delete=CASCADE)
    fuel_type = ForeignKey("api.FuelType", on_delete=CASCADE)
    co2 = FloatField(null=True, blank=True)
    ch4 = FloatField(null=True, blank=True)
    n2o = FloatField(null=True, blank=True)

    def __str__(self):
        fuel_use_type = getattr(self.fuel_type.fuel_use_type, "name", None)
        return f"({self.pk}) {self.fuel_type} {fuel_use_type} {self.co2} {self.ch4} {self.n2o}"

    class Meta:
        verbose_name_plural = "Energy default emission factors"
        unique_together = ("fuel_use_type", "fuel_type")


class IrrigationSystemData(Model):
    irrigation_system_type = OneToOneField("api.IrrigationSystemType", on_delete=CASCADE, unique=True)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.irrigation_system_type} {self.value}"

    class Meta:
        verbose_name_plural = "Irrigation system data"


class IrrigationPhaseData(Model):

    class Meta:
        verbose_name = "Irrigation Phase Data"
        verbose_name_plural = "Irrigation Phase Data"

    fuel_type = ForeignKey("api.FuelType", on_delete=CASCADE)
    emission_factor = FloatField()
    calorific_value = FloatField(blank=True, null=True)
    co2_emissions = FloatField(blank=True, null=True)
    ch4_emissions = FloatField(blank=True, null=True)
    n2o_emissions = FloatField(blank=True, null=True)
    density = FloatField(blank=True, null=True)


class IrrigationPressureRequirement(Model):

    class Meta:
        verbose_name = "Irrigation Pressure Requirement"
        verbose_name_plural = "Irrigation Pressure Requirements"

    irrigation_system_type = ForeignKey("api.IrrigationSystemType", on_delete=CASCADE)
    initial_denomination = CharField(max_length=255, null=True, blank=True)
    bar_start = FloatField(null=True, blank=True)
    bar_end = FloatField(null=True, blank=True)
    avg_pressure = FloatField()
    head = FloatField()

    def save(self, *args, **kwargs):
        if not self.avg_pressure:
            self.avg_pressure = (self.bar_start + self.bar_end) / 2
        super().save(*args, **kwargs)

    def __str__(self):
        return f"({self.pk}) {self.irrigation_system_type.name} {self.avg_pressure}"


class RiceDefaultEmissionFactor(Model):
    """
    IPCC:A515
    """

    class Meta:
        verbose_name = "Rice Default Emission Factor"
        verbose_name_plural = "Rice Default Emission Factors"

    continent = ForeignKey("api.Region", on_delete=CASCADE)
    cultivation_period = IntegerField()
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.continent.name} {self.value}"


class RiceSFO(Model):
    """
    IPCC:J512
    """

    class Meta:
        verbose_name = "Rice SFO"
        verbose_name_plural = "Rice SFOs"

    organic_amendment_type = ForeignKey("api.OrganicAmendmentType", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.organic_amendment_type.name} {self.value}"


class RiceSFP(Model):
    """
    IPCC:E524
    """

    class Meta:
        verbose_name = "Rice SFP"
        verbose_name_plural = "Rice SFPs"

    water_management_type_before_cultivation = ForeignKey("api.WaterManagementTypeBeforeCultivation", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.water_management_type_before_cultivation.name} {self.value}"


class RiceSFW(Model):
    """
    IPCC:E512
    """

    class Meta:
        verbose_name = "Rice SFW"
        verbose_name_plural = "Rice SFWs"

    water_management_type_after_cultivation = ForeignKey("api.WaterManagementTypeAfterCultivation", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.water_management_type_after_cultivation.name} {self.value}"


class RiceYield(Model):
    """
    Rice!AC3
    """

    class Meta:
        verbose_name = "Rice Yield"
        verbose_name_plural = "Rice Yields"

    continent = ForeignKey("api.Region", on_delete=CASCADE)
    value = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.continent.name} {self.value}"


class TrophicStateFactor(Model):
    """
    IPCC:3222
    """

    class Meta:
        verbose_name = "Trophic State Factor"
        verbose_name_plural = "Trophic State Factors"

    trophic_type = ForeignKey("api.TrophicType", on_delete=CASCADE)
    value = FloatField()
    chloa = FloatField()

    def __str__(self):
        return f"({self.pk}) {self.trophic_type.name} {self.value} {self.chloa}"


# TODO: Dump data from here to end


class OrganicSoilDrainageEmissionFactorManager(Manager):
    def get_or_other_luc(self, climate, moisture, module_type_name, peat_type, site_location_type_name):
        try:
            return self.get(
                climate=climate,
                moisture=moisture,
                module_type__name=module_type_name,
                peat_type=peat_type,
                site_location_type__name=site_location_type_name,
            )
        except:
            return self.get(
                climate=climate,
                moisture=moisture,
                module_type__name=module_type_name,
                peat_type=peat_type,
                site_location_type__name="OtherLandUseChange",
            )


class OrganicSoilDrainageEmissionFactor(Model):

    class Meta:
        verbose_name = "Organic Soil Drainage Emission Factor"
        verbose_name_plural = "Organic Soil Drainage Emission Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    module_type = ForeignKey("api.ModuleType", on_delete=CASCADE)
    peat_type = ForeignKey("api.PeatType", on_delete=CASCADE)
    site_location_type = ForeignKey("api.SiteLocationType", on_delete=CASCADE)

    co2 = FloatField(default=0)
    co2_unit = CharField(max_length=100, default="tC/ha/yr")

    doc = FloatField(default=0)
    doc_unit = CharField(max_length=100, default="tC/ha/yr")

    ch4 = FloatField(default=0)
    ch4_unit = CharField(max_length=100, default="kg CH4/ha/yr")

    n2o = FloatField(default=0)
    n2o_unit = CharField(max_length=100, default="kg N2O/ha/yr")

    objects = OrganicSoilDrainageEmissionFactorManager()

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name} {self.module_type.name} {self.peat_type.name} {self.site_location_type.name}"


class PeatExtractionEmissionFactor(Model):

    class Meta:
        verbose_name = "Peat Extraction Emission Factor"
        verbose_name_plural = "Peat Extraction Emission Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    peat_type = ForeignKey("api.PeatType", on_delete=CASCADE)
    site_location_type = ForeignKey("api.SiteLocationType", on_delete=CASCADE)

    co2 = FloatField(default=0)
    co2_unit = CharField(max_length=100, default="tC/ha/yr")

    doc = FloatField(default=0)
    doc_unit = CharField(max_length=100, default="tC/ha/yr")

    ch4 = FloatField(default=0)
    ch4_unit = CharField(max_length=100, default="kg CH4/ha/yr")

    n2o = FloatField(default=0)
    n2o_unit = CharField(max_length=100, default="kg N2O/ha/yr")

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name} {self.peat_type.name} {self.site_location_type.name}"


class PeatExtractionConversionFactor(Model):

    class Meta:
        verbose_name = "Peat Extraction Conversion Factor"
        verbose_name_plural = "Peat Extraction Conversion Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    peat_type = ForeignKey("api.PeatType", on_delete=CASCADE)
    weight = FloatField(default=0)
    weight_unit = CharField(max_length=100, default="tC/t air dry peat")
    volume = FloatField(default=0)
    volume_unit = CharField(max_length=100, default="tC/m3 air dry peat")

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name} {self.peat_type.name}"


class OrganicSoilFuelConsumption(Model):

    class Meta:
        verbose_name = "Organic Soil Fuel Consumption"
        verbose_name_plural = "Organic Soil Fuel Consumptions"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    fire_type = ForeignKey("api.FireType", on_delete=CASCADE)
    value = FloatField(default=0)
    unit = CharField(max_length=100, default="t dm/ha")

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name} {self.fire_type.name}"


class OrganicSoilGefEmissionFactor(Model):

    class Meta:
        verbose_name = "Organic Soil GEF Emission Factor"
        verbose_name_plural = "Organic Soil GEF Emission Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    co2 = FloatField(default=0)
    co2_unit = CharField(max_length=100, default="g CO2-C/kg dry matter burned")
    co = FloatField(default=0)
    co_unit = CharField(max_length=100, default="g CO/kg dry matter burned")
    ch4 = FloatField(default=0)
    ch4_unit = CharField(max_length=100, default="g CH4/kg dry matter burned")

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name}"


class OrganicSoilRewettingEmissionFactor(Model):

    class Meta:
        verbose_name = "Organic Soil Rewetting Emission Factor"
        verbose_name_plural = "Organic Soil Rewetting Emission Factors"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    peat_type = ForeignKey("api.PeatType", on_delete=CASCADE)
    module_type = ForeignKey("api.ModuleType", on_delete=CASCADE)

    co2 = FloatField(default=0)
    co2_unit = CharField(max_length=100, default="tCO2-C/ha/yr")

    doc = FloatField(default=0)
    doc_unit = CharField(max_length=100, default="tCO2-C/ha/yr")

    ch4 = FloatField(default=0)
    ch4_unit = CharField(max_length=100, default="kg CH4-C/ha/yr")

    n2o = FloatField(default=0)
    n2o_unit = CharField(max_length=100, default="tN2O-N/ha/yr")

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name} {self.peat_type.name} {self.module_type.name}"


class ForestManagementAGB(Model):

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE)
    region = ForeignKey("api.Region", on_delete=CASCADE)
    forest_condition_type = ForeignKey("api.ForestConditionType", on_delete=CASCADE)
    from_year = IntegerField(default=0)
    forest_type = ForeignKey("api.ForestType", on_delete=CASCADE)
    agb_min = FloatField(blank=True, null=True)
    agb_max = FloatField(blank=True, null=True)
    agb_growth_min = FloatField(blank=True, null=True)
    agb_growth_max = FloatField(blank=True, null=True)
    agb_unit = CharField(max_length=100, default="tonnes d.m./ha")

    class Meta:
        verbose_name = "Forest Management AGB"
        verbose_name_plural = "Forest Management AGB"
        unique_together = ("climate", "land_use_type", "region", "forest_condition_type", "from_year", "forest_type")

    def __str__(self):
        return f"({self.pk}) ({self.forest_type.name}) {self.land_use_type.name} {self.forest_condition_type.name} from {self.from_year} years in {self.region.name}"


class FMGData(Model):

    class Meta:
        verbose_name = "FMG Data"
        verbose_name_plural = "FMG Data"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    tillage_management_type = ForeignKey("api.TillageManagementType", on_delete=CASCADE, null=True)
    grassland_management_type = ForeignKey("api.GrasslandManagementType", on_delete=CASCADE, null=True)
    value = FloatField(default=0)

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name} {self.tillage_management_type} {self.grassland_management_type} {self.value}"


class FIData(Model):
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    organic_input_type = ForeignKey("api.OrganicInputType", on_delete=CASCADE, null=True)
    grassland_management_type = ForeignKey("api.GrasslandManagementType", on_delete=CASCADE, null=True)
    value = FloatField(default=0)

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name} {self.organic_input_type} {self.grassland_management_type} {self.value}"

    class Meta:
        verbose_name = "FI Data"
        verbose_name_plural = "FI Data"
        unique_together = ("climate", "moisture", "organic_input_type", "grassland_management_type")


class FLUData(Model):

    class Meta:
        verbose_name = "FLU Data"
        verbose_name_plural = "FLU Data"

    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    land_use_type = ForeignKey("api.LandUseType", on_delete=CASCADE, null=True)
    grassland_management_type = ForeignKey("api.GrasslandManagementType", on_delete=CASCADE, null=True)
    value = FloatField(default=0)

    def __str__(self):
        return f"({self.pk}) {self.climate.name} {self.moisture.name} {self.land_use_type} {self.grassland_management_type} {self.value}"

    class Meta:
        unique_together = ("climate", "moisture", "land_use_type", "grassland_management_type")


class SettlementEF(Model):
    settlement_type = ForeignKey("api.SettlementType", on_delete=CASCADE)
    climate = ForeignKey("api.Climate", on_delete=CASCADE)
    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    flu = FloatField(default=1)
    fmg = FloatField(default=1)
    fi = FloatField(default=1)
    biomass = FloatField(default=0)

    class Meta:
        verbose_name = "Settlement Emission Factor"
        verbose_name_plural = "Settlement Emission Factors"
        unique_together = ("settlement_type", "climate", "moisture")

    def __str__(self):
        return f"({self.pk}) {self.flu} {self.fi} {self.fmg} for {self.settlement_type.name} {self.climate.name} {self.moisture.name}"


class NitrousEmissionFactor(Model):

    class Meta:
        verbose_name = "Nitrous Emission Factor"
        verbose_name_plural = "Nitrous Emission Factors"

    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"({self.pk}) {self.moisture.name} {self.value}"


class InputsNitrousEmissionFactor(Model):

    class Meta:
        verbose_name = "Inputs Nitrous Emission Factor"
        verbose_name_plural = "Inputs Nitrous Emission Factors"

    moisture = ForeignKey("api.Moisture", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"({self.pk}) {self.moisture.name} {self.value}"


class ValueChainPackagingEmissionFactor(Model):
    """
    Type of packaging	Emission factors (t〖CO〗_2-e/tonne of packaging)
    Wood	            0.4
    Paper	            2.1
    Aluminium	        8.5
    Plastic (mixed)	    3.6
    """

    class Meta:
        verbose_name = "Value Chain Packaging Emission Factor"
        verbose_name_plural = "Value Chain Packaging Emission Factors"

    packaging_material_type = ForeignKey("api.PackagingMaterialType", on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"({self.pk}) {self.packaging_material_type.name} {self.value}"


class ValueChainRefrigerantEmissionFactor(Model):
    """"""

    class Meta:
        verbose_name = "Value Chain Refrigerant Emission Factor"
        verbose_name_plural = "Value Chain Refrigerant Emission Factors"

    refrigerant_type = ForeignKey("api.RefrigerantType", on_delete=CASCADE)
    gwp = ForeignKey(GlobalWarmingPotential, on_delete=CASCADE)
    value = FloatField(default=0)

    def __str__(self):
        return f"({self.pk}) {self.refrigerant_type.name} {self.value}"
