"""
Unit Test Factories

Factory classes specifically designed for unit testing that provide reliable default values
for all modules tested in the unit test suite. These factories are climate and project-aware
and provide consistent, testable configurations.

These factories differ from the main factories.py in that they:
- Provide more reliable, non-random defaults for unit testing
- Are climate/moisture/project context-aware
- Follow the exact patterns used in the unit tests
- Provide minimal but sufficient data for calculations to work
"""

import factory
import factory.fuzzy
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText, FuzzyInteger, FuzzyFloat, FuzzyChoice

import api.models as models
import ipcc.models as ipcc_models


def _resolve_land_use_type(resolver, class_name):
    """Climate/moisture-aware LandUseType for `class_name`.

    Module-level (not a factory method): inside `@factory.lazy_attribute`,
    `self` is factory_boy's Resolver, which exposes declared attributes
    (e.g. `activity`) but cannot dispatch to factory instance methods — so
    `self._get_land_use_type()` raised AttributeError. Mirrors the working
    UnitTestAnnualCroplandFactory logic.
    """
    qs = models.LandUseType.objects.filter(module_types__class_name=class_name, is_active=True)
    if hasattr(resolver, "activity") and resolver.activity and resolver.activity.project:
        project = resolver.activity.project
        qs = qs.filter(climates=project.climate, moistures=project.moisture)
    return qs.first()


class UnitTestProjectFactory(DjangoModelFactory):
    """
    Project factory specifically for unit testing with reliable defaults.
    """

    class Meta:
        model = models.Project

    name = factory.LazyFunction(lambda: f"Unit_Test_Project_{factory.fuzzy.FuzzyInteger(1000, 9999).fuzz()}")
    start_year_of_activities = 2024
    implementation_years = 10
    last_year_of_accounting = 2040

    # Use consistent climate/moisture for predictable testing
    climate = factory.LazyAttribute(lambda obj: models.Climate.objects.first())
    moisture = factory.LazyAttribute(lambda obj: obj.climate.moistures.first())
    country = factory.LazyAttribute(lambda obj: models.Country.objects.filter(region__isnull=False).first())
    soil_type = factory.LazyAttribute(lambda obj: models.SoilType.objects.filter(active=True).exclude(name__in=["Mineral", "Organic"]).first())
    gw_potential = factory.LazyAttribute(lambda obj: ipcc_models.GlobalWarmingPotential.objects.first())
    soc_ref_t2 = 50  # Fixed value for predictable testing


class UnitTestActivityFactory(DjangoModelFactory):
    """
    Activity factory for unit testing.
    """

    class Meta:
        model = models.Activity

    name = factory.LazyFunction(lambda: f"Unit_Test_Activity_{factory.fuzzy.FuzzyInteger(1000, 9999).fuzz()}")
    change_rate = factory.LazyAttribute(lambda obj: models.ChangeRate.objects.get(name="linear"))


