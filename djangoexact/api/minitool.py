import pandas as pd
from dataclasses import dataclass
import os
import sys
import logging
import itertools
import time
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor
import traceback
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Callable
from pathlib import Path
from enum import Enum
import io
import yaml
from google.cloud import storage

# Django setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")

import django

try:
    django.setup()
except Exception as e:
    pass


class _PairedValues:
    """Marker wrapper for paired _start/_w values in constrained permutations.

    When the permutation engine encounters a ``_PairedValues`` instance in a
    combination tuple it knows to unpack ``.start`` and ``.w`` into two
    consecutive positions (matching the original ``_start`` / ``_w`` field
    order).  This avoids collisions with regular 2-tuples such as
    ``(climate, moisture)``.
    """
    __slots__ = ("start", "w")

    def __init__(self, start: Any, w: Any) -> None:
        self.start = start
        self.w = w

    def __repr__(self) -> str:  # pragma: no cover – debugging aid
        return f"_PairedValues({self.start!r}, {self.w!r})"


def extract_relevant_traceback(traceback_str: str, max_lines: int = 10) -> str:
    """
    Extract only the most relevant lines from a stack trace to avoid huge CSV files.

    Args:
        traceback_str: Full stack trace string
        max_lines: Maximum number of lines to include (default: 10)

    Returns:
        Condensed stack trace with only the most relevant lines
    """
    if not traceback_str:
        return ""

    lines = traceback_str.strip().split("\n")

    # Keep the exception type and message (first few lines)
    relevant_lines = []

    # Add exception info (usually first 2-3 lines)
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith("  File "):
            relevant_lines.append(line)
            if len(relevant_lines) >= 3:  # Keep exception type, message, and maybe one more
                break

    # Add the most recent stack frames (last few lines before the exception)
    stack_lines = [line for line in lines if line.startswith("  File ")]
    if stack_lines:
        # Take the last few stack frames (most recent)
        relevant_stack = stack_lines[-max_lines:]
        relevant_lines.extend(relevant_stack)

    return "\n".join(relevant_lines)


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
    is_single_field: bool = False  # If True, field doesn't have start/w/wo variations

    def get_field_names(self) -> Dict[str, str]:
        """Get all field name variations"""
        if self.is_single_field:
            return {"field": self.field_name}
        else:
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

    # Single field convenience methods
    @staticmethod
    def single_foreign_key(field_name: str, **kwargs) -> FieldMapping:
        """Create a single foreign key field mapping"""
        return FieldMapping(field_name, FieldType.FOREIGN_KEY, is_single_field=True, **kwargs)

    @staticmethod
    def single_boolean(field_name: str, **kwargs) -> FieldMapping:
        """Create a single boolean field mapping"""
        return FieldMapping(field_name, FieldType.BOOLEAN, is_single_field=True, **kwargs)

    @staticmethod
    def single_numeric(field_name: str, **kwargs) -> FieldMapping:
        """Create a single numeric field mapping"""
        return FieldMapping(field_name, FieldType.NUMERIC, is_single_field=True, **kwargs)

    @staticmethod
    def single_string(field_name: str, **kwargs) -> FieldMapping:
        """Create a single string field mapping"""
        return FieldMapping(field_name, FieldType.STRING, is_single_field=True, **kwargs)


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
        if field_mapping.is_single_field:
            value = getattr(module, field_names["field"], None)
            data[field_names["field"]] = value
        else:
            start_value = getattr(module, field_names["start"], None)
            with_value = getattr(module, field_names["with"], None)

            data[field_names["start"]] = start_value
            data[field_names["with"]] = with_value
            data[field_names["without"]] = start_value

    def _process_boolean_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process boolean fields"""
        if field_mapping.is_single_field:
            value = getattr(module, field_names["field"], None)
            data[field_names["field"]] = value
        else:
            start_value = getattr(module, field_names["start"], None)
            with_value = getattr(module, field_names["with"], None)

            data[field_names["start"]] = start_value
            data[field_names["with"]] = with_value
            data[field_names["without"]] = start_value

    def _process_numeric_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process numeric fields"""
        if field_mapping.is_single_field:
            value = getattr(module, field_names["field"], None)
            data[field_names["field"]] = value
        else:
            start_value = getattr(module, field_names["start"], None)
            with_value = getattr(module, field_names["with"], None)

            data[field_names["start"]] = start_value
            data[field_names["with"]] = with_value
            data[field_names["without"]] = start_value

    def _process_foreign_key_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process foreign key fields (extract .name)"""
        if field_mapping.is_single_field:
            value = getattr(module, field_names["field"], None)
            data[field_names["field"]] = value.name if value else None
        else:
            start_value = getattr(module, field_names["start"], None)
            with_value = getattr(module, field_names["with"], None)

            data[field_names["start"]] = start_value.name if start_value else None
            data[field_names["with"]] = with_value.name if with_value else None
            data[field_names["without"]] = start_value.name if start_value else None

    def _process_many_to_many_field(self, module: Any, data: Dict[str, Any], field_mapping: FieldMapping, field_names: Dict[str, str]):
        """Process many-to-many fields"""
        if field_mapping.is_single_field:
            value = getattr(module, field_names["field"], None)
            data[field_names["field"]] = [item.name for item in value.all()] if value else []
        else:
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
            FieldMappingBuilder.single_foreign_key("livestock_category_type"),
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
            # Core forest fields (single fields)
            FieldMappingBuilder.single_foreign_key("forest_type"),
            FieldMappingBuilder.single_foreign_key("forest_condition_type"),
            # Degradation fields
            FieldMappingBuilder.numeric("average_yearly_degradation_percentage"),
        ]

    def get_custom_fields(self, module: Any) -> Dict[str, Any]:
        """Get custom fields that don't follow the standard pattern"""
        return {
            "area": getattr(module, "area", None),
        }


class SmallFisheryDataBuilder(ModuleDataBuilder):
    """Data builder for Small Fishery modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.single_foreign_key("fishery_type"),
            FieldMappingBuilder.foreign_key("gear_type"),
        ]


class LargeFisheryDataBuilder(ModuleDataBuilder):
    """Data builder for Large Fishery modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.single_foreign_key("fish_type"),
            FieldMappingBuilder.foreign_key("gear_type"),
        ]


class CoastalWetlandDataBuilder(ModuleDataBuilder):
    """Data builder for Coastal Wetland modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.single_foreign_key("land_use_type"),
            FieldMappingBuilder.numeric("area_under_drainage"),
            FieldMappingBuilder.numeric("drained_area_excavated"),
            FieldMappingBuilder.numeric("area_not_drained_or_rewetted"),
            FieldMappingBuilder.numeric("area_w_restored_vegetation"),
        ]


class WaterbodyDataBuilder(ModuleDataBuilder):
    """Data builder for Waterbody modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.single_foreign_key("waterbody_type"),
            FieldMappingBuilder.foreign_key("trophic_type"),
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


class EnergyDataBuilder(ModuleDataBuilder):
    """Data builder for Energy modules (extracted from the single EnergyEntry)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("fuel_type"),
            FieldMappingBuilder.numeric("quantity_consumed_per_year"),
            FieldMappingBuilder.boolean("account_for_co2", is_single_field=True),
        ]


class StorageDataBuilder(ModuleDataBuilder):
    """Data builder for Storage modules (extracted from StorageEntry)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("fuel_type"),
            FieldMappingBuilder.numeric("quantity_consumed_per_year"),
            FieldMappingBuilder.boolean("is_refrigerant_used", is_single_field=True),
            FieldMappingBuilder.foreign_key("refrigerant_type"),
        ]


class ProcessingDataBuilder(ModuleDataBuilder):
    """Data builder for Processing modules (extracted from ProcessingEntry)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("fuel_type"),
            FieldMappingBuilder.numeric("quantity_consumed_per_year"),
            FieldMappingBuilder.boolean("is_water_used", is_single_field=True),
        ]


class PackagingDataBuilder(ModuleDataBuilder):
    """Data builder for Packaging modules (extracted from PackagingEntry)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("packaging_material_type"),
            FieldMappingBuilder.numeric("kg_of_packaging_material"),
            FieldMappingBuilder.boolean("is_electric", is_single_field=True),
        ]


class TransportDataBuilder(ModuleDataBuilder):
    """Data builder for Transport modules (extracted from TransportEntry)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("fuel_type"),
            FieldMappingBuilder.numeric("quantity_consumed_per_year"),
        ]


class IrrigationSystemDataBuilder(ModuleDataBuilder):
    """Data builder for IrrigationSystem submodules (under Irrigation parent)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("irrigation_system_type", is_single_field=True),
            FieldMappingBuilder.numeric("ha"),
            FieldMappingBuilder.numeric("ef_t2"),
        ]


class IrrigationPhaseDataBuilder(ModuleDataBuilder):
    """Data builder for IrrigationPhase submodules (under Irrigation parent)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("irrigation_system_type", is_single_field=True),
            FieldMappingBuilder.foreign_key("fuel_type"),
            FieldMappingBuilder.numeric("ha"),
            FieldMappingBuilder.numeric("gross_irrigation_water"),
        ]


class SettlementDataBuilder(ModuleDataBuilder):
    """Data builder for Settlement land modules."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("settlement_type"),
            FieldMappingBuilder.numeric("biomass_t2"),
        ]


