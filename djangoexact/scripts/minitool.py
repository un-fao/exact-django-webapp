import pandas as pd
from dataclasses import dataclass, field
import os
import logging
import itertools
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor
import django
import traceback
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Callable
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProcessorError(Exception):
    """Custom exception for data processing errors"""

    pass


@dataclass
class ProcessingResult:
    """Container for processing results with error handling"""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def success_result(cls, data: Dict[str, Any]) -> "ProcessingResult":
        return cls(success=True, data=data)

    @classmethod
    def error_result(cls, error_type: str, error_message: str, combination: Tuple, traceback_str: str = None) -> "ProcessingResult":
        return cls(success=False, error={"error_type": error_type, "error_message": error_message, "traceback": traceback_str, "combination": combination})


@dataclass
class BaseData:
    """Base data class for all module data"""

    module: Any
    climate: str = None
    moisture: str = None
    soil_type: str = None
    region: str = None
    total: float = 0.0

    def __post_init__(self):
        """Initialize common fields from module"""
        activity = self.module.activity
        project = activity.project

        self.climate = activity.climate_t2.name if activity.climate_t2 else project.climate.name
        self.moisture = activity.moisture_t2.name if activity.moisture_t2 else project.moisture.name
        self.soil_type = activity.soil_type_t2.name if activity.soil_type_t2 else project.soil_type.name
        self.region = project.country.region

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "module": self.module.__class__.__name__,
            "climate": self.climate,
            "moisture": self.moisture,
            "soil_type": self.soil_type,
            "region": self.region,
            "total": self.total,
        }


from enum import Enum
from typing import Union, List, Dict, Any, Optional, Tuple, Callable


class FieldType(Enum):
    """Enumeration of field types for automatic processing"""

    STRING = "string"  # String fields (e.g., names)
    BOOLEAN = "boolean"  # Boolean fields
    NUMERIC = "numeric"  # Numeric fields (int, float)
    FOREIGN_KEY = "foreign_key"  # Foreign key fields (get .name)
    MANY_TO_MANY = "many_to_many"  # Many-to-many fields
    CUSTOM = "custom"  # Custom processing required
    COMPUTED = "computed"  # Computed fields (calculated values)
    CONDITIONAL = "conditional"  # Conditional fields (depends on other fields)


@dataclass
class FieldMapping:
    """Configuration for field mapping with type information"""

    field_name: str
    field_type: FieldType
    start_suffix: str = "_start"
    with_suffix: str = "_w"
    without_suffix: str = "_wo"
    custom_processor: Optional[Callable] = None
    skip_processing: bool = False  # Skip automatic processing for this field

    def get_field_names(self) -> Dict[str, str]:
        """Get all field name variations"""
        return {"start": f"{self.field_name}{self.start_suffix}", "with": f"{self.field_name}{self.with_suffix}", "without": f"{self.field_name}{self.without_suffix}"}


class FieldMappingBuilder:
    """Utility class for building field mappings more easily"""

    @staticmethod
    def foreign_key(field_name: str, **kwargs) -> FieldMapping:
        """Create a foreign key field mapping"""
        return FieldMapping(field_name, FieldType.FOREIGN_KEY, **kwargs)

    @staticmethod
    def boolean(field_name: str, **kwargs) -> FieldMapping:
        """Create a boolean field mapping"""
        return FieldMapping(field_name, FieldType.BOOLEAN, **kwargs)

    @staticmethod
    def numeric(field_name: str, **kwargs) -> FieldMapping:
        """Create a numeric field mapping"""
        return FieldMapping(field_name, FieldType.NUMERIC, **kwargs)

    @staticmethod
    def string(field_name: str, **kwargs) -> FieldMapping:
        """Create a string field mapping"""
        return FieldMapping(field_name, FieldType.STRING, **kwargs)

    @staticmethod
    def many_to_many(field_name: str, **kwargs) -> FieldMapping:
        """Create a many-to-many field mapping"""
        return FieldMapping(field_name, FieldType.MANY_TO_MANY, **kwargs)

    @staticmethod
    def computed(field_name: str, processor: Callable, **kwargs) -> FieldMapping:
        """Create a computed field mapping"""
        return FieldMapping(field_name, FieldType.COMPUTED, custom_processor=processor, **kwargs)

    @staticmethod
    def conditional(field_name: str, processor: Callable, **kwargs) -> FieldMapping:
        """Create a conditional field mapping"""
        return FieldMapping(field_name, FieldType.CONDITIONAL, custom_processor=processor, **kwargs)

    @staticmethod
    def custom(field_name: str, processor: Callable, **kwargs) -> FieldMapping:
        """Create a custom field mapping"""
        return FieldMapping(field_name, FieldType.CUSTOM, custom_processor=processor, **kwargs)