class UnitTestAnnualCroplandFactory(DjangoModelFactory):
    """
    AnnualCropland factory based on unit test patterns.
    """

    class Meta:
        model = models.AnnualCropland

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    @factory.lazy_attribute
    def land_use_type_start(self):
        """Get appropriate land use type for AnnualCropland based on project climate."""
        if hasattr(self, "activity") and self.activity and self.activity.project:
            climate = self.activity.project.climate
            moisture = self.activity.project.moisture
            return models.LandUseType.objects.filter(module_types__class_name="AnnualCropland", climates=climate, moistures=moisture, is_active=True).first()
        return models.LandUseType.objects.filter(module_types__class_name="AnnualCropland", is_active=True).first()

    @factory.lazy_attribute
    def land_use_type_w(self):
        """Get appropriate land use type for AnnualCropland based on project climate."""
        if hasattr(self, "activity") and self.activity and self.activity.project:
            climate = self.activity.project.climate
            moisture = self.activity.project.moisture
            return models.LandUseType.objects.filter(module_types__class_name="AnnualCropland", climates=climate, moistures=moisture, is_active=True).first()
        return models.LandUseType.objects.filter(module_types__class_name="AnnualCropland", is_active=True).first()

    @factory.lazy_attribute
    def land_use_type_wo(self):
        """Get appropriate land use type for AnnualCropland based on project climate."""
        if hasattr(self, "activity") and self.activity and self.activity.project:
            climate = self.activity.project.climate
            moisture = self.activity.project.moisture
            return models.LandUseType.objects.filter(module_types__class_name="AnnualCropland", climates=climate, moistures=moisture, is_active=True).first()
        return models.LandUseType.objects.filter(module_types__class_name="AnnualCropland", is_active=True).first()

    @factory.lazy_attribute
    def tillage_management_type_start(self):
        return models.TillageManagementType.objects.order_by("?").first()

    @factory.lazy_attribute
    def tillage_management_type_w(self):
        return models.TillageManagementType.objects.order_by("?").first()

    @factory.lazy_attribute
    def tillage_management_type_wo(self):
        return models.TillageManagementType.objects.order_by("?").first()

    @factory.lazy_attribute
    def organic_input_type_start(self):
        return models.OrganicInputType.objects.order_by("?").filter(is_active=True).first()

    @factory.lazy_attribute
    def organic_input_type_w(self):
        return models.OrganicInputType.objects.order_by("?").filter(is_active=True).first()

    @factory.lazy_attribute
    def organic_input_type_wo(self):
        return models.OrganicInputType.objects.order_by("?").filter(is_active=True).first()

    @factory.lazy_attribute
    def residue_management_type_start(self):
        return models.ResidueManagementType.objects.order_by("?").first()

    @factory.lazy_attribute
    def residue_management_type_w(self):
        return models.ResidueManagementType.objects.order_by("?").first()

    @factory.lazy_attribute
    def residue_management_type_wo(self):
        return models.ResidueManagementType.objects.order_by("?").first()

    @classmethod
    def get_validated_data(cls, **kwargs):
        """
        Get validated data in the format expected by API calls.

        Returns:
            dict: Configuration data with IDs for API calls
        """
        instance = cls.build(**kwargs)
        return {
            "land_use_type_start": instance.land_use_type_start.id,
            "land_use_type_w": instance.land_use_type_w.id,
            "land_use_type_wo": instance.land_use_type_wo.id,
            "tillage_management_type_start": instance.tillage_management_type_start.id,
            "tillage_management_type_w": instance.tillage_management_type_w.id,
            "tillage_management_type_wo": instance.tillage_management_type_wo.id,
            "organic_input_type_start": instance.organic_input_type_start.id,
            "organic_input_type_w": instance.organic_input_type_w.id,
            "organic_input_type_wo": instance.organic_input_type_wo.id,
            "residue_management_type_start": instance.residue_management_type_start.id,
            "residue_management_type_w": instance.residue_management_type_w.id,
            "residue_management_type_wo": instance.residue_management_type_wo.id,
        }


class UnitTestForestManagementFactory(DjangoModelFactory):
    """
    ForestManagement factory based on unit test patterns.
    """

    class Meta:
        model = models.ForestManagement

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    @factory.lazy_attribute
    def land_use_type_start(self):
        return _resolve_land_use_type(self, "ForestManagement")

    forest_type = factory.LazyAttribute(lambda obj: models.ForestType.objects.get(name_en="Natural"))
    forest_condition_type = factory.LazyAttribute(lambda obj: models.ForestConditionType.objects.get(name_en="Primary"))

    rotation_start_year_t2_start = 1
    rotation_start_year_t2_w = 2
    rotation_start_year_t2_wo = 0
    rotation_length_yrs_start = 2
    rotation_length_yrs_w = 2
    rotation_length_yrs_wo = 2

    # land_use_type resolved via module-level _resolve_land_use_type()


class UnitTestGrasslandFactory(DjangoModelFactory):
    """
    Grassland factory based on unit test patterns.
    """

    class Meta:
        model = models.Grassland

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    @factory.lazy_attribute
    def land_use_type_start(self):
        return _resolve_land_use_type(self, "Grassland")

    @factory.lazy_attribute
    def land_use_type_w(self):
        return _resolve_land_use_type(self, "Grassland")

    @factory.lazy_attribute
    def land_use_type_wo(self):
        return _resolve_land_use_type(self, "Grassland")

    grassland_management_type_start = factory.LazyAttribute(lambda obj: models.GrasslandManagementType.objects.first())
    grassland_management_type_w = factory.LazyAttribute(lambda obj: models.GrasslandManagementType.objects.first())
    grassland_management_type_wo = factory.LazyAttribute(lambda obj: models.GrasslandManagementType.objects.first())

    is_fire_used_start = False  # Use predictable values for unit tests
    is_fire_used_w = False
    is_fire_used_wo = False

    fire_periodicity_start = 2
    fire_periodicity_w = 2
    fire_periodicity_wo = 2

    fire_impact_start = 0.5
    fire_impact_w = 0.5
    fire_impact_wo = 0.5

    yield_start = 50.0
    yield_w = 60.0
    yield_wo = 50.0

    # land_use_type resolved via module-level _resolve_land_use_type()