class BuildingDataBuilder(ModuleDataBuilder):
    """Data builder for Building submodules (under Settlement parent)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.single_foreign_key("building_type"),
            FieldMappingBuilder.numeric("area_m2"),
            FieldMappingBuilder.numeric("ef_t2"),
        ]


class RoadDataBuilder(ModuleDataBuilder):
    """Data builder for Road submodules (under Settlement parent)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.single_foreign_key("road_type"),
            FieldMappingBuilder.numeric("length_km"),
            FieldMappingBuilder.numeric("width_m"),
        ]


class OtherInfrastructureDataBuilder(ModuleDataBuilder):
    """Data builder for OtherInfrastructure submodules (under Settlement parent)."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.numeric("area_m2"),
            FieldMappingBuilder.numeric("ef_t2"),
        ]


class LandUseChangeDataBuilder(ModuleDataBuilder):
    """Data builder for LandUseChange modules."""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("module_type"),
            FieldMappingBuilder.boolean("is_fire_used"),
        ]


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
        self.register("ForestManagement", ForestManagementDataBuilder())
        self.register("SmallFishery", SmallFisheryDataBuilder())
        self.register("LargeFishery", LargeFisheryDataBuilder())
        self.register("CoastalWetland", CoastalWetlandDataBuilder())
        self.register("CoastalWetland2", CoastalWetlandDataBuilder())
        self.register("Waterbody", WaterbodyDataBuilder())
        self.register("Energy", EnergyDataBuilder())
        self.register("Storage", StorageDataBuilder())
        self.register("Processing", ProcessingDataBuilder())
        self.register("Packaging", PackagingDataBuilder())
        self.register("Transport", TransportDataBuilder())
        self.register("IrrigationSystem", IrrigationSystemDataBuilder())
        self.register("IrrigationPhase", IrrigationPhaseDataBuilder())
        self.register("Settlement", SettlementDataBuilder())
        self.register("Building", BuildingDataBuilder())
        self.register("Road", RoadDataBuilder())
        self.register("OtherInfrastructure", OtherInfrastructureDataBuilder())
        self.register("LandUseChange", LandUseChangeDataBuilder())

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

    # Optional override: when the catalog/MODULE_CONFIGS key differs from
    # the Django class of the module returned by `create_module` (e.g.
    # `EnergyProcessor` returns an EnergyEntry submodule but data must be
    # written under the "Energy" key), set this to the catalog key. The
    # default of None falls back to `module.__class__.__name__`.
    data_builder_key: Optional[str] = None

    def __init__(self, data_builder_registry: ModuleDataBuilderRegistry):
        self.data_builder_registry = data_builder_registry

    def create_project(self, climate: Any, moisture: Any, soil_type: Any, region: Any, factories: Any) -> Any:
        """Helper method to create a project with proper country selection"""
        # Get a random country from the region, with fallback
        country = region.countries.filter(ipcc_region__isnull=False).order_by("?").first()
        if not country:
            # Skip this combination if no country is available
            raise ValueError(f"No countries found for region: {region}")

        return factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=country,
        )

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

            # Build data — when ``data_builder_key`` is set, use it
            # instead of the module's class name so parent-with-submodule
            # processors can return the submodule (for calculator dispatch)
            # but still emit ChangeRecord rows under the parent's key.
            if self.data_builder_key is not None:
                builder = self.data_builder_registry.get_builder(self.data_builder_key)
                data = builder.build_data(module)
            else:
                data = self.data_builder_registry.build_data(module)
            data["total"] = balance

            return ProcessingResult.success_result(data)

        except Exception as e:
            full_traceback = traceback.format_exc()
            condensed_traceback = extract_relevant_traceback(full_traceback)

            # Log specific errors for debugging
            if "No countries found for region" in str(e):
                # This is expected for some regions, so don't log as error
                return ProcessingResult.error_result(type(e).__name__, str(e), combination, condensed_traceback)
            elif "Project has no country" in str(e):
                # This is also expected for some combinations
                return ProcessingResult.error_result(type(e).__name__, str(e), combination, condensed_traceback)
            else:
                # Log unexpected errors
                logger.warning(f"Unexpected error in combination processing: {type(e).__name__}: {str(e)}")
                return ProcessingResult.error_result(type(e).__name__, str(e), combination, condensed_traceback)


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
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
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
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
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
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
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
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        # FloodedRiceFactory does not default land_use_type, and the
        # catalog doesn't permute it (it's fixed to "Flooded Rice"). Set
        # it explicitly so FloodedRiceCalculator.get_biomass_ef finds it
        # instead of raising "Missing land use type for start scenario".
        flooded_rice_lut = models.LandUseType.objects.get(name="Flooded Rice")
        module = factories.FloodedRiceFactory.build(
            activity=a,
            area=1,
            land_use_type_start=flooded_rice_lut,
            land_use_type_w=flooded_rice_lut,
            land_use_type_wo=flooded_rice_lut,
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
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
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
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
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


class SmallFisheryProcessor(ModuleProcessor):
    """Processor for Small Fishery modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            gear_type_start,
            gear_type_w,
            fishery_type,
            total_catch_yr_start,
            total_catch_yr_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.SmallFisheryFactory.build(
            activity=a,
            fishery_type=fishery_type,
            gear_type_start=gear_type_start,
            gear_type_w=gear_type_w,
            gear_type_wo=gear_type_start,
            total_catch_yr_start=total_catch_yr_start,
            total_catch_yr_w=total_catch_yr_w,
            total_catch_yr_wo=total_catch_yr_start,
        )
        return module