class ModuleDataBuilder(ABC):
    """Abstract base class for building module-specific data"""

    def __init__(self):
        self._field_mappings: Optional[List[FieldMapping]] = None

    @abstractmethod
    def get_field_mappings(self) -> List[FieldMapping]:
        """Get field mappings for the module"""
        pass

    def get_custom_fields(self, module: Any) -> Dict[str, Any]:
        """Get custom fields that don't follow the standard pattern"""
        return {}

    def build_data(self, module: Any) -> Dict[str, Any]:
        """Build data dictionary for the module using field mappings"""
        base_data = BaseData(module)
        data = base_data.to_dict()

        # Process standard field mappings
        for field_mapping in self.get_field_mappings():
            if field_mapping.skip_processing:
                continue

            field_names = field_mapping.get_field_names()

            if field_mapping.field_type == FieldType.STRING:
                self._process_string_field(module, data, field_mapping, field_names)
            elif field_mapping.field_type == FieldType.BOOLEAN:
                self._process_boolean_field(module, data, field_mapping, field_names)
            elif field_mapping.field_type == FieldType.NUMERIC:
                self._process_numeric_field(module, data, field_mapping, field_names)
            elif field_mapping.field_type == FieldType.FOREIGN_KEY:
                self._process_foreign_key_field(module, data, field_mapping, field_names)
            elif field_mapping.field_type == FieldType.MANY_TO_MANY:
                self._process_many_to_many_field(module, data, field_mapping, field_names)
            elif field_mapping.field_type == FieldType.CUSTOM and field_mapping.custom_processor:
                field_mapping.custom_processor(module, data, field_mapping, field_names)
            elif field_mapping.field_type == FieldType.COMPUTED and field_mapping.custom_processor:
                field_mapping.custom_processor(module, data, field_mapping, field_names)
            elif field_mapping.field_type == FieldType.CONDITIONAL and field_mapping.custom_processor:
                field_mapping.custom_processor(module, data, field_mapping, field_names)

        # Add custom fields
        data.update(self.get_custom_fields(module))

        return data

    def _process_string_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process string fields"""
        start_value = getattr(module, field_names["start"], None)
        with_value = getattr(module, field_names["with"], None)

        data[field_names["start"]] = start_value
        data[field_names["with"]] = with_value
        data[field_names["without"]] = start_value

    def _process_boolean_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process boolean fields"""
        start_value = getattr(module, field_names["start"], None)
        with_value = getattr(module, field_names["with"], None)

        data[field_names["start"]] = start_value
        data[field_names["with"]] = with_value
        data[field_names["without"]] = start_value

    def _process_numeric_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process numeric fields"""
        start_value = getattr(module, field_names["start"], None)
        with_value = getattr(module, field_names["with"], None)

        data[field_names["start"]] = start_value
        data[field_names["with"]] = with_value
        data[field_names["without"]] = start_value

    def _process_foreign_key_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process foreign key fields (extract .name)"""
        start_value = getattr(module, field_names["start"], None)
        with_value = getattr(module, field_names["with"], None)

        data[field_names["start"]] = start_value.name if start_value else None
        data[field_names["with"]] = with_value.name if with_value else None
        data[field_names["without"]] = start_value.name if start_value else None

    def _process_many_to_many_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process many-to-many fields"""
        start_value = getattr(module, field_names["start"], None)
        with_value = getattr(module, field_names["with"], None)

        # For many-to-many, we might want to get all names
        data[field_names["start"]] = [item.name for item in start_value.all()] if start_value else []
        data[field_names["with"]] = [item.name for item in with_value.all()] if with_value else []
        data[field_names["without"]] = [item.name for item in start_value.all()] if start_value else []


class AnnualCroplandDataBuilder(ModuleDataBuilder):
    """Data builder for Annual Cropland modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("land_use_type"),
            FieldMappingBuilder.foreign_key("tillage_management_type"),
            FieldMappingBuilder.foreign_key("organic_input_type"),
            FieldMappingBuilder.foreign_key("residue_management_type"),
        ]