class UnitTestAquacultureFactory(DjangoModelFactory):
    """
    Aquaculture factory based on unit test patterns.
    """

    class Meta:
        model = models.Aquaculture

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    annual_production_start = 100.0
    annual_production_w = 120.0
    annual_production_wo = 100.0


class UnitTestLivestockFactory(DjangoModelFactory):
    """
    Livestock factory based on unit test patterns.
    """

    class Meta:
        model = models.Livestock

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    livestock_category_type = factory.LazyAttribute(lambda obj: models.LivestockCategoryType.objects.filter(is_active=True).first())

    livestock_production_type_start = factory.LazyAttribute(lambda obj: models.LivestockProductionType.objects.first())
    livestock_production_type_w = factory.LazyAttribute(lambda obj: models.LivestockProductionType.objects.first())
    livestock_production_type_wo = factory.LazyAttribute(lambda obj: models.LivestockProductionType.objects.first())

    production_start = 50.0
    production_w = 60.0
    production_wo = 50.0

    heads_number_start = 100
    heads_number_w = 120
    heads_number_wo = 100

    complementary_manure_management_start = factory.LazyAttribute(lambda obj: models.ManureManagementType.objects.first())
    complementary_manure_management_w = factory.LazyAttribute(lambda obj: models.ManureManagementType.objects.first())
    complementary_manure_management_wo = factory.LazyAttribute(lambda obj: models.ManureManagementType.objects.first())


class UnitTestCoastalWetlandFactory(DjangoModelFactory):
    """
    CoastalWetland factory based on unit test patterns.
    """

    class Meta:
        model = models.CoastalWetland

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    land_use_type = factory.LazyAttribute(lambda obj: models.LandUseType.objects.filter(module_types__class_name="CoastalWetland", is_active=True).first())

    area_under_drainage_start = 50.0
    area_under_drainage_w = 30.0
    area_under_drainage_wo = 50.0

    avg_salinity_t2 = factory.LazyAttribute(lambda obj: models.SalinityType.objects.get(value="<18"))


class UnitTestWaterbodyFactory(DjangoModelFactory):
    """
    Waterbody factory based on unit test patterns.
    """

    class Meta:
        model = models.Waterbody

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    waterbody_type = factory.LazyAttribute(lambda obj: models.WaterbodyType.objects.first())

    trophic_type_start = factory.LazyAttribute(lambda obj: models.TrophicType.objects.first())
    trophic_type_w = factory.LazyAttribute(lambda obj: models.TrophicType.objects.first())
    trophic_type_wo = factory.LazyAttribute(lambda obj: models.TrophicType.objects.first())


class UnitTestFloodedRiceFactory(DjangoModelFactory):
    """
    FloodedRice factory based on unit test patterns.
    """

    class Meta:
        model = models.FloodedRice

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    water_management_type_before_cultivation_start = factory.LazyAttribute(lambda obj: models.WaterManagementTypeBeforeCultivation.objects.first())
    water_management_type_before_cultivation_w = factory.LazyAttribute(lambda obj: models.WaterManagementTypeBeforeCultivation.objects.first())
    water_management_type_before_cultivation_wo = factory.LazyAttribute(lambda obj: models.WaterManagementTypeBeforeCultivation.objects.first())

    water_management_type_after_cultivation_start = factory.LazyAttribute(lambda obj: models.WaterManagementTypeAfterCultivation.objects.first())
    water_management_type_after_cultivation_w = factory.LazyAttribute(lambda obj: models.WaterManagementTypeAfterCultivation.objects.first())
    water_management_type_after_cultivation_wo = factory.LazyAttribute(lambda obj: models.WaterManagementTypeAfterCultivation.objects.first())

    organic_amendment_type_start = factory.LazyAttribute(lambda obj: models.OrganicAmendmentType.objects.first())
    organic_amendment_type_w = factory.LazyAttribute(lambda obj: models.OrganicAmendmentType.objects.first())
    organic_amendment_type_wo = factory.LazyAttribute(lambda obj: models.OrganicAmendmentType.objects.first())


# Value Chain Module Factories (Parent + Submodule pattern)