class LargeFisheryProcessor(ModuleProcessor):
    """Processor for Large Fishery modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            gear_type_start,
            gear_type_w,
            fish_type,
            total_catch_yr_start,
            total_catch_yr_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.LargeFisheryFactory.build(
            activity=a,
            fish_type=fish_type,
            gear_type_start=gear_type_start,
            gear_type_w=gear_type_w,
            gear_type_wo=gear_type_start,
            total_catch_yr_start=total_catch_yr_start,
            total_catch_yr_w=total_catch_yr_w,
            total_catch_yr_wo=total_catch_yr_start,
        )
        return module


class CoastalWetlandProcessor(ModuleProcessor):
    """Processor for CoastalWetland modules.

    The calculator only reads direct fields and FKs (no reverse relations),
    so an unsaved instance is fine. Registered for both ``CoastalWetland``
    and ``CoastalWetland2`` MODULE_CONFIGS keys — the two configs vary
    different field subsets (drained vs. rewetted) against the same model.
    """

    data_builder_key = "CoastalWetland"

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            land_use_type,
            area_under_drainage_start,
            area_under_drainage_w,
            drained_area_excavated_start,
            drained_area_excavated_w,
            area_not_drained_or_rewetted_start,
            area_not_drained_or_rewetted_w,
            area_w_restored_vegetation_start,
            area_w_restored_vegetation_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.CoastalWetlandFactory.build(
            activity=a,
            area=1,
            land_use_type=land_use_type,
            area_under_drainage_start=area_under_drainage_start,
            area_under_drainage_w=area_under_drainage_w,
            area_under_drainage_wo=area_under_drainage_start,
            drained_area_excavated_start=drained_area_excavated_start,
            drained_area_excavated_w=drained_area_excavated_w,
            drained_area_excavated_wo=drained_area_excavated_start,
            area_not_drained_or_rewetted_start=area_not_drained_or_rewetted_start,
            area_not_drained_or_rewetted_w=area_not_drained_or_rewetted_w,
            area_not_drained_or_rewetted_wo=area_not_drained_or_rewetted_start,
            area_w_restored_vegetation_start=area_w_restored_vegetation_start,
            area_w_restored_vegetation_w=area_w_restored_vegetation_w,
            area_w_restored_vegetation_wo=area_w_restored_vegetation_start,
        )
        return module


class WaterbodyProcessor(ModuleProcessor):
    """Processor for Waterbody modules.

    Calculator reads direct fields only — unsaved instance is safe.
    """

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            waterbody_type,
            trophic_type_start,
            trophic_type_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture

        p = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=region.countries.filter(ipcc_region__isnull=False).order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.WaterbodyFactory.build(
            activity=a,
            area=1,
            waterbody_type=waterbody_type,
            trophic_type_start=trophic_type_start,
            trophic_type_w=trophic_type_w,
            trophic_type_wo=trophic_type_start,
        )
        return module


# ---------------------------------------------------------------------------
# Processors for modules with a parent + submodule shape
#
# The existing land/livestock processors use ``factories.X.build()`` and rely
# on the calculator operating on a single self-contained module. Energy /
# Irrigation / Storage / Processing / Packaging / Transport / Settlement
# all rely on submodules attached to a parent via a reverse-FK relation —
# parent calculators that iterate ``parent.entries.all()`` only work when
# the parent is persisted. To avoid DB writes during permutation, we
# **build the parent unsaved**, build one submodule pointing at it, and
# pass the *submodule* to ``CalculatorFactory`` so the submodule-level
# calculator runs directly. ``data_builder_key`` then routes data emission
# back to the catalog name (e.g. "Energy") so ChangeRecord rows align with
# the UI selector.
# ---------------------------------------------------------------------------


def _build_project_activity(combination, factories):
    """Pull climate/moisture/soil_type/region off the tail of a combination
    and build an unsaved Project + Activity pair shared by every new
    processor below. The tail order matches what compute_permutations
    appends in ``fields.update({"climate_moistures": ..., "soil_types": ...,
    "region": ...})``.
    """
    climate_moisture, soil_type, region = combination[-3:]
    climate, moisture = climate_moisture
    # Filter to countries with ipcc_region populated — LivestockCalculator's
    # LivestockTAM lookup uses country.ipcc_region as a filter key, and
    # picking a country with ipcc_region=None drove Test Run #4's
    # "Could not find TAM (START) for ..., None" cascade. The companion
    # filter at PermutationComputer-region level removes regions that have
    # zero such countries, so this pick should always succeed.
    country = region.countries.filter(ipcc_region__isnull=False).order_by("?").first()
    project = factories.ProjectFactory.build(
        climate=climate,
        moisture=moisture,
        soil_type=soil_type,
        country=country,
    )
    activity = factories.ActivityFactory.build(project=project)
    return project, activity


def _apply_unsaved_defaults(instance, models):
    """Set FK defaults that the model's ``save()`` would normally populate.

    ``ElectricityTier2Mixin.save()`` sets ``ef_source`` to
    EmissionFactorSource(OPERATING_MARGIN). The permutation runner uses
    ``Factory.build()`` (unsaved) to avoid DB writes per combination, so
    those defaults never fire — and calculators that read e.g.
    ``self.module.ef_source.name`` blow up with
    ``'NoneType' object has no attribute 'name'``.

    Status is set to READY (not the EMPTY default Submodule.save would
    use): BaseValueChainCalculator gates its EnergyEntryCalculator
    instantiation on ``self.module.is_ready()`` — when status is EMPTY
    the inner calculator stays None and later
    ``self.energy_calculator_w.get_defaults()`` / ``.calculate()`` raises
    'NoneType' object has no attribute. For the permutation runner the
    intent is always to run the math, so READY is the right default.
    """
    if hasattr(instance, "status") and not getattr(instance, "status", None):
        if not hasattr(_apply_unsaved_defaults, "_status_ready"):
            _apply_unsaved_defaults._status_ready = models.StatusType.objects.get_or_create(name_en="READY")[0]
        instance.status = _apply_unsaved_defaults._status_ready
    if hasattr(instance, "ef_source") and not getattr(instance, "ef_source", None):
        if not hasattr(_apply_unsaved_defaults, "_ef_source"):
            _apply_unsaved_defaults._ef_source = models.EmissionFactorSource.objects.get_or_create(
                name=models.EmissionFactorSource.OPERATING_MARGIN
            )[0]
        instance.ef_source = _apply_unsaved_defaults._ef_source

    # Tier-2 override floats default to None on the mixins ("no override,
    # use IPCC default"). When the IPCC default is also missing — e.g.
    # ``EnergyDefaultEmissionFactor.co2 is None`` for a renewable fuel —
    # the calculator falls back to the tier-2 value and the math throws
    # ``unsupported operand type(s) for *: 'float' and 'NoneType'``.
    # Replacing None with 0 keeps "no override" semantics (factor_t2 is
    # only used via ``factor or default`` / ``factor if factor is not
    # None`` patterns) while keeping the math arithmetic-safe.
    from django.db.models import FloatField as _FloatField
    for _field in instance._meta.get_fields():
        if not isinstance(_field, _FloatField):
            continue
        _name = _field.attname
        if "_t2" not in _name:
            continue
        if getattr(instance, _name, None) is None:
            setattr(instance, _name, 0)

    return instance


class EnergyProcessor(ModuleProcessor):
    """Build Energy parent + a single EnergyEntry submodule.

    The catalog/MODULE_CONFIGS key is ``"Energy"`` so ChangeRecord rows
    land under that module_type, but the submodule's own calculator is
    what actually runs (avoids the parent-bound ``entries.all()`` query).
    """

    data_builder_key = "Energy"

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            fuel_type_start, fuel_type_w,
            account_for_co2_start, account_for_co2_w,
            quantity_consumed_per_year_start, quantity_consumed_per_year_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.EnergyFactory.build(activity=activity)
        entry = models.EnergyEntry(
            parent=parent,
            fuel_type_start=fuel_type_start,
            fuel_type_w=fuel_type_w,
            fuel_type_wo=fuel_type_start,
            quantity_consumed_per_year_start=quantity_consumed_per_year_start,
            quantity_consumed_per_year_w=quantity_consumed_per_year_w,
            quantity_consumed_per_year_wo=quantity_consumed_per_year_start,
            account_for_co2=account_for_co2_start,
        )
        return _apply_unsaved_defaults(entry, models)


class StorageProcessor(ModuleProcessor):
    """Build Storage parent + a single StorageEntry submodule."""

    data_builder_key = "Storage"

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            fuel_type_start, fuel_type_w,
            quantity_consumed_per_year_start, quantity_consumed_per_year_w,
            is_refrigerant_used_start, is_refrigerant_used_w,
            refrigerant_type_start, refrigerant_type_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.StorageFactory.build(activity=activity)
        # Use the factory so total_refrigerant_leakage_* and
        # emission_factor_t2_* land on the instance — StorageEntryCalculator
        # feeds them straight into MathValueChain, and bare model
        # construction left them None, triggering "unsupported operand
        # type(s) for *: 'NoneType' and 'float'" in the math.
        entry = factories.StorageEntryFactory.build(
            parent=parent,
            fuel_type_start=fuel_type_start,
            fuel_type_w=fuel_type_w,
            fuel_type_wo=fuel_type_start,
            quantity_consumed_per_year_start=quantity_consumed_per_year_start,
            quantity_consumed_per_year_w=quantity_consumed_per_year_w,
            quantity_consumed_per_year_wo=quantity_consumed_per_year_start,
            is_refrigerant_used=is_refrigerant_used_start,
            refrigerant_type_start=refrigerant_type_start,
            refrigerant_type_w=refrigerant_type_w,
            refrigerant_type_wo=refrigerant_type_start,
        )
        return _apply_unsaved_defaults(entry, models)


class ProcessingProcessor(ModuleProcessor):
    """Build Processing parent + a single ProcessingEntry submodule."""

    data_builder_key = "Processing"

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            fuel_type_start, fuel_type_w,
            quantity_consumed_per_year_start, quantity_consumed_per_year_w,
            is_water_used_start, is_water_used_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.ProcessingFactory.build(activity=activity)
        # Use the factory so water_use_per_year_* and any future
        # ProcessingEntry-specific defaults land on the instance —
        # bare models.ProcessingEntry(...) leaves them None and the math
        # falls over with "float * NoneType".
        entry = factories.ProcessingEntryFactory.build(
            parent=parent,
            fuel_type_start=fuel_type_start,
            fuel_type_w=fuel_type_w,
            fuel_type_wo=fuel_type_start,
            quantity_consumed_per_year_start=quantity_consumed_per_year_start,
            quantity_consumed_per_year_w=quantity_consumed_per_year_w,
            quantity_consumed_per_year_wo=quantity_consumed_per_year_start,
            is_water_used=is_water_used_start,
        )
        return _apply_unsaved_defaults(entry, models)


class PackagingProcessor(ModuleProcessor):
    """Build Packaging parent + a single PackagingEntry submodule."""

    data_builder_key = "Packaging"

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            packaging_material_type_start, packaging_material_type_w,
            kg_of_packaging_material_start, kg_of_packaging_material_w,
            is_electric_start, is_electric_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.PackagingFactory.build(activity=activity)
        # Use the factory so quantity_consumed_per_year_* land on the
        # PackagingEntry — when is_electric=True the calculator spawns an
        # EnergyEntryCalculator that multiplies mwh_* (which reads from
        # quantity_consumed_per_year_*); leaving it None crashes the math
        # with "float * NoneType".
        entry = factories.PackagingEntryFactory.build(
            parent=parent,
            packaging_material_type_start=packaging_material_type_start,
            packaging_material_type_w=packaging_material_type_w,
            packaging_material_type_wo=packaging_material_type_start,
            kg_of_packaging_material_start=kg_of_packaging_material_start,
            kg_of_packaging_material_w=kg_of_packaging_material_w,
            kg_of_packaging_material_wo=kg_of_packaging_material_start,
            is_electric=is_electric_start,
        )
        return _apply_unsaved_defaults(entry, models)


class TransportProcessor(ModuleProcessor):
    """Build Transport parent + a single TransportEntry submodule."""

    data_builder_key = "Transport"

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            fuel_type_start, fuel_type_w,
            quantity_consumed_per_year_start, quantity_consumed_per_year_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.TransportFactory.build(activity=activity)
        # Same pattern as Storage/Processing/Packaging — use the factory so
        # any TransportEntry-specific defaults land on the instance.
        entry = factories.TransportEntryFactory.build(
            parent=parent,
            fuel_type_start=fuel_type_start,
            fuel_type_w=fuel_type_w,
            fuel_type_wo=fuel_type_start,
            quantity_consumed_per_year_start=quantity_consumed_per_year_start,
            quantity_consumed_per_year_w=quantity_consumed_per_year_w,
            quantity_consumed_per_year_wo=quantity_consumed_per_year_start,
        )
        return _apply_unsaved_defaults(entry, models)


class IrrigationSystemProcessor(ModuleProcessor):
    """Build Irrigation parent + a single IrrigationSystem submodule.

    Catalog key matches the submodule class name, so
    ``CalculatorFactory`` dispatches to ``IrrigationSystemCalculator`` and
    the default data builder lookup ("IrrigationSystem") works without
    needing ``data_builder_key``.
    """

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            irrigation_system_type_start, irrigation_system_type_w,
            ha_start, ha_w,
            ef_t2_start, ef_t2_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.IrrigationFactory.build(activity=activity)
        system = models.IrrigationSystem(
            parent=parent,
            irrigation_system_type=irrigation_system_type_start,
            ha_start=ha_start,
            ha_w=ha_w,
            ha_wo=ha_start,
            ef_t2_start=ef_t2_start,
            ef_t2_w=ef_t2_w,
            ef_t2_wo=ef_t2_start,
        )
        return _apply_unsaved_defaults(system, models)


class IrrigationPhaseProcessor(ModuleProcessor):
    """Build Irrigation parent + a single IrrigationPhase submodule."""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            irrigation_system_type_start, irrigation_system_type_w,
            fuel_type_start, fuel_type_w,
            ha_start, ha_w,
            gross_irrigation_water_start, gross_irrigation_water_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.IrrigationFactory.build(activity=activity)
        # Use the factory rather than the bare model constructor so all the
        # Tier-2 defaults (ef_co2_t2, ef_ch4_t2, ef_n2o_t2, average_pressure_t2,
        # total_dynamic_head_t2, pumping_efficiency_t2, well_depth) land on
        # the instance. The IrrigationPhaseCalculator hard-arithmetics those
        # values (e.g. `None + 0.1` from transmission_loss math), so leaving
        # them None blows up with "unsupported operand type(s) for +".
        phase = factories.IrrigationPhaseFactory.build(
            parent=parent,
            irrigation_system_type=irrigation_system_type_start,
            fuel_type_start=fuel_type_start,
            fuel_type_w=fuel_type_w,
            fuel_type_wo=fuel_type_start,
            ha_start=ha_start,
            ha_w=ha_w,
            ha_wo=ha_start,
            gross_irrigation_water_start=gross_irrigation_water_start,
            gross_irrigation_water_w=gross_irrigation_water_w,
            gross_irrigation_water_wo=gross_irrigation_water_start,
        )
        return _apply_unsaved_defaults(phase, models)


class SettlementProcessor(ModuleProcessor):
    """Build a Settlement land module (no submodules attached).

    Settlement is a LandModule whose calculator only loops over
    ``buildings``/``roads`` when those submodules exist — leaving the
    relation empty lets the parent's own carbon-stock math run unchanged.
    """

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            land_use_type_start,
            settlement_type_start, settlement_type_w,
            biomass_t2_start, biomass_t2_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        settlement = factories.SettlementFactory.build(
            activity=activity,
            land_use_type_start=land_use_type_start,
            land_use_type_w=land_use_type_start,
            land_use_type_wo=land_use_type_start,
            settlement_type_start=settlement_type_start,
            settlement_type_w=settlement_type_w,
            settlement_type_wo=settlement_type_start,
            biomass_t2_start=biomass_t2_start,
            biomass_t2_w=biomass_t2_w,
            biomass_t2_wo=biomass_t2_start,
        )
        return _apply_unsaved_defaults(settlement, models)


class BuildingProcessor(ModuleProcessor):
    """Build Settlement parent + a single Building submodule."""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            building_type_start, building_type_w,
            area_m2_start, area_m2_w,
            ef_t2_start, ef_t2_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.SettlementFactory.build(activity=activity)
        building = models.Building(
            parent=parent,
            building_type=building_type_start,
            area_m2_start=area_m2_start,
            area_m2_w=area_m2_w,
            area_m2_wo=area_m2_start,
            ef_t2_start=ef_t2_start,
            ef_t2_w=ef_t2_w,
            ef_t2_wo=ef_t2_start,
        )
        return _apply_unsaved_defaults(building, models)


class RoadProcessor(ModuleProcessor):
    """Build Settlement parent + a single Road submodule."""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            road_type_start, road_type_w,
            length_km_start, length_km_w,
            width_m_start, width_m_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.SettlementFactory.build(activity=activity)
        road = models.Road(
            parent=parent,
            road_type=road_type_start,
            length_km_start=length_km_start,
            length_km_w=length_km_w,
            length_km_wo=length_km_start,
            width_m_start=width_m_start,
            width_m_w=width_m_w,
            width_m_wo=width_m_start,
        )
        return _apply_unsaved_defaults(road, models)


class OtherInfrastructureProcessor(ModuleProcessor):
    """Build Settlement parent + a single OtherInfrastructure submodule."""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            area_m2_start, area_m2_w,
            ef_t2_start, ef_t2_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        parent = factories.SettlementFactory.build(activity=activity)
        other = models.OtherInfrastructure(
            parent=parent,
            area_m2_start=area_m2_start,
            area_m2_w=area_m2_w,
            area_m2_wo=area_m2_start,
            ef_t2_start=ef_t2_start,
            ef_t2_w=ef_t2_w,
            ef_t2_wo=ef_t2_start,
        )
        return _apply_unsaved_defaults(other, models)


class LandUseChangeProcessor(ModuleProcessor):
    """Build a minimal LandUseChange.

    LUC depends on three sibling land modules (start / with / without)
    keyed off Activity. A full LUC permutation pipeline would require
    auto-generating those siblings plus their own attributes — out of
    scope here. The processor builds just the LUC instance itself; the
    `LandUseChangeCalculator` will raise without the siblings, so this
    processor is intentionally only useful once paired with the same
    Activity-built sibling fixtures (tracked as a follow-up).
    """

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            module_type_start, module_type_w,
            is_fire_used_start, is_fire_used_w,
            climate_moisture, soil_type, region,
        ) = combination

        project, activity = _build_project_activity(combination, factories)
        luc = factories.LandUseChangeFactory.build(
            activity=activity,
            module_type_start=module_type_start,
            module_type_w=module_type_w,
            module_type_wo=module_type_start,
            is_fire_used_start=is_fire_used_start,
            is_fire_used_w=is_fire_used_w,
            is_fire_used_wo=is_fire_used_start,
            area=1,
        )
        return luc


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
        self.register("SmallFishery", SmallFisheryProcessor(self._data_builder_registry))
        self.register("LargeFishery", LargeFisheryProcessor(self._data_builder_registry))
        # CoastalWetland2 reuses the same processor — the two MODULE_CONFIGS
        # entries vary different field subsets (drained vs. rewetted) against
        # one model class with one calculator.
        self.register("CoastalWetland", CoastalWetlandProcessor(self._data_builder_registry))
        self.register("CoastalWetland2", CoastalWetlandProcessor(self._data_builder_registry))
        self.register("Waterbody", WaterbodyProcessor(self._data_builder_registry))
        self.register("Energy", EnergyProcessor(self._data_builder_registry))
        self.register("Storage", StorageProcessor(self._data_builder_registry))
        self.register("Processing", ProcessingProcessor(self._data_builder_registry))
        self.register("Packaging", PackagingProcessor(self._data_builder_registry))
        self.register("Transport", TransportProcessor(self._data_builder_registry))
        self.register("IrrigationSystem", IrrigationSystemProcessor(self._data_builder_registry))
        self.register("IrrigationPhase", IrrigationPhaseProcessor(self._data_builder_registry))
        self.register("Settlement", SettlementProcessor(self._data_builder_registry))
        self.register("Building", BuildingProcessor(self._data_builder_registry))
        self.register("Road", RoadProcessor(self._data_builder_registry))
        self.register("OtherInfrastructure", OtherInfrastructureProcessor(self._data_builder_registry))
        self.register("LandUseChange", LandUseChangeProcessor(self._data_builder_registry))

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
                # SoilOrganicCarbon.value is nullable — a record can exist
                # with value=None and still trip the calculator's
                # ``if self.soc_start.value is None`` check. Require value
                # to be set so this matches what the calculator treats as
                # a valid SOC reference.
                if ipcc_models.SoilOrganicCarbon.objects.filter(
                    climate=climate, moisture=moisture,
                    soil_type=soil_type, value__isnull=False,
                ).exists():
                    valid_combinations.append((climate, moisture, soil_type))

        logger.info(f"Found {len(valid_combinations)} valid climate-moisture-soiltype combinations out of {total_combinations} total combinations")
        return valid_combinations


class ConfigurationLoader:
    """Loads configuration from GCP storage bucket or local fallback"""

    def __init__(self, bucket_name: str = None):
        self.bucket_name = bucket_name or os.getenv("STORAGE_BUCKET")
        self._storage_client = None
        self._bucket = None

    @property
    def storage_client(self):
        """Lazy initialization of storage client"""
        if self._storage_client is None:
            self._storage_client = storage.Client()
        return self._storage_client

    @property
    def bucket(self):
        """Lazy initialization of bucket"""
        if self._bucket is None:
            self._bucket = self.storage_client.bucket(self.bucket_name)
        return self._bucket

    def load_config(self, config_name: str = "minitool_config.yml", local: bool = False) -> Dict[str, Any]:
        """Load configuration from GCP storage or local fallback"""
        config = None

        # Try to load from GCP storage first
        if self.bucket_name and not local:
            try:
                blob = self.bucket.blob(f"minitool/{config_name}")
                if blob.exists():
                    config_content = blob.download_as_text()
                    config = yaml.safe_load(config_content)
                    logger.info(f"Loaded configuration from gs://{self.bucket_name}/minitool/{config_name}")
                    return self._validate_and_merge_config(config)
                else:
                    logger.warning(f"Configuration file not found in bucket: gs://{self.bucket_name}/minitool/{config_name}")
            except Exception as e:
                logger.warning(f"Failed to load configuration from GCP storage: {e}")

        # Fallback to local file
        local_config_path = Path(__file__).parent.parent / config_name
        print(local_config_path)
        if local_config_path.exists():
            try:
                with open(local_config_path, "r") as f:
                    config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from local file: {local_config_path}")
                return self._validate_and_merge_config(config)
            except Exception as e:
                logger.error(f"Failed to load local configuration: {e}")

        # Return default configuration if no file found
        logger.warning("No configuration file found, using default configuration")
        return self._get_default_config()

    def _validate_and_merge_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and merge configuration with defaults"""
        default_config = self._get_default_config()

        # Merge modules configuration
        if "modules" in config:
            default_config["modules"].update(config["modules"])

        # Merge performance configuration
        if "performance" in config:
            default_config["performance"].update(config["performance"])

        return default_config

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "modules": {
                "annual_cropland": False,
                "flooded_rice": False,
                "grassland": False,
                "livestock": False,
                "perennial_cropland": False,
                "forest_management": False,
                "small_fishery": False,
                "large_fishery": False,
                "aquaculture": False,
                "coastal_wetland": False,
                "waterbody": False,
                "other_land": False,
                "set_aside": False,
                "energy": False,
                "storage": False,
                "processing": False,
                "packaging": False,
                "transport": False,
                "irrigation_system": False,
                "irrigation_phase": False,
                "settlement": False,
                "building": False,
                "road": False,
                "other_infrastructure": False,
                "land_use_change": False,
            },
            "performance": {
                "max_rows": 10000,
                "max_workers": None,
                "chunk_size": 10000,
            },
        }