class LivestockDataBuilder(ModuleDataBuilder):
    """Data builder for Livestock modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("livestock_production_type"),
            FieldMappingBuilder.foreign_key("complementary_manure_management_type"),
            FieldMappingBuilder.foreign_key("livestock_category_type"),
            FieldMappingBuilder.numeric("heads_number"),
        ]


class GrasslandDataBuilder(ModuleDataBuilder):
    """Data builder for Grassland modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("grassland_management_type"),
            FieldMappingBuilder.boolean("is_fire_used"),
            FieldMappingBuilder.numeric("fire_periodicity"),
            FieldMappingBuilder.numeric("fire_impact"),
            FieldMappingBuilder.numeric("yield"),
        ]


class FloodedRiceDataBuilder(ModuleDataBuilder):
    """Data builder for Flooded Rice modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("water_management_type_before_cultivation"),
            FieldMappingBuilder.foreign_key("water_management_type_after_cultivation"),
            FieldMappingBuilder.foreign_key("organic_amendment_type"),
        ]


class PerennialCroplandDataBuilder(ModuleDataBuilder):
    """Data builder for Perennial Cropland modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("land_use_type"),
            FieldMappingBuilder.foreign_key("tillage_management_type"),
            FieldMappingBuilder.foreign_key("organic_input_type"),
            FieldMappingBuilder.boolean("is_biomass_burned"),
            FieldMappingBuilder.numeric("fire_periodicity_t2"),
        ]


class ForestManagementDataBuilder(ModuleDataBuilder):
    """Data builder for Forest Management modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("forest_type"),
            FieldMappingBuilder.foreign_key("forest_condition_type"),
            FieldMappingBuilder.numeric("average_yearly_degradation_percentage"),
        ]


# Implementation example of a more complex module
# class ForestManagementDataBuilder(ModuleDataBuilder):
#     """Example data builder for Forest Management modules - shows extensibility"""

#     def get_field_mappings(self) -> List[FieldMapping]:
#         return [
#             FieldMappingBuilder.foreign_key("forest_type"),
#             FieldMappingBuilder.foreign_key("management_type"),
#             FieldMappingBuilder.numeric("area"),
#             FieldMappingBuilder.boolean("is_selective_logging"),
#             FieldMappingBuilder.numeric("logging_intensity"),
#             # Example of a computed field that depends on other fields
#             FieldMappingBuilder.computed("carbon_impact", self._compute_carbon_impact),
#             # Example of a conditional field based on management type
#             FieldMappingBuilder.conditional("management_category", self._categorize_management),
#         ]

#     def get_custom_fields(self, module: Any) -> Dict[str, Any]:
#         """Get custom fields that don't follow the standard pattern"""
#         return {
#             "forest_age": getattr(module, "forest_age", None),
#             "biodiversity_index": getattr(module, "biodiversity_index", None),
#         }

#     def _compute_carbon_impact(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
#         """Custom processor for computing carbon impact"""
#         area = getattr(module, "area_start", 0) or 0
#         logging_intensity = getattr(module, "logging_intensity_start", 0) or 0

#         # Simplified carbon impact calculation
#         carbon_impact = area * logging_intensity * 0.5

#         data["carbon_impact_start"] = carbon_impact
#         data["carbon_impact_w"] = carbon_impact * 0.8  # Assume 20% reduction with intervention
#         data["carbon_impact_wo"] = carbon_impact

#     def _categorize_management(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
#         """Custom processor for categorizing management type"""
#         management_type = getattr(module, "management_type_start", None)

#         def get_category(mgmt_type) -> str:
#             if not mgmt_type:
#                 return "unknown"
#             mgmt_name = mgmt_type.name.lower()
#             if "conservation" in mgmt_name:
#                 return "conservation"
#             elif "production" in mgmt_name:
#                 return "production"
#             elif "mixed" in mgmt_name:
#                 return "mixed"
#             else:
#                 return "other"

#         start_category = get_category(getattr(module, "management_type_start", None))
#         with_category = get_category(getattr(module, "management_type_w", None))

#         data["management_category_start"] = start_category
#         data["management_category_w"] = with_category
#         data["management_category_wo"] = start_category