class UnitTestTransportFactory(DjangoModelFactory):
    """
    Transport parent module factory.
    """

    class Meta:
        model = models.Transport

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))


class UnitTestTransportEntryFactory(DjangoModelFactory):
    """
    TransportEntry submodule factory based on unit test patterns.
    """

    class Meta:
        model = models.TransportEntry

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    fuel_type_start = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())
    fuel_type_w = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())
    fuel_type_wo = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())

    quantity_consumed_per_year_start = 100.0
    quantity_consumed_per_year_w = 120.0
    quantity_consumed_per_year_wo = 100.0

    energy_ef_co2_t2 = 2.5
    energy_ef_ch4_t2 = 0.1
    energy_ef_n2o_t2 = 0.05


class UnitTestPackagingFactory(DjangoModelFactory):
    """
    Packaging parent module factory.
    """

    class Meta:
        model = models.Packaging

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))


class UnitTestPackagingEntryFactory(DjangoModelFactory):
    """
    PackagingEntry submodule factory based on unit test patterns.
    """

    class Meta:
        model = models.PackagingEntry

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    packaging_material_type_start = factory.LazyAttribute(lambda obj: models.PackagingMaterialType.objects.first())
    packaging_material_type_w = factory.LazyAttribute(lambda obj: models.PackagingMaterialType.objects.first())
    packaging_material_type_wo = factory.LazyAttribute(lambda obj: models.PackagingMaterialType.objects.first())

    kg_of_packaging_material_start = 10.0
    kg_of_packaging_material_w = 12.0
    kg_of_packaging_material_wo = 10.0

    is_electric = False

    quantity_consumed_per_year_start = 100.0
    quantity_consumed_per_year_w = 120.0
    quantity_consumed_per_year_wo = 100.0


class UnitTestStorageFactory(DjangoModelFactory):
    """
    Storage parent module factory.
    """

    class Meta:
        model = models.Storage

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))


class UnitTestStorageEntryFactory(DjangoModelFactory):
    """
    StorageEntry submodule factory based on unit test patterns.
    """

    class Meta:
        model = models.StorageEntry

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    quantity_consumed_per_year_start = 100.0
    quantity_consumed_per_year_w = 120.0
    quantity_consumed_per_year_wo = 100.0

    is_refrigerant_used = False  # Simpler configuration for unit tests


class UnitTestProcessingFactory(DjangoModelFactory):
    """
    Processing parent module factory.
    """

    class Meta:
        model = models.Processing

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))


class UnitTestProcessingEntryFactory(DjangoModelFactory):
    """
    ProcessingEntry submodule factory based on unit test patterns.
    """

    class Meta:
        model = models.ProcessingEntry

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    fuel_type_start = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())
    fuel_type_w = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())
    fuel_type_wo = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())

    quantity_consumed_per_year_start = 100.0
    quantity_consumed_per_year_w = 120.0
    quantity_consumed_per_year_wo = 100.0

    is_water_used = False  # Simpler configuration

    water_use_per_year_start = 0.0
    water_use_per_year_w = 0.0
    water_use_per_year_wo = 0.0


class UnitTestEnergyFactory(DjangoModelFactory):
    """
    Energy parent module factory.
    """

    class Meta:
        model = models.Energy

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))


class UnitTestEnergyEntryFactory(DjangoModelFactory):
    """
    EnergyEntry submodule factory based on unit test patterns.
    """

    class Meta:
        model = models.EnergyEntry

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    fuel_type_start = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())
    fuel_type_w = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())
    fuel_type_wo = factory.LazyAttribute(lambda obj: models.FuelType.objects.first())

    quantity_consumed_per_year_start = 100.0
    quantity_consumed_per_year_w = 120.0
    quantity_consumed_per_year_wo = 100.0


# Fishery Factories


class UnitTestSmallFisheryFactory(DjangoModelFactory):
    """
    SmallFishery factory based on unit test patterns.
    """

    class Meta:
        model = models.SmallFishery

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    fishery_type = factory.LazyAttribute(lambda obj: models.FisheryType.objects.first())

    gear_type_start = factory.LazyAttribute(lambda obj: models.SmallFisheryGearType.objects.first())
    gear_type_w = factory.LazyAttribute(lambda obj: models.SmallFisheryGearType.objects.first())
    gear_type_wo = factory.LazyAttribute(lambda obj: models.SmallFisheryGearType.objects.first())

    refrigerant_pc_start = 0.1
    refrigerant_pc_w = 0.1
    refrigerant_pc_wo = 0.1

    refrigerant_gwp = 1810

    total_catch_yr_start = 100.0
    total_catch_yr_w = 120.0
    total_catch_yr_wo = 100.0

    ice_preserved_catch_pc_start = 0.5
    ice_preserved_catch_pc_w = 0.5
    ice_preserved_catch_pc_wo = 0.5