class DataManager:
    """Manages data storage and retrieval"""

    def __init__(self, bucket_name: str = None):
        self.bucket_name = bucket_name or os.getenv("STORAGE_BUCKET")
        if not self.bucket_name:
            raise ValueError("STORAGE_BUCKET environment variable must be set or bucket_name must be provided")
        # Don't initialize storage client here to avoid pickling issues
        self._storage_client = None
        self._bucket = None

    @property
    def storage_client(self):
        """Lazy initialization of storage client to avoid pickling issues"""
        if self._storage_client is None:
            self._storage_client = storage.Client()
        return self._storage_client

    @property
    def bucket(self):
        """Lazy initialization of bucket to avoid pickling issues"""
        if self._bucket is None:
            self._bucket = self.storage_client.bucket(self.bucket_name)
        return self._bucket

    def save_data(self, data: List[Dict[str, Any]], errors: List[Dict[str, Any]], module_name: str) -> None:
        """Save data and errors to GCP storage bucket as CSV files"""
        try:
            if data:
                df = pd.DataFrame(data)
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)

                blob_name = f"minitool/{module_name.lower()}.csv"
                blob = self.bucket.blob(blob_name)
                blob.upload_from_string(csv_buffer.getvalue(), content_type="text/csv")
                logger.info(f"Saved {len(data)} rows to gs://{self.bucket_name}/{blob_name}")

            if errors:
                errors_df = pd.DataFrame(errors)
                errors_csv_buffer = io.StringIO()
                errors_df.to_csv(errors_csv_buffer, index=False)

                errors_blob_name = f"minitool/{module_name.lower()}_errors.csv"
                errors_blob = self.bucket.blob(errors_blob_name)
                errors_blob.upload_from_string(errors_csv_buffer.getvalue(), content_type="text/csv")
                logger.info(f"Saved {len(errors)} errors to gs://{self.bucket_name}/{errors_blob_name}")

        except Exception as e:
            logger.error(f"Failed to save data to GCP storage: {e}")
            # Fallback to local file storage if GCP storage fails
            self._save_to_local_fallback(data, errors, module_name)

    def _save_to_local_fallback(self, data: List[Dict[str, Any]], errors: List[Dict[str, Any]], module_name: str) -> None:
        """Fallback method to save data locally if GCP storage fails"""
        output_dir = Path("scripts/minitool")
        output_dir.mkdir(exist_ok=True)

        if data:
            df = pd.DataFrame(data)
            filepath = output_dir / f"{module_name.lower()}.csv"
            df.to_csv(filepath, index=False)
            logger.info(f"Fallback: Saved {len(data)} rows to {filepath}")

        if errors:
            errors_df = pd.DataFrame(errors)
            errors_filepath = output_dir / f"{module_name.lower()}_errors.csv"
            errors_df.to_csv(errors_filepath, index=False)
            logger.info(f"Fallback: Saved {len(errors)} errors to {errors_filepath}")