class ModuleDataBuilderRegistry:
    """Registry for module data builders"""

    def __init__(self):
        self._builders: Dict[str, ModuleDataBuilder] = {}
        self._register_default_builders()

    def _register_default_builders(self):
        """Register default builders"""
        self.register("AnnualCropland", AnnualCroplandDataBuilder())
        self.register("Livestock", LivestockDataBuilder())
        self.register("Grassland", GrasslandDataBuilder())
        self.register("FloodedRice", FloodedRiceDataBuilder())
        self.register("PerennialCropland", PerennialCroplandDataBuilder())

    def register(self, module_name: str, builder: ModuleDataBuilder):
        """Register a new builder"""
        self._builders[module_name] = builder

    def get_builder(self, module_name: str) -> ModuleDataBuilder:
        """Get builder for module"""
        if module_name not in self._builders:
            raise ValueError(f"No builder registered for module: {module_name}")
        return self._builders[module_name]

    def build_data(self, module: Any) -> Dict[str, Any]:
        """Build data for a module using the appropriate builder"""
        module_name = module.__class__.__name__
        builder = self.get_builder(module_name)
        return builder.build_data(module)


class ModuleProcessor(ABC):
    """Abstract base class for module processors"""

    def __init__(self, data_builder_registry: ModuleDataBuilderRegistry):
        self.data_builder_registry = data_builder_registry

    @abstractmethod
    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        """Create a module instance from combination"""
        pass

    def process_combination(self, combination: Tuple) -> ProcessingResult:
        """Process a single combination"""
        try:
            # Import inside function for multiprocessing compatibility
            import api.tests.factories as factories
            import api.calculators as calculators
            import api.models as models

            # Suppress logging in worker processes
            logging.getLogger().setLevel(logging.CRITICAL)

            # Create module
            module = self.create_module(combination, factories, models)

            # Calculate result
            balance = calculators.CalculatorFactory().calculate_result(module)[0][2]

            # Build data
            data = self.data_builder_registry.build_data(module)
            data["total"] = balance

            return ProcessingResult.success_result(data)

        except Exception as e:
            return ProcessingResult.error_result(type(e).__name__, str(e), combination, traceback.format_exc())


class GrasslandProcessor(ModuleProcessor):
    """Processor for Grassland modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            grassland_management_type_start,
            grassland_management_type_w,
            is_fire_used_start,
            is_fire_used_w,
            fire_periodicity_start,
            fire_periodicity_w,
            fire_impact_start,
            fire_impact_w,
            yield_start,
            yield_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.GrasslandFactory.build(
            activity=a,
            area=1,
            grassland_management_type_start=grassland_management_type_start,
            grassland_management_type_w=grassland_management_type_w,
            grassland_management_type_wo=grassland_management_type_start,
            is_fire_used_start=is_fire_used_start,
            is_fire_used_w=is_fire_used_w,
            is_fire_used_wo=is_fire_used_start,
            fire_periodicity_start=fire_periodicity_start,
            fire_periodicity_w=fire_periodicity_w,
            fire_periodicity_wo=fire_periodicity_start,
            fire_impact_start=fire_impact_start,
            fire_impact_w=fire_impact_w,
            fire_impact_wo=fire_impact_start,
            yield_start=yield_start,
            yield_w=yield_w,
            yield_wo=yield_start,
            land_use_type_start=models.LandUseType.objects.get(name="Grassland"),
            land_use_type_w=models.LandUseType.objects.get(name="Grassland"),
            land_use_type_wo=models.LandUseType.objects.get(name="Grassland"),
        )
        return module


class LivestockProcessor(ModuleProcessor):
    """Processor for Livestock modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            livestock_category_type,
            livestock_production_type_start,
            livestock_production_type_w,
            heads_number_start,
            heads_number_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.LivestockFactory.build(
            activity=a,
            livestock_category_type=livestock_category_type,
            livestock_production_type_start=livestock_production_type_start,
            livestock_production_type_w=livestock_production_type_w,
            livestock_production_type_wo=livestock_production_type_start,
            heads_number_start=heads_number_start,
            heads_number_w=heads_number_w,
            heads_number_wo=heads_number_start,
        )
        return module