class UnitTestLargeFisheryFactory(DjangoModelFactory):
    """
    LargeFishery factory based on unit test patterns.
    """

    class Meta:
        model = models.LargeFishery

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    fish_type = factory.LazyAttribute(lambda obj: models.FishType.objects.first())

    gear_type_start = factory.LazyAttribute(lambda obj: models.LargeFisheryGearType.objects.first())
    gear_type_w = factory.LazyAttribute(lambda obj: models.LargeFisheryGearType.objects.first())
    gear_type_wo = factory.LazyAttribute(lambda obj: models.LargeFisheryGearType.objects.first())

    refrigerant_pc_start = 0.1
    refrigerant_pc_w = 0.1
    refrigerant_pc_wo = 0.1

    refrigerant_gwp = 1810

    total_catch_yr_start = 500.0
    total_catch_yr_w = 600.0
    total_catch_yr_wo = 500.0

    ice_preserved_catch_pc_start = 0.7
    ice_preserved_catch_pc_w = 0.7
    ice_preserved_catch_pc_wo = 0.7


# Infrastructure Factories


class UnitTestSettlementFactory(DjangoModelFactory):
    """
    Settlement factory based on unit test patterns.
    """

    class Meta:
        model = models.Settlement

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    settlement_type_start = factory.LazyAttribute(lambda obj: models.SettlementType.objects.first())
    settlement_type_w = factory.LazyAttribute(lambda obj: models.SettlementType.objects.first())
    settlement_type_wo = factory.LazyAttribute(lambda obj: models.SettlementType.objects.first())

    biomass_t2_start = 1.0
    biomass_t2_w = 1.2
    biomass_t2_wo = 1.0


class UnitTestIrrigationFactory(DjangoModelFactory):
    """
    Irrigation parent module factory.
    """

    class Meta:
        model = models.Irrigation

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))


class UnitTestIrrigationSystemFactory(DjangoModelFactory):
    """
    IrrigationSystem submodule factory.
    """

    class Meta:
        model = models.IrrigationSystem

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    irrigation_system_type = factory.LazyAttribute(lambda obj: models.IrrigationSystemType.objects.filter(module_types__class_name="IrrigationSystem").first())

    ha_start = 50.0
    ha_w = 60.0
    ha_wo = 50.0

    ef_t2_start = 2.0
    ef_t2_w = 2.0
    ef_t2_wo = 2.0


# Other Factories


class UnitTestOtherLandFactory(DjangoModelFactory):
    """
    OtherLand factory based on unit test patterns.
    """

    class Meta:
        model = models.OtherLand

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    @factory.lazy_attribute
    def land_use_type_start(self):
        return _resolve_land_use_type(self, "OtherLand")

    @factory.lazy_attribute
    def land_use_type_w(self):
        return _resolve_land_use_type(self, "OtherLand")

    @factory.lazy_attribute
    def land_use_type_wo(self):
        return _resolve_land_use_type(self, "OtherLand")

    is_degraded_land_start = False
    is_degraded_land_w = False
    is_degraded_land_wo = False

    # land_use_type resolved via module-level _resolve_land_use_type()


class UnitTestOrganicSoilFactory(DjangoModelFactory):
    """
    OrganicSoil factory for land use change scenarios.
    """

    class Meta:
        model = models.OrganicSoil

    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    drainage_area_start = 50.0
    drainage_area_w = 30.0
    drainage_area_wo = 50.0

    area_not_drained_start = 100.0
    area_not_drained_w = 120.0
    area_not_drained_wo = 100.0

    ditches_area_start = 10.0
    ditches_area_w = 8.0
    ditches_area_wo = 10.0

    fire_type_start = factory.LazyAttribute(lambda obj: models.FireType.objects.first())
    fire_type_w = factory.LazyAttribute(lambda obj: models.FireType.objects.first())
    fire_type_wo = factory.LazyAttribute(lambda obj: models.FireType.objects.first())

    soil_fire_periodicity_start = 2.0
    soil_fire_periodicity_w = 2.0
    soil_fire_periodicity_wo = 2.0

    soil_fire_impact_percentage_start = 0.3
    soil_fire_impact_percentage_w = 0.3
    soil_fire_impact_percentage_wo = 0.3