class PermutationComputer:
    """Handles permutation computation with multiprocessing"""

    def __init__(self, processor_registry: ProcessorRegistry):
        self.processor_registry = processor_registry

    def django_initializer(self):
        """Initialize Django in child processes"""
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
        logging.getLogger().setLevel(logging.CRITICAL)

        from django.apps import apps
        if not apps.ready:
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

    @staticmethod
    def _flatten_combo(combo: tuple) -> tuple:
        """Flatten a combination tuple, unpacking ``_PairedValues`` markers.

        Regular elements are kept as-is (including ``(climate, moisture)``
        2-tuples), while ``_PairedValues`` instances are expanded to their
        ``.start`` and ``.w`` components so the resulting flat tuple matches
        the positional order that each module processor expects.
        """
        flat: list = []
        for item in combo:
            if isinstance(item, _PairedValues):
                flat.append(item.start)
                flat.append(item.w)
            else:
                flat.append(item)
        return tuple(flat)

    @staticmethod
    def _build_combination_validator(module_type: str, fields_dict: dict):
        """Return ``validator(combination) -> bool`` that filters out
        permutations whose ``(land_use_type, climate, moisture, ...)`` tuple
        has no matching IPCC reference-data row, or ``None`` if the module
        has no per-permutation reference-data dependencies.

        This is the planner-side "skip bad pairings" filter the user asked
        for: it sits between the cartesian product and the worker pool, so
        permutations that would deterministically raise "X does not exist"
        / "is missing" inside the calculator never reach a worker — the
        ``max_rows`` cap then applies to *processable* combinations.

        The flat ``fields_dict`` keys are turned into positional indices to
        match what ``_flatten_combo`` yields (paired ``_start``/``_w`` are
        already split back into two positions at this point).
        """
        flat_keys: list[str] = []
        for key in fields_dict.keys():
            flat_keys.append(key)

        def _idx(name: str) -> Optional[int]:
            return flat_keys.index(name) if name in flat_keys else None

        cm_idx = _idx("climate_moistures")
        region_idx = _idx("region")
        soil_idx = _idx("soil_types")
        if cm_idx is None or region_idx is None:
            return None

        # Land modules go through LandModuleCalculator.get_defaults which
        # looks up SoilOrganicCarbon.objects.filter(climate, moisture,
        # soil_type).first() and then raises "SOC for X climate, Y
        # moisture, and Z soil type is missing" when ``.value is None`` —
        # the model's value field is nullable, so a row can exist but
        # still trip the calculator's None check. Pre-load only the
        # triples whose row has a non-null value, which mirrors what the
        # calculator actually treats as a valid SOC reference.
        _soc_set = frozenset(
            ipcc_models.SoilOrganicCarbon.objects.filter(
                value__isnull=False,
            ).values_list(
                "climate_id", "moisture_id", "soil_type_id",
            )
        )

        def _soc_ok(combo) -> bool:
            if soil_idx is None or not _soc_set:
                return True
            climate, moisture = combo[cm_idx]
            soil_type = combo[soil_idx]
            if soil_type is None:
                return True
            return (climate.id, moisture.id, soil_type.id) in _soc_set

        if module_type == "PerennialCropland":
            # PerennialAGB rows are keyed by
            # (land_use_type, climate, moisture, continent). LUTs without a
            # matching row for the picked (climate, moisture, region) raise
            # "PerennialAGB for X in Y climate does not exist for start
            # scenario" inside the calculator.
            valid_set = frozenset(
                ipcc_models.PerennialAGB.objects.values_list(
                    "land_use_type_id", "climate_id", "moisture_id", "continent_id",
                )
            )
            if not valid_set:
                return None
            lut_indices = [
                _idx(k) for k in (
                    "land_use_type_start", "land_use_type_w", "land_use_type_wo", "land_use_type",
                ) if _idx(k) is not None
            ]
            if not lut_indices:
                return None

            def validator(combo):
                if not _soc_ok(combo):
                    return False
                climate, moisture = combo[cm_idx]
                region = combo[region_idx]
                if region is None:
                    return True
                for li in lut_indices:
                    lut = combo[li]
                    if lut is None:
                        continue
                    if (lut.id, climate.id, moisture.id, region.id) not in valid_set:
                        return False
                return True
            return validator

        if module_type in ("CoastalWetland", "CoastalWetland2"):
            # CoastalWetlandCalculator chains lookups through CoastalAGB,
            # CoastalLitter, CoastalDeadwood, DefaultSoilCarbonStock,
            # DrainageEmissionFactor and RewettingCarbonFactor (the latter
            # was the source of Test Run #4's "Rewetting CO2 ... is
            # missing" failure). Intersect against the table with the
            # widest key — RewettingCarbonFactor's (climate, moisture,
            # soil_type, land_use_type) — which is the strictest filter
            # and so prunes the tuples whose downstream lookups would
            # also fail.
            valid_set = frozenset(
                ipcc_models.RewettingCarbonFactor.objects.values_list(
                    "land_use_type_id", "climate_id", "moisture_id", "soil_type_id",
                )
            )
            if not valid_set:
                return None
            soil_idx = _idx("soil_types")
            if soil_idx is None:
                return None
            lut_indices = [
                _idx(k) for k in (
                    "land_use_type_start", "land_use_type_w", "land_use_type_wo", "land_use_type",
                ) if _idx(k) is not None
            ]
            if not lut_indices:
                return None

            def validator(combo):
                # RewettingCarbonFactor's key already includes
                # (climate, moisture, soil_type) so a hit here implies SOC
                # would also pass — no separate _soc_ok call needed.
                climate, moisture = combo[cm_idx]
                soil_type = combo[soil_idx]
                if soil_type is None:
                    return True
                for li in lut_indices:
                    lut = combo[li]
                    if lut is None:
                        continue
                    if (lut.id, climate.id, moisture.id, soil_type.id) not in valid_set:
                        return False
                return True
            return validator

        if module_type == "ForestManagement":
            # Three reference tables gate ForestManagement permutations:
            #   - ForestCombustionFactor(land_use_type, climate, forest_type)
            #   - ForestManagementAGB(climate, land_use_type, region,
            #     forest_condition_type, forest_type, from_year=0)
            #   - LitterDeadwoodCarbonStock(climate, forest_type,
            #     land_use_type) — the table has no unique constraint, so
            #     duplicate rows trip the calculator's ``.get()`` with
            #     "get() returned more than one LitterDeadwoodCarbonStock".
            #     Keep only the triples that have exactly one row.
            # Any of the three lookups missing → calculator raises and the
            # whole 100-permutation budget burns. Pre-load each as a set
            # and require the combination to satisfy all of them.
            cf_set = frozenset(
                ipcc_models.ForestCombustionFactor.objects.values_list(
                    "land_use_type_id", "climate_id", "forest_type_id",
                )
            )
            agb_set = frozenset(
                ipcc_models.ForestManagementAGB.objects.filter(from_year=0).values_list(
                    "climate_id", "land_use_type_id", "region_id",
                    "forest_condition_type_id", "forest_type_id",
                )
            )
            from django.db.models import Count as _Count
            litter_set = frozenset(
                ipcc_models.LitterDeadwoodCarbonStock.objects.values(
                    "climate_id", "forest_type_id", "land_use_type_id",
                ).annotate(_n=_Count("id")).filter(_n=1).values_list(
                    "climate_id", "forest_type_id", "land_use_type_id",
                )
            )
            if not cf_set and not agb_set and not litter_set:
                return None
            forest_type_idx = _idx("forest_type")
            forest_condition_type_idx = _idx("forest_condition_type")
            if forest_type_idx is None:
                return None
            lut_indices = [
                _idx(k) for k in (
                    "land_use_type_start", "land_use_type_w", "land_use_type_wo", "land_use_type",
                ) if _idx(k) is not None
            ]
            if not lut_indices:
                return None

            def validator(combo):
                if not _soc_ok(combo):
                    return False
                climate, _moisture = combo[cm_idx]
                forest_type = combo[forest_type_idx]
                forest_condition_type = (
                    combo[forest_condition_type_idx]
                    if forest_condition_type_idx is not None else None
                )
                region = combo[region_idx]
                if forest_type is None:
                    return True
                for li in lut_indices:
                    lut = combo[li]
                    if lut is None:
                        continue
                    if cf_set and (lut.id, climate.id, forest_type.id) not in cf_set:
                        return False
                    if (
                        agb_set
                        and forest_condition_type is not None
                        and region is not None
                        and (
                            climate.id, lut.id, region.id,
                            forest_condition_type.id, forest_type.id,
                        ) not in agb_set
                    ):
                        return False
                    if litter_set and (climate.id, forest_type.id, lut.id) not in litter_set:
                        return False
                return True
            return validator

        return None

    def _chunked_constrained_product(self, *iterables, chunk_size: int = 1000):
        """Yield chunks of Cartesian product with ``_PairedValues`` flattening."""
        it = itertools.product(*iterables)
        while True:
            raw_chunk = list(itertools.islice(it, chunk_size))
            if not raw_chunk:
                break
            yield [self._flatten_combo(combo) for combo in raw_chunk]

    def compute_permutations(
        self, fields: Dict[str, Any], model: Any, chunk_size: int = 10000,
        stop_at: Optional[int] = None, is_coastal: bool = False,
        max_workers: Optional[int] = None, progress_callback=None,
        paired_keys: Optional[List[Tuple[str, str]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
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

        # Filter regions to only include those with countries that have
        # ipcc_region set — LivestockCalculator's LivestockTAM lookup
        # filters by country.ipcc_region and crashes with "Could not find
        # TAM (START) for ..., None" otherwise.
        regions_with_countries = list(
            models.Region.objects.filter(
                countries__isnull=False,
                countries__ipcc_region__isnull=False,
            ).distinct()
        )

        logger.info(f"Found {len(regions_with_countries)} regions with countries (out of {models.Region.objects.count()} total regions)")

        # Update fields with validated dimensions
        fields.update(
            {
                "climate_moistures": valid_climate_moistures,
                "soil_types": valid_soil_types,
                "region": regions_with_countries,
            }
        )

        logger.info(f"Computing permutations for {model.__name__}...")

        # Get processor
        processor = self.processor_registry.get_processor(model.__name__)

        # Prepare iterables, respecting paired fields that must vary together
        use_constrained = bool(paired_keys)

        if use_constrained:
            paired_start_keys = {s for s, _ in paired_keys}
            paired_w_keys = {w for _, w in paired_keys}
            paired_map = {s: w for s, w in paired_keys}

            iterables = []
            field_keys = list(fields.keys())
            skip_keys: set = set()

            for key in field_keys:
                if key in skip_keys:
                    continue

                val = fields[key]
                items = list(val) if not isinstance(val, int) else list(range(val))

                if key in paired_start_keys:
                    # Paired _start key: merge with its _w counterpart into
                    # a single axis using _PairedValues so the product yields
                    # one element that will be unpacked into two positions.
                    w_key = paired_map[key]
                    skip_keys.add(w_key)
                    iterables.append([_PairedValues(v, v) for v in items])
                elif key in paired_w_keys:
                    # Already consumed by the start key above
                    continue
                else:
                    iterables.append(items)

            total = math.prod(len(x) for x in iterables)
            logger.info(f"Total permutations (constrained): {total:,}")
        else:
            # Original behaviour: full cartesian product
            iterables = [list(val) if not isinstance(val, int) else list(range(val)) for val in fields.values()]
            total = math.prod(len(x) for x in iterables)
            logger.info(f"Total permutations (theoretical): {total:,}")

        # Per-module reference-data validator. If the module has IPCC table
        # dependencies (e.g. PerennialCropland → PerennialAGB) the validator
        # drops combinations whose (LUT, climate, moisture, ...) tuple has no
        # matching row, so the worker pool never sees them.
        combination_validator = self._build_combination_validator(model.__name__, fields)
        if combination_validator is not None:
            logger.info(f"Per-module reference-data validator active for {model.__name__}")

        data = []
        errors_data = []

        try:
            # Use more workers for better CPU utilization
            # You can adjust this based on your system's capabilities
            # A good rule of thumb is to use CPU cores - 1 or CPU cores - 2
            if max_workers is None:
                max_workers = min(12, os.cpu_count() - 1) if os.cpu_count() else 8
            logger.info(f"Using {max_workers} worker processes for computation")

            # Performance monitoring
            start_time = time.time()
            processed_count = 0

            # Use 'fork' context explicitly: the management command is single-threaded so
            # fork is safe, and it avoids the spawn chicken-and-egg where unpickling the
            # initializer imports api.minitool (which runs module-level ORM queries)
            # before Django is set up — causing "populate() isn't reentrant" on macOS.
            import multiprocessing
            mp_context = multiprocessing.get_context("fork")
            # Close parent's DB connections before forking so children don't inherit
            # the open socket. With fork, psycopg2's close() in child sends a
            # protocol-level termination over the shared FD, killing the parent's connection.
            from django.db import connections
            connections.close_all()
            with ProcessPoolExecutor(max_workers=max_workers, initializer=self.django_initializer, mp_context=mp_context) as executor:
                pbar = tqdm(total=total, desc=f"Building {model.__name__} permutations", unit=" permutations", postfix={"success": 0, "errors": 0})

                # Optimize chunk size based on number of workers
                optimal_chunk_size = max(chunk_size, chunk_size // max_workers * max_workers)
                logger.info(f"Using chunk size: {optimal_chunk_size}")

                if use_constrained:
                    chunk_iter = self._chunked_constrained_product(*iterables, chunk_size=optimal_chunk_size)
                else:
                    chunk_iter = self.chunked_product(*iterables, chunk_size=optimal_chunk_size)

                stopped_early = False
                for chunk in chunk_iter:
                    if stopped_early:
                        # Executor is already shut down — submitting more
                        # futures would raise "cannot schedule new futures
                        # after shutdown" and abort the whole run.
                        break

                    # Filter out combinations the per-module reference-data
                    # validator rejects. Skipped combinations don't count
                    # against the cap or surface as errors — they're dropped
                    # silently so the runner spends its budget on permutations
                    # that can actually compute.
                    if combination_validator is not None:
                        chunk = [c for c in chunk if combination_validator(c)]
                        if not chunk:
                            continue

                    # Use submit instead of map for better load balancing
                    futures = [executor.submit(processor.process_combination, combo) for combo in chunk]

                    for future in futures:
                        result = future.result()

                        # stop_at caps total work — successes AND errors. Without
                        # the errors term, a run where every permutation raises
                        # exhausts the full Cartesian product before exiting,
                        # producing "All N permutations failed" with N way over
                        # the cap (seen in Test Run #1 with N up to 9600).
                        if stop_at and (len(data) + len(errors_data)) >= stop_at:
                            if hasattr(executor, "_processes"):
                                for proc in executor._processes.values():
                                    proc.terminate()
                            executor.shutdown(wait=False, cancel_futures=True)
                            stopped_early = True
                            break

                        if result.success:
                            if result.data.get("total", 0) != 0:
                                data.append(result.data)
                                pbar.set_postfix({"success": len(data), "errors": len(errors_data)})
                        else:
                            errors_data.append(result.error)
                            pbar.set_postfix({"success": len(data), "errors": len(errors_data)})

                        pbar.update(1)
                        processed_count += 1

                        if progress_callback and processed_count % 500 == 0:
                            pct = min(int(processed_count * 100 / total), 99)
                            progress_callback(pct)

                        # Log performance every 1000 processed items
                        if processed_count % 1000 == 0:
                            elapsed_time = time.time() - start_time
                            rate = processed_count / elapsed_time if elapsed_time > 0 else 0
                            logger.info(f"Processed {processed_count:,} items at {rate:.1f} items/sec")
                    else:
                        continue
                    break

                pbar.close()

        except KeyboardInterrupt:
            logger.info(f"\nKeyboard interrupt detected! Returning {len(data)} computed rows...")
            try:
                pbar.close()
            except Exception:
                pass
            return data, errors_data

        if not data:
            logger.warning(f"No data for {model.__name__}!")
            return [], errors_data

        # Log summary of results
        total_processed = len(data) + len(errors_data)
        success_rate = (len(data) / total_processed * 100) if total_processed > 0 else 0
        logger.info(f"Completed {model.__name__}: {len(data):,} successful, {len(errors_data):,} errors ({success_rate:.1f}% success rate)")

        return data, errors_data


import api.models as models
import ipcc.models as ipcc_models


# A handful of LandUseType / FuelType options exist in MODULE_CONFIGS'
# querysets but lack the IPCC reference data the calculators depend on,
# so picking them deterministically yields "X does not exist / not found
# / is missing. Please provide a tier 2 value" errors. This page exists
# to exercise the math, not surface reference-data gaps — so we gate the
# querysets on the presence of the relevant IPCC record. The filters
# below intersect each LUT/FuelType queryset with the LUT/FuelType ids
# that appear in the required reference table.

# PerennialAGB has records keyed by (climate, moisture, continent,
# land_use_type). A LUT is "testable" for PerennialCropland only if at
# least one PerennialAGB record exists for it.
_PERENNIAL_TESTABLE_LUTS = ipcc_models.PerennialAGB.objects.values_list(
    "land_use_type", flat=True,
).distinct()

# ForestCombustionFactor is keyed by (climate, forest_type,
# land_use_type) — testable LUTs are the ones with at least one record.
_FOREST_TESTABLE_LUTS = ipcc_models.ForestCombustionFactor.objects.values_list(
    "land_use_type", flat=True,
).distinct()


# Module configurations
MODULE_CONFIGS = {
    "Grassland": {
        "fields": {
            "grassland_management_type_start": models.GrasslandManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "grassland_management_type_w": models.GrasslandManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "is_fire_used_start": [True, False],
            "is_fire_used_w": [True, False],
            "fire_periodicity_start": [1],
            "fire_periodicity_w": [1],
            "fire_impact_start": [1, 0],
            "fire_impact_w": [1, 0],
        },
        "config_name": "grassland",
    },
    "Livestock": {
        "fields": {
            "livestock_category_types": models.LivestockCategoryType.objects.all(),
            "livestock_production_type_start": models.LivestockProductionType.objects.all(),
            "livestock_production_type_w": models.LivestockProductionType.objects.all(),
            "heads_number_start": [1],
            "heads_number_w": [1],
        },
        "config_name": "livestock",
    },
    "AnnualCropland": {
        "fields": {
            # Filtered querysets (not .get()) — _constrain_fields_for_change
            # iterates every paired _start/_w value, including ones held fixed,
            # via `list(fields[key])`. A single ORM instance is not iterable.
            "land_use_type_start": models.LandUseType.objects.filter(name="Default"),
            "land_use_type_w": models.LandUseType.objects.filter(name="Default"),
            "tillage_management_type_start": models.TillageManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "tillage_management_type_w": models.TillageManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "organic_input_type_start": models.OrganicInputType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "organic_input_type_w": models.OrganicInputType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "residue_management_type_start": models.ResidueManagementType.objects.all(),
            "residue_management_type_w": models.ResidueManagementType.objects.all(),
        },
        "config_name": "annual_cropland",
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
        "config_name": "flooded_rice",
    },
    "PerennialCropland": {
        "fields": {
            # id__in=_PERENNIAL_TESTABLE_LUTS drops LUTs that lack PerennialAGB
            # reference data (e.g. "Alley Cropping" in some climates) so the
            # runner doesn't waste 100 permutations on "PerennialAGB ... does
            # not exist" errors that aren't actually computation bugs.
            "land_use_type_start": models.LandUseType.objects.filter(
                module_types__name="Perennial Cropland",
                id__in=_PERENNIAL_TESTABLE_LUTS,
            ).all(),
            "land_use_type_w": models.LandUseType.objects.filter(
                module_types__name="Perennial Cropland",
                id__in=_PERENNIAL_TESTABLE_LUTS,
            ).all(),
            "organic_input_type_start": models.OrganicInputType.objects.filter(is_active=True).all(),
            "organic_input_type_w": models.OrganicInputType.objects.filter(is_active=True).all(),
            "tillage_management_type_start": models.TillageManagementType.objects.all(),
            "tillage_management_type_w": models.TillageManagementType.objects.all(),
            "is_biomass_burned_start": [True, False],
            "is_biomass_burned_w": [True, False],
            "fire_periodicity_t2_start": [1],
            "fire_periodicity_t2_w": [1],
        },
        "config_name": "perennial_cropland",
    },
    "ForestManagement": {
        "fields": {
            # See _PERENNIAL_TESTABLE_LUTS note: filter to LUTs that have at
            # least one ForestCombustionFactor record so the runner doesn't
            # spin on "Combustion Factor not found for Rainforest, ..." errors.
            "land_use_type_start": models.LandUseType.objects.filter(
                module_types__name="Forest Management",
                id__in=_FOREST_TESTABLE_LUTS,
            ).all(),
            "forest_type": models.ForestType.objects.all(),
            "forest_condition_type": models.ForestConditionType.objects.all(),
            "average_yearly_degradation_percentage_start": [0],
            "average_yearly_degradation_percentage_w": [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5],  # 1% to 5% and then 10% to 50%
        },
        "config_name": "forest_management",
    },
    "SmallFishery": {
        "fields": {
            "gear_type_start": models.SmallFisheryGearType.objects.all(),
            "gear_type_w": models.SmallFisheryGearType.objects.all(),
            "fishery_type": models.FisheryType.objects.all(),
            "total_catch_yr_start": [1, 0],
            "total_catch_yr_w": [1, 0],
        },
        "config_name": "small_fishery",
    },
    "LargeFishery": {
        "fields": {
            "gear_type_start": models.LargeFisheryGearType.objects.all(),
            "gear_type_w": models.LargeFisheryGearType.objects.all(),
            "fish_type": models.FishType.objects.all(),
            "total_catch_yr_start": [1, 0],
            "total_catch_yr_w": [1, 0],
        },
        "config_name": "large_fishery",
    },
    # NOTE: Not needed
    # "Aquaculture": {
    #     "fields": {
    #         "annual_production_start": [1],
    #         "annual_production_w": [1],
    #     },
    #     "enabled": CONFIG["aquaculture"],
    # },
    "CoastalWetland": {
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland").all(),
            "area_under_drainage_start": [1, 0],
            "area_under_drainage_w": [1, 0],
            "drained_area_excavated_start": [1, 0],
            "drained_area_excavated_w": [1, 0],
            "area_not_drained_or_rewetted_start": [0],
            "area_not_drained_or_rewetted_w": [0],
            "area_w_restored_vegetation_start": [0],
            "area_w_restored_vegetation_w": [0],
        },
        "config_name": "coastal_wetland",
    },
    "CoastalWetland2": {
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland").all(),
            "area_under_drainage_start": [0],
            "area_under_drainage_w": [0],
            "drained_area_excavated_start": [0],
            "drained_area_excavated_w": [0],
            "area_not_drained_or_rewetted_start": [1, 0],
            "area_not_drained_or_rewetted_w": [1, 0],
            "area_w_restored_vegetation_start": [1, 0],
            "area_w_restored_vegetation_w": [1, 0],
        },
        "config_name": "coastal_wetland",
    },
    "Waterbody": {
        "fields": {
            "waterbody_type": models.WaterbodyType.objects.all(),
            "trophic_type_start": models.TrophicType.objects.all(),
            "trophic_type_w": models.TrophicType.objects.all(),
        },
        "config_name": "waterbody",
    },
    # Parent modules with a single submodule type. Field lists mirror the
    # *Entry submodule's columns — the processor below builds the parent
    # plus one submodule and runs the submodule's calculator directly so we
    # don't have to persist the parent's `.entries.all()` relation.
    "Energy": {
        "fields": {
            # Exclude Wood/Peat/Charcoal — those fuels route through
            # gwp.ch4_fossil which is nullable on GlobalWarmingPotential
            # and crashes the math when None. Same exclusion already used
            # by IrrigationPhase for the same reason.
            "fuel_type_start": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "fuel_type_w": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "account_for_co2_start": [True, False],
            "account_for_co2_w": [True, False],
            "quantity_consumed_per_year_start": [1],
            "quantity_consumed_per_year_w": [1],
        },
        "config_name": "energy",
    },
    "Storage": {
        "fields": {
            "fuel_type_start": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "fuel_type_w": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "quantity_consumed_per_year_start": [1],
            "quantity_consumed_per_year_w": [1],
            "is_refrigerant_used_start": [True, False],
            "is_refrigerant_used_w": [True, False],
            "refrigerant_type_start": models.RefrigerantType.objects.all(),
            "refrigerant_type_w": models.RefrigerantType.objects.all(),
        },
        "config_name": "storage",
    },
    "Processing": {
        "fields": {
            "fuel_type_start": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "fuel_type_w": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "quantity_consumed_per_year_start": [1],
            "quantity_consumed_per_year_w": [1],
            "is_water_used_start": [True, False],
            "is_water_used_w": [True, False],
        },
        "config_name": "processing",
    },
    "Packaging": {
        "fields": {
            "packaging_material_type_start": models.PackagingMaterialType.objects.all(),
            "packaging_material_type_w": models.PackagingMaterialType.objects.all(),
            "kg_of_packaging_material_start": [1],
            "kg_of_packaging_material_w": [1],
            "is_electric_start": [True, False],
            "is_electric_w": [True, False],
        },
        "config_name": "packaging",
    },
    "Transport": {
        "fields": {
            "fuel_type_start": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "fuel_type_w": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "quantity_consumed_per_year_start": [1],
            "quantity_consumed_per_year_w": [1],
        },
        "config_name": "transport",
    },
    # Parent modules with multiple submodule types — one MODULE_CONFIGS entry
    # per submodule class. ChangeRecord.module_type stores the submodule
    # class name (e.g. "IrrigationSystem"), and the corresponding processor
    # wires up the parent (Irrigation/Settlement) at build-time so the
    # submodule's calculator can resolve `self.module.parent.activity`.
    "IrrigationSystem": {
        "fields": {
            "irrigation_system_type_start": models.IrrigationSystemType.objects.filter(module_types__class_name="IrrigationSystem").all(),
            "irrigation_system_type_w": models.IrrigationSystemType.objects.filter(module_types__class_name="IrrigationSystem").all(),
            "ha_start": [1],
            "ha_w": [1],
            "ef_t2_start": [0],
            "ef_t2_w": [0],
        },
        "config_name": "irrigation_system",
    },
    "IrrigationPhase": {
        "fields": {
            "irrigation_system_type_start": models.IrrigationSystemType.objects.filter(module_types__class_name="IrrigationPhase").all(),
            "irrigation_system_type_w": models.IrrigationSystemType.objects.filter(module_types__class_name="IrrigationPhase").all(),
            "fuel_type_start": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "fuel_type_w": models.FuelType.objects.filter(fuel_use_type__name__icontains="stationary").exclude(name__in=["Wood", "Peat", "Charcoal"]).all(),
            "ha_start": [1],
            "ha_w": [1],
            "gross_irrigation_water_start": [1],
            "gross_irrigation_water_w": [1],
        },
        "config_name": "irrigation_phase",
    },
    "Settlement": {
        "fields": {
            "land_use_type_start": models.LandUseType.objects.filter(name_en="Settlement").all(),
            "settlement_type_start": models.SettlementType.objects.all(),
            "settlement_type_w": models.SettlementType.objects.all(),
            "biomass_t2_start": [0],
            "biomass_t2_w": [0],
        },
        "config_name": "settlement",
    },
    "Building": {
        "fields": {
            "building_type_start": models.BuildingType.objects.all(),
            "building_type_w": models.BuildingType.objects.all(),
            "area_m2_start": [1],
            "area_m2_w": [1],
            "ef_t2_start": [0],
            "ef_t2_w": [0],
        },
        "config_name": "building",
    },
    "Road": {
        "fields": {
            "road_type_start": models.RoadType.objects.all(),
            "road_type_w": models.RoadType.objects.all(),
            "length_km_start": [1],
            "length_km_w": [1],
            "width_m_start": [1],
            "width_m_w": [1],
        },
        "config_name": "road",
    },
    "OtherInfrastructure": {
        "fields": {
            "area_m2_start": [1],
            "area_m2_w": [1],
            "ef_t2_start": [0],
            "ef_t2_w": [0],
        },
        "config_name": "other_infrastructure",
    },
    "LandUseChange": {
        # LandUseChange wires three land-modules together (start / with /
        # without). The permutation engine here only varies the module_type
        # FK pair; per-side land-module attributes are picked by the
        # processor to keep the search space tractable.
        "fields": {
            "module_type_start": models.ModuleType.objects.filter(is_luc=True).all(),
            "module_type_w": models.ModuleType.objects.filter(is_luc=True).all(),
            "is_fire_used_start": [True, False],
            "is_fire_used_w": [True, False],
        },
        "config_name": "land_use_change",
    },
    # "OtherLand": {
    #     # TODO: I don't think this makes much sense.
    #     "fields": {
    #         "is_degraded_land_start": [True, False],
    #         "is_degraded_land_w": [True, False],
    #     },
    # },
    # "SetAside": {
    #     # TODO: I don't think this makes much sense.
    #     "fields": {
    #         "is_set_aside_start": [True, False],
    #         "is_set_aside_w": [True, False],
    #     },
    # },
}


def run():
    """Main execution function"""
    # Suppress log noise
    logging.getLogger().setLevel(logging.CRITICAL)
    logger.info("Running script without noisy logging...")

    # Initialize components
    data_builder_registry = ModuleDataBuilderRegistry()
    processor_registry = ProcessorRegistry(data_builder_registry)
    data_manager = DataManager()  # Will use STORAGE_BUCKET from environment
    permutation_computer = PermutationComputer(processor_registry)

    # Load configuration
    config_loader = ConfigurationLoader()
    config = config_loader.load_config(local=True)

    # Extract configuration
    CONFIG = {**config["modules"], **config["performance"]}

    try:
        for module_name, config in MODULE_CONFIGS.items():
            if CONFIG[config["config_name"]]:
                model_class = getattr(models, module_name)
                data, errors = permutation_computer.compute_permutations(config["fields"], model_class, chunk_size=CONFIG["chunk_size"], stop_at=CONFIG["max_rows"], max_workers=CONFIG["max_workers"])
                if data or errors:
                    data_manager.save_data(data, errors, module_name)

    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt detected in main run function!")
        logger.info("Script terminated by user. Any completed computations have been saved.")
        return