class AnnualCroplandProcessor(ModuleProcessor):
    """Processor for Annual Cropland modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            land_use_type_start,
            land_use_type_w,
            tillage_management_start,
            tillage_management_w,
            organic_input_type_start,
            organic_input_type_w,
            residue_management_type_start,
            residue_management_type_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.AnnualCroplandFactory.build(
            activity=a,
            area=1,
            land_use_type_start=land_use_type_start,
            land_use_type_w=land_use_type_w,
            land_use_type_wo=land_use_type_start,
            tillage_management_type_start=tillage_management_start,
            tillage_management_type_w=tillage_management_w,
            tillage_management_type_wo=tillage_management_start,
            organic_input_type_start=organic_input_type_start,
            organic_input_type_w=organic_input_type_w,
            organic_input_type_wo=organic_input_type_start,
            residue_management_type_start=residue_management_type_start,
            residue_management_type_w=residue_management_type_w,
            residue_management_type_wo=residue_management_type_start,
        )
        return module


class FloodedRiceProcessor(ModuleProcessor):
    """Processor for Flooded Rice modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            water_management_type_before_cultivation_start,
            water_management_type_before_cultivation_w,
            water_management_type_after_cultivation_start,
            water_management_type_after_cultivation_w,
            organic_amendment_type_start,
            organic_amendment_type_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.FloodedRiceFactory.build(
            activity=a,
            area=1,
            water_management_type_before_cultivation_start=water_management_type_before_cultivation_start,
            water_management_type_before_cultivation_w=water_management_type_before_cultivation_w,
            water_management_type_before_cultivation_wo=water_management_type_before_cultivation_start,
            water_management_type_after_cultivation_start=water_management_type_after_cultivation_start,
            water_management_type_after_cultivation_w=water_management_type_after_cultivation_w,
            water_management_type_after_cultivation_wo=water_management_type_after_cultivation_start,
            organic_amendment_type_start=organic_amendment_type_start,
            organic_amendment_type_w=organic_amendment_type_w,
            organic_amendment_type_wo=organic_amendment_type_start,
        )
        return module


class PerennialCroplandProcessor(ModuleProcessor):
    """Processor for Perennial Cropland modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            land_use_type_start,
            land_use_type_w,
            organic_input_type_start,
            organic_input_type_w,
            tillage_management_type_start,
            tillage_management_type_w,
            is_biomass_burned_start,
            is_biomass_burned_w,
            fire_periodicity_t2_start,
            fire_periodicity_t2_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.order_by("?").first(),
            implementation_years=0,
            start_year_of_activities=2025,
            last_year_of_accounting=2026,
        )
        a = factories.ActivityFactory.build(project=p, change_rate=models.ChangeRate.objects.get(name="immediate"))
        module = factories.PerennialCroplandFactory.build(
            activity=a,
            area=1,
            land_use_type_start=land_use_type_start,
            land_use_type_w=land_use_type_w,
            land_use_type_wo=land_use_type_start,
            organic_input_type_start=organic_input_type_start,
            organic_input_type_w=organic_input_type_w,
            organic_input_type_wo=organic_input_type_start,
            tillage_management_type_start=tillage_management_type_start,
            tillage_management_type_w=tillage_management_type_w,
            tillage_management_type_wo=tillage_management_type_start,
            is_biomass_burned_start=is_biomass_burned_start,
            is_biomass_burned_w=is_biomass_burned_w,
            is_biomass_burned_wo=is_biomass_burned_start,
            fire_periodicity_t2_start=fire_periodicity_t2_start,
            fire_periodicity_t2_w=fire_periodicity_t2_w,
            fire_periodicity_t2_wo=fire_periodicity_t2_start,
        )
        return module


class ForestManagementProcessor(ModuleProcessor):
    """Processor for Forest Management modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            land_use_type_start,
            forest_type,
            forest_condition_type,
            average_yearly_degradation_percentage_start,
            average_yearly_degradation_percentage_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.ForestManagementFactory.build(
            activity=a,
            land_use_type_start=land_use_type_start,
            land_use_type_w=land_use_type_start,
            land_use_type_wo=land_use_type_start,
            forest_type=forest_type,
            forest_condition_type=forest_condition_type,
            average_yearly_degradation_percentage_start=average_yearly_degradation_percentage_start,
            average_yearly_degradation_percentage_w=average_yearly_degradation_percentage_w,
            average_yearly_degradation_percentage_wo=average_yearly_degradation_percentage_start,
        )
        return module