class UnitTestLandUseChangeFactory(DjangoModelFactory):
    """
    LandUseChange factory for land use change scenarios.
    """

    class Meta:
        model = models.LandUseChange

    area = 150
    status = factory.LazyAttribute(lambda obj: models.StatusType.objects.get(name_en="READY"))

    # Module types are set based on specific scenarios
    module_type_start = factory.LazyAttribute(lambda obj: models.ModuleType.objects.get(class_name="AnnualCropland"))
    module_type_w = factory.LazyAttribute(lambda obj: models.ModuleType.objects.get(class_name="ForestManagement"))
    module_type_wo = factory.LazyAttribute(lambda obj: models.ModuleType.objects.get(class_name="AnnualCropland"))

    is_fire_used_start = False
    is_fire_used_w = False
    is_fire_used_wo = False

    dry_matter_start = 0.0
    dry_matter_w = 0.0
    dry_matter_wo = 0.0


# Utility Functions for Unit Testing


def get_unit_test_factory(module_class_name):
    """
    Get the appropriate unit test factory for a given module class name.

    Args:
        module_class_name (str): The class name of the module (e.g., "AnnualCropland")

    Returns:
        Factory class or None if not found
    """
    factory_mapping = {
        "AnnualCropland": UnitTestAnnualCroplandFactory,
        "ForestManagement": UnitTestForestManagementFactory,
        "Grassland": UnitTestGrasslandFactory,
        "Aquaculture": UnitTestAquacultureFactory,
        "Livestock": UnitTestLivestockFactory,
        "CoastalWetland": UnitTestCoastalWetlandFactory,
        "Waterbody": UnitTestWaterbodyFactory,
        "FloodedRice": UnitTestFloodedRiceFactory,
        "Transport": UnitTestTransportFactory,
        "TransportEntry": UnitTestTransportEntryFactory,
        "Packaging": UnitTestPackagingFactory,
        "PackagingEntry": UnitTestPackagingEntryFactory,
        "Storage": UnitTestStorageFactory,
        "StorageEntry": UnitTestStorageEntryFactory,
        "Processing": UnitTestProcessingFactory,
        "ProcessingEntry": UnitTestProcessingEntryFactory,
        "Energy": UnitTestEnergyFactory,
        "EnergyEntry": UnitTestEnergyEntryFactory,
        "SmallFishery": UnitTestSmallFisheryFactory,
        "LargeFishery": UnitTestLargeFisheryFactory,
        "Settlement": UnitTestSettlementFactory,
        "Irrigation": UnitTestIrrigationFactory,
        "IrrigationSystem": UnitTestIrrigationSystemFactory,
        "OtherLand": UnitTestOtherLandFactory,
        "OrganicSoil": UnitTestOrganicSoilFactory,
        "LandUseChange": UnitTestLandUseChangeFactory,
        "Project": UnitTestProjectFactory,
        "Activity": UnitTestActivityFactory,
    }

    return factory_mapping.get(module_class_name)


def create_unit_test_module_with_defaults(module_class_name, **kwargs):
    """
    Create a module instance using unit test factories with sensible defaults.

    Args:
        module_class_name (str): The class name of the module
        **kwargs: Additional parameters to override defaults

    Returns:
        Module instance or None if factory not found
    """
    factory_class = get_unit_test_factory(module_class_name)
    if factory_class:
        return factory_class.create(**kwargs)
    return None


"""
Usage Examples:

# Create a project with reliable defaults for unit testing
project = UnitTestProjectFactory.create()

# Create an activity for the project  
activity = UnitTestActivityFactory.create(project=project)

# Create modules with climate-aware defaults
annual_cropland = UnitTestAnnualCroplandFactory.create(activity=activity)
forest_management = UnitTestForestManagementFactory.create(activity=activity)

# Create value chain modules with submodules
transport = UnitTestTransportFactory.create(activity=activity)
transport_entry = UnitTestTransportEntryFactory.create(parent=transport)

# Use utility function to get any factory
factory = get_unit_test_factory("AnnualCropland")
module = factory.create(activity=activity)

# Create module with overridden defaults
module = create_unit_test_module_with_defaults("Grassland", activity=activity, area=300)
"""