class ProcessorRegistry:
    """Registry for module processors"""

    def __init__(self, data_builder_registry: ModuleDataBuilderRegistry):
        self._processors: Dict[str, ModuleProcessor] = {}
        self._data_builder_registry = data_builder_registry
        self._register_default_processors()

    def _register_default_processors(self):
        """Register default processors"""
        self.register("Grassland", GrasslandProcessor(self._data_builder_registry))
        self.register("Livestock", LivestockProcessor(self._data_builder_registry))
        self.register("AnnualCropland", AnnualCroplandProcessor(self._data_builder_registry))
        self.register("FloodedRice", FloodedRiceProcessor(self._data_builder_registry))
        self.register("PerennialCropland", PerennialCroplandProcessor(self._data_builder_registry))
        self.register("ForestManagement", ForestManagementProcessor(self._data_builder_registry))

    def register(self, module_name: str, processor: ModuleProcessor):
        """Register a new processor"""
        self._processors[module_name] = processor

    def get_processor(self, module_name: str) -> ModuleProcessor:
        """Get processor for module"""
        if module_name not in self._processors:
            raise ValueError(f"No processor registered for module: {module_name}")
        return self._processors[module_name]


class ClimateMoistureValidator:
    """Validates climate-moisture combinations based on land use types"""

    @staticmethod
    def get_valid_combinations(land_use_types: List, models: Any) -> List[Tuple]:
        """Get valid climate-moisture combinations for given land use types"""
        if not land_use_types:
            # Fallback: use all active climates and their moistures
            active_climates = models.Climate.objects.filter(is_active=True).all()
            valid_combinations = set()
            for climate in active_climates:
                for moisture in climate.moistures.all():
                    valid_combinations.add((climate, moisture))
            return sorted(list(valid_combinations), key=lambda x: (x[0].id, x[1].id))

        # Filter by land use type constraints
        valid_combinations = set()
        for land_use_type in land_use_types:
            for climate in land_use_type.climates.all():
                for moisture in climate.moistures.all():
                    valid_combinations.add((climate, moisture))

        return sorted(list(valid_combinations), key=lambda x: (x[0].id, x[1].id))


class SoilOrganicCarbonValidator:
    """Validates climate-moisture-soiltype combinations by checking SoilOrganicCarbon records"""

    @staticmethod
    def get_valid_combinations(climate_moistures: List[Tuple], soil_types: List, models: Any) -> List[Tuple]:
        """Get valid climate-moisture-soiltype combinations that have SoilOrganicCarbon records"""
        import ipcc.models as ipcc_models

        valid_combinations = []
        total_combinations = len(climate_moistures) * len(soil_types)
        logger.info(f"Validating {total_combinations} climate-moisture-soiltype combinations...")

        for climate, moisture in climate_moistures:
            for soil_type in soil_types:
                try:
                    # Try to get SoilOrganicCarbon record for this combination
                    ipcc_models.SoilOrganicCarbon.objects.get(climate=climate, moisture=moisture, soil_type=soil_type)
                    valid_combinations.append((climate, moisture, soil_type))
                except ipcc_models.SoilOrganicCarbon.DoesNotExist:
                    # This combination is invalid - no SoilOrganicCarbon record exists
                    continue

        logger.info(f"Found {len(valid_combinations)} valid climate-moisture-soiltype combinations out of {total_combinations} total combinations")
        return valid_combinations


class DataManager:
    """Manages data storage and retrieval"""

    def __init__(self, output_dir: str = "scripts/minitool"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def save_data(self, data: List[Dict[str, Any]], errors: List[Dict[str, Any]], module_name: str) -> None:
        """Save data and errors to CSV files"""
        if data:
            df = pd.DataFrame(data)
            filepath = self.output_dir / f"{module_name.lower()}.csv"
            df.to_csv(filepath, index=False)
            logger.info(f"Saved {len(data)} rows to {filepath}")

        if errors:
            errors_df = pd.DataFrame(errors)
            errors_filepath = self.output_dir / f"{module_name.lower()}_errors.csv"
            errors_df.to_csv(errors_filepath, index=False)
            logger.info(f"Saved {len(errors)} errors to {errors_filepath}")


class PermutationComputer:
    """Handles permutation computation with multiprocessing"""

    def __init__(self, processor_registry: ProcessorRegistry, data_manager: DataManager):
        self.processor_registry = processor_registry
        self.data_manager = data_manager

    def django_initializer(self):
        """Initialize Django in child processes"""
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
        logging.getLogger().setLevel(logging.CRITICAL)
        django.setup()

        from django.db import connections

        connections.close_all()

    def chunked_product(self, *iterables, chunk_size: int = 1000):
        """Yield chunks of Cartesian product"""
        it = itertools.product(*iterables)
        while True:
            chunk = list(itertools.islice(it, chunk_size))
            if not chunk:
                break
            yield chunk

    def compute_permutations(self, fields: Dict[str, Any], model: Any, chunk_size: int = 10000, stop_at: Optional[int] = None, is_coastal: bool = False) -> None:
        """Compute permutations for a model"""
        import api.models as models
        import math

        # Get land use types for validation
        land_use_types = []
        if "land_use_type_start" in fields:
            land_use_types.extend(fields["land_use_type_start"])
        if "land_use_type_w" in fields:
            land_use_types.extend(fields["land_use_type_w"])

        # Remove duplicates while preserving order
        seen = set()
        unique_land_use_types = []
        for lut in land_use_types:
            if lut.id not in seen:
                seen.add(lut.id)
                unique_land_use_types.append(lut)

        # Get valid climate-moisture combinations
        climate_moistures = ClimateMoistureValidator.get_valid_combinations(unique_land_use_types, models)

        logger.info(f"Found {len(climate_moistures)} valid climate-moisture combinations for {len(unique_land_use_types)} land use types")

        # Get soil types for validation
        soil_types = models.SoilType.objects.filter(is_coastal=is_coastal, active=True).all()

        # Validate climate-moisture-soiltype combinations using SoilOrganicCarbon records
        valid_combinations = SoilOrganicCarbonValidator.get_valid_combinations(climate_moistures, soil_types, models)

        # Extract unique climate-moisture and soil_type combinations from valid combinations
        valid_climate_moistures = list(set((cm[0], cm[1]) for cm in valid_combinations))
        valid_soil_types = list(set(cm[2] for cm in valid_combinations))

        logger.info(f"After SoilOrganicCarbon validation: {len(valid_climate_moistures)} climate-moisture combinations and {len(valid_soil_types)} soil types")

        # Update fields with validated dimensions
        fields.update(
            {
                "climate_moistures": valid_climate_moistures,
                "soil_types": valid_soil_types,
                "region": models.Region.objects.all(),
            }
        )

        logger.info(f"Computing permutations for {model.__name__}...")

        # Get processor
        processor = self.processor_registry.get_processor(model.__name__)

        # Prepare iterables
        iterables = [list(val) if not isinstance(val, int) else range(val) for val in fields.values()]

        # Compute total permutations
        total = math.prod(len(x) for x in iterables)
        logger.info(f"Total permutations (theoretical): {total:,}")

        data = []
        errors_data = []

        try:
            with ProcessPoolExecutor(max_workers=4, initializer=self.django_initializer) as executor:
                pbar = tqdm(total=total, desc=f"Building {model.__name__} permutations")

                for chunk in self.chunked_product(*iterables, chunk_size=chunk_size):
                    results_iter = executor.map(processor.process_combination, chunk)

                    for result in results_iter:
                        if stop_at and len(data) >= stop_at:
                            # Terminate worker processes
                            for proc in executor._processes.values():
                                proc.terminate()
                            executor.shutdown(wait=False, cancel_futures=True)
                            break

                        if result.success:
                            if result.data.get("total", 0) != 0:
                                data.append(result.data)
                        else:
                            errors_data.append(result.error)

                        pbar.update(1)
                    else:
                        continue
                    break

                pbar.close()

        except KeyboardInterrupt:
            logger.info(f"\nKeyboard interrupt detected! Saving {len(data)} computed rows...")
            try:
                pbar.close()
            except:
                pass
            self.data_manager.save_data(data, errors_data, model.__name__)
            logger.info("Data saved successfully. Exiting gracefully.")
            return

        if not data:
            logger.warning(f"No data for {model.__name__}!")
            return

        self.data_manager.save_data(data, errors_data, model.__name__)


def run():
    """Main execution function"""
    # Suppress log noise
    logging.getLogger().setLevel(logging.CRITICAL)
    logger.info("Running script without noisy logging...")

    # Initialize components
    data_builder_registry = ModuleDataBuilderRegistry()
    processor_registry = ProcessorRegistry(data_builder_registry)
    data_manager = DataManager()
    permutation_computer = PermutationComputer(processor_registry, data_manager)

    # Import models
    import api.models as models

    # Configuration
    CONFIG = {
        "ANNUAL_CROPLAND": False,
        "FLOODED_RICE": False,
        "GRASSLAND": False,
        "LIVESTOCK": False,
        "PERENNIAL_CROPLAND": False,
        "FOREST_MANAGEMENT": True,
        "MAX_ROWS": 10000,
    }

    # Module configurations
    MODULE_CONFIGS = {
        "Grassland": {
            "fields": {
                "grassland_management_type_start": models.GrasslandManagementType.objects.all(),
                "grassland_management_type_w": models.GrasslandManagementType.objects.all(),
                "is_fire_used_start": [True, False],
                "is_fire_used_w": [True, False],
                "fire_periodicity_start": [1],
                "fire_periodicity_w": [1],
                "fire_impact_start": [1, 0],
                "fire_impact_w": [1, 0],
                "yield_start": [1],
                "yield_w": [1],
            },
            "enabled": CONFIG["GRASSLAND"],
        },
        "Livestock": {
            "fields": {
                "livestock_category_types": models.LivestockCategoryType.objects.all(),
                "livestock_production_type_start": models.LivestockProductionType.objects.all(),
                "livestock_production_type_w": models.LivestockProductionType.objects.all(),
                "heads_number_start": [1],
                "heads_number_w": [1],
            },
            "enabled": CONFIG["LIVESTOCK"],
        },
        "AnnualCropland": {
            "fields": {
                "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Annual Cropland").all(),
                "land_use_type_w": models.LandUseType.objects.filter(module_types__name="Annual Cropland").all(),
                "tillage_management_type_start": models.TillageManagementType.objects.all(),
                "tillage_management_type_w": models.TillageManagementType.objects.all(),
                "organic_input_type_start": models.OrganicInputType.objects.all(),
                "organic_input_type_w": models.OrganicInputType.objects.all(),
                "residue_management_type_start": models.ResidueManagementType.objects.all(),
                "residue_management_type_w": models.ResidueManagementType.objects.all(),
            },
            "enabled": CONFIG["ANNUAL_CROPLAND"],
        },
        "FloodedRice": {
            "fields": {
                "water_management_type_before_cultivation_start": models.WaterManagementTypeBeforeCultivation.objects.all(),
                "water_management_type_before_cultivation_w": models.WaterManagementTypeBeforeCultivation.objects.all(),
                "water_management_type_after_cultivation_start": models.WaterManagementTypeAfterCultivation.objects.all(),
                "water_management_type_after_cultivation_w": models.WaterManagementTypeAfterCultivation.objects.all(),
                "organic_amendment_type_start": models.OrganicAmendmentType.objects.all(),
                "organic_amendment_type_w": models.OrganicAmendmentType.objects.all(),
            },
            "enabled": CONFIG["FLOODED_RICE"],
        },
        "PerennialCropland": {
            "fields": {
                "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Perennial Cropland").all(),
                "land_use_type_w": models.LandUseType.objects.filter(module_types__name="Perennial Cropland").all(),
                "organic_input_type_start": models.OrganicInputType.objects.filter(is_active=True).all(),
                "organic_input_type_w": models.OrganicInputType.objects.filter(is_active=True).all(),
                "tillage_management_type_start": models.TillageManagementType.objects.all(),
                "tillage_management_type_w": models.TillageManagementType.objects.all(),
                "is_biomass_burned_start": [True, False],
                "is_biomass_burned_w": [True, False],
                "fire_periodicity_t2_start": [1],
                "fire_periodicity_t2_w": [1],
            },
            "enabled": CONFIG["PERENNIAL_CROPLAND"],
        },
        "ForestManagement": {
            "fields": {
                "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Forest Management").all(),
                "forest_type": models.ForestType.objects.all(),
                "forest_condition_type": models.ForestConditionType.objects.all(),
                "average_yearly_degradation_percentage_start": [0],
                "average_yearly_degradation_percentage_w": [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5],  # 1% to 5% and then 10% to 50%
            },
            "enabled": CONFIG["FOREST_MANAGEMENT"],
        },
    }

    try:
        for module_name, config in MODULE_CONFIGS.items():
            if config["enabled"]:
                model_class = getattr(models, module_name)
                permutation_computer.compute_permutations(config["fields"], model_class, stop_at=CONFIG["MAX_ROWS"])

    except KeyboardInterrupt:
        logger.info(f"\nKeyboard interrupt detected in main run function!")
        logger.info("Script terminated by user. Any completed computations have been saved.")
        return
