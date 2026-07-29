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
import json
from google.cloud import storage

# Django setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")

import django

django.setup()

import api.models as models


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


class ProgressTracker:
    """Tracks and saves progress for permutation processing"""

    def __init__(self, module_name: str, progress_dir: str = "scripts/minitool/progress"):
        self.module_name = module_name
        self.progress_dir = Path(progress_dir)
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.progress_dir / f"{module_name.lower()}_progress.json"
        self.current_index = 0
        self.total_permutations = 0
        self.start_time = None
        self.last_save_time = time.time()
        self.save_interval = 10  # Save progress every 10 seconds

    def load_progress(self) -> bool:
        """Load progress from file. Returns True if progress was loaded, False otherwise."""
        if not self.progress_file.exists():
            return False

        try:
            with open(self.progress_file, "r") as f:
                data = json.load(f)
                self.current_index = data.get("current_index", 0)
                self.total_permutations = data.get("total_permutations", 0)
                self.start_time = data.get("start_time", time.time())
                logger.info(f"Loaded progress for {self.module_name}: {self.current_index:,}/{self.total_permutations:,} permutations processed")
                return True
        except Exception as e:
            logger.warning(f"Failed to load progress for {self.module_name}: {e}")
            return False

    def save_progress(self, force: bool = False):
        """Save current progress to file"""
        current_time = time.time()
        if not force and (current_time - self.last_save_time) < self.save_interval:
            return

        try:
            data = {
                "current_index": self.current_index,
                "total_permutations": self.total_permutations,
                "start_time": self.start_time or time.time(),
                "last_updated": current_time,
                "module_name": self.module_name,
            }
            with open(self.progress_file, "w") as f:
                json.dump(data, f, indent=2)
            self.last_save_time = current_time
            logger.info(f"Progress saved for {self.module_name}: {self.current_index}/{self.total_permutations}")
        except Exception as e:
            logger.warning(f"Failed to save progress for {self.module_name}: {e}")

    def update_progress(self, index: int, total: int):
        """Update current progress"""
        self.current_index = index
        self.total_permutations = total
        if self.start_time is None:
            self.start_time = time.time()
        self.save_progress()

    def increment_progress(self):
        """Increment progress by 1"""
        self.current_index += 1
        self.save_progress()
        # Only log every 100 increments to avoid spam
        if self.current_index % 100 == 0:
            logger.info(f"Progress: {self.module_name} at {self.current_index}/{self.total_permutations}")

    def get_resume_index(self) -> int:
        """Get the index to resume from"""
        return self.current_index

    def clear_progress(self):
        """Clear progress file"""
        if self.progress_file.exists():
            self.progress_file.unlink()
            logger.info(f"Cleared progress for {self.module_name}")

    def get_elapsed_time(self) -> float:
        """Get elapsed time since start"""
        if self.start_time is None:
            return 0
        return time.time() - self.start_time

    def get_eta(self) -> Optional[float]:
        """Get estimated time to completion in seconds"""
        if self.current_index == 0 or self.total_permutations == 0:
            return None
        elapsed = self.get_elapsed_time()
        rate = self.current_index / elapsed if elapsed > 0 else 0
        remaining = self.total_permutations - self.current_index
        return remaining / rate if rate > 0 else None


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
            "land_use_type": getattr(module, "land_use_type_start", None),
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


class InputDataBuilder(ModuleDataBuilder):
    """Data builder for Input modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        # Input module itself doesn't have these fields - they're in InputEntry submodules
        return []

    def get_custom_fields(self, module: Any) -> Dict[str, Any]:
        """Get custom fields from InputEntry submodules"""
        custom_fields = {}

        # Get all input entries for this Input module
        input_entries = module.input_entries.all()

        if input_entries:
            # For now, we'll take the first input entry's data
            # In a more complex scenario, you might want to aggregate or handle multiple entries
            first_entry = input_entries[0]

            custom_fields.update(
                {
                    "input_type": first_entry.input_type.name if first_entry.input_type else None,
                    "value_start": first_entry.value_start,
                    "value_w": first_entry.value_w,
                    "value_wo": first_entry.value_wo,
                }
            )

        return custom_fields


class WaterbodyDataBuilder(ModuleDataBuilder):
    """Data builder for Waterbody modules"""

    def get_field_mappings(self) -> List[FieldMapping]:
        return [
            FieldMappingBuilder.foreign_key("waterbody_type"),
            FieldMappingBuilder.foreign_key("trophic_type"),
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
        self.register("ForestManagement", ForestManagementDataBuilder())
        self.register("SmallFishery", SmallFisheryDataBuilder())
        self.register("LargeFishery", LargeFisheryDataBuilder())
        self.register("Input", InputDataBuilder())
        self.register("Waterbody", WaterbodyDataBuilder())
        self.register("CoastalWetland", CoastalWetlandDataBuilder())

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
    """Abstract base class for module processors

    This class provides the base functionality for processing module combinations.
    Some processors may need to create actual database records (projects, activities, modules)
    when foreign key constraints are required for calculations. In such cases:

    1. Set requires_project_creation = True in the processor's __init__ method
    2. Use create_project() instead of build_project() in create_module()
    3. Use .create() instead of .build() for factories that need database records
    4. The created records will be automatically cleaned up after processing

    Example:
        class MyProcessor(ModuleProcessor):
            def __init__(self, data_builder_registry):
                super().__init__(data_builder_registry)
                self.requires_project_creation = True  # Enable cleanup
    """

    def __init__(self, data_builder_registry: ModuleDataBuilderRegistry):
        self.data_builder_registry = data_builder_registry
        self.project = None
        self.user = models.CustomUser.objects.get_or_create(email="test@test.com")[0]
        self.requires_project_creation = False  # Flag to indicate if this processor needs to create projects for foreign key constraints

    def create_project(self, climate: Any, moisture: Any, soil_type: Any, region: Any, factories: Any) -> Any:
        """Helper method to create a project with proper country selection"""
        # Get a random country from the region, with fallback
        country = region.countries.order_by("?").first()
        if not country:
            # Skip this combination if no country is available
            raise ValueError(f"No countries found for region: {region}")

        self.project = factories.ProjectFactory.create(
            owner=self.user,
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=country,
        )
        return self.project

    def build_project(self, climate: Any, moisture: Any, soil_type: Any, region: Any, factories: Any) -> Any:
        """Helper method to build a project (without saving to database)"""
        # Get a random country from the region, with fallback
        country = region.countries.order_by("?").first()
        if not country:
            # Skip this combination if no country is available
            raise ValueError(f"No countries found for region: {region}")

        self.project = factories.ProjectFactory.build(
            climate=climate,
            moisture=moisture,
            soil_type=soil_type,
            country=country,
        )
        return self.project

    @abstractmethod
    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        """Create a module instance from combination"""
        pass

    def process_combination(self, combination: Tuple) -> ProcessingResult:
        """Process a single combination"""
        created_project = None
        try:
            # Import inside function for multiprocessing compatibility
            import api.tests.factories as factories
            import api.calculators as calculators
            import api.models as models

            # Suppress logging in worker processes
            logging.getLogger().setLevel(logging.CRITICAL)

            # Create module
            module = self.create_module(combination, factories, models)

            # Store reference to created project if this processor creates projects
            if self.requires_project_creation and hasattr(self, "project") and self.project:
                created_project = self.project

            # Calculate result
            balance = calculators.CalculatorFactory().calculate_result(module)[0][2]

            # Build data
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
        finally:
            # Clean up created project if this processor creates projects
            if created_project and self.requires_project_creation:
                try:
                    # Delete the project and all related objects
                    created_project.delete()
                except Exception as cleanup_error:
                    # Log cleanup errors but don't fail the processing
                    logger.warning(f"Failed to cleanup project {created_project.id}: {cleanup_error}")


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


class SmallFisheryProcessor(ModuleProcessor):
    """Processor for Small Fishery modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            gear_type_start,
            gear_type_w,
            fishery_type,
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
        module = factories.SmallFisheryFactory.build(
            activity=a,
            fishery_type=fishery_type,
            gear_type_start=gear_type_start,
            gear_type_w=gear_type_w,
            gear_type_wo=gear_type_start,
            total_catch_yr_start=1,
            total_catch_yr_w=1,
            total_catch_yr_wo=1,
        )
        return module


class LargeFisheryProcessor(ModuleProcessor):
    """Processor for Large Fishery modules"""

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            gear_type_start,
            gear_type_w,
            fish_type,
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
        module = factories.LargeFisheryFactory.build(
            activity=a,
            fish_type=fish_type,
            gear_type_start=gear_type_start,
            gear_type_w=gear_type_w,
            gear_type_wo=gear_type_start,
            total_catch_yr_start=1,
            total_catch_yr_w=1,
            total_catch_yr_wo=1,
        )
        return module


class InputProcessor(ModuleProcessor):
    """Processor for Input modules

    This processor requires project creation because Input modules have foreign key
    constraints that need actual database records to be created for proper calculation.
    The created projects are automatically cleaned up after processing.
    """

    def __init__(self, data_builder_registry: ModuleDataBuilderRegistry):
        super().__init__(data_builder_registry)
        self.requires_project_creation = True  # Input modules need projects for foreign key constraints

    def create_module(self, combination: Tuple, factories: Any, models: Any) -> Any:
        (
            input_type,
            value_start,
            value_w,
            climate_moisture,
            soil_type,
            region,
        ) = combination
        climate, moisture = climate_moisture
        self.project = self.create_project(climate, moisture, soil_type, region, factories)
        a = factories.ActivityFactory.create(project=self.project)
        module = factories.InputFactory.create(
            activity=a,
        )
        submodule = factories.InputEntryFactory.create(
            parent=module,
            input_type=input_type,
            value_start=value_start,
            value_w=value_w,
            value_wo=value_start,
        )
        module.input_entries.add(submodule)
        return module


class WaterbodyProcessor(ModuleProcessor):
    """Processor for Waterbody modules"""

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
            country=region.countries.order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.WaterbodyFactory.build(
            activity=a,
            waterbody_type=waterbody_type,
            trophic_type_start=trophic_type_start,
            trophic_type_w=trophic_type_w,
            trophic_type_wo=trophic_type_start,
        )
        return module

class CoastalWetlandProcessor(ModuleProcessor):
    """Processor for Coastal Wetland modules"""
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
            country=region.countries.order_by("?").first(),
        )
        a = factories.ActivityFactory.build(project=p)
        module = factories.CoastalWetlandFactory.build(
            activity=a,
            land_use_type=land_use_type,
            area_under_drainage_start=area_under_drainage_start,
            area_under_drainage_w=area_under_drainage_w,
            drained_area_excavated_start=drained_area_excavated_start,
            drained_area_excavated_w=drained_area_excavated_w,
            area_not_drained_or_rewetted_start=area_not_drained_or_rewetted_start,
            area_not_drained_or_rewetted_w=area_not_drained_or_rewetted_w,
            area_w_restored_vegetation_start=area_w_restored_vegetation_start,
            area_w_restored_vegetation_w=area_w_restored_vegetation_w,
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
        self.register("SmallFishery", SmallFisheryProcessor(self._data_builder_registry))
        self.register("LargeFishery", LargeFisheryProcessor(self._data_builder_registry))
        self.register("Input", InputProcessor(self._data_builder_registry))
        self.register("Waterbody", WaterbodyProcessor(self._data_builder_registry))
        self.register("CoastalWetland", CoastalWetlandProcessor(self._data_builder_registry))

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

    def save_data(self, data: List[Dict[str, Any]], errors: List[Dict[str, Any]], module_name: str, local: bool = False) -> None:
        """Save data and errors to GCP storage bucket as CSV files"""
        try:
            if local:
                self._save_to_local_fallback(data, errors, module_name)
                return

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
        django.setup()

        from django.db import connections

        connections.close_all()

    def chunked_product(self, *iterables, chunk_size: int = 1000, start_index: int = 0):
        """Yield chunks of Cartesian product, optionally starting from a specific index"""
        it = itertools.product(*iterables)

        # Skip to the start index if specified
        if start_index > 0:
            logger.info(f"Skipping to index {start_index:,} in permutation generation...")
            # Use islice to skip the first start_index items
            it = itertools.islice(it, start_index, None)

        while True:
            chunk = list(itertools.islice(it, chunk_size))
            if not chunk:
                break
            yield chunk

    def compute_permutations(
        self, fields: Dict[str, Any], model: Any, chunk_size: int = 10000, stop_at: Optional[int] = None, is_coastal: bool = False, max_workers: Optional[int] = None, resume: bool = False
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

        # Filter regions to only include those with countries
        # Use a more efficient database query
        regions_with_countries = list(models.Region.objects.filter(countries__isnull=False).distinct())

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

        # Prepare iterables
        iterables = [list(val) if not isinstance(val, int) else range(val) for val in fields.values()]

        # Compute total permutations
        total = math.prod(len(x) for x in iterables)
        logger.info(f"Total permutations (theoretical): {total:,}")

        # Initialize progress tracker
        progress_tracker = ProgressTracker(model.__name__)
        start_index = 0

        logger.info(f"Progress tracker initialized for {model.__name__}")
        logger.info(f"Progress file path: {progress_tracker.progress_file}")

        if resume:
            if progress_tracker.load_progress():
                start_index = progress_tracker.get_resume_index()
                logger.info(f"Resuming {model.__name__} from permutation {start_index:,}")
            else:
                logger.info(f"No previous progress found for {model.__name__}, starting from beginning")
        else:
            # Clear any existing progress if not resuming
            progress_tracker.clear_progress()
            logger.info(f"Starting fresh computation for {model.__name__}")

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

            with ProcessPoolExecutor(max_workers=max_workers, initializer=self.django_initializer) as executor:
                # Initialize progress tracker with total
                progress_tracker.update_progress(start_index, total)
                # Force save initial progress
                progress_tracker.save_progress(force=True)

                pbar = tqdm(total=total, initial=start_index, desc=f"Building {model.__name__} permutations", unit=" permutations", postfix={"success": 0, "errors": 0})

                # Optimize chunk size based on number of workers
                optimal_chunk_size = max(chunk_size, chunk_size // max_workers * max_workers)
                logger.info(f"Using chunk size: {optimal_chunk_size}")

                for chunk in self.chunked_product(*iterables, chunk_size=optimal_chunk_size, start_index=start_index):
                    # Use submit instead of map for better load balancing
                    futures = [executor.submit(processor.process_combination, combo) for combo in chunk]

                    for future in futures:
                        result = future.result()

                        if stop_at and len(data) >= stop_at:
                            # Terminate worker processes
                            for proc in executor._processes.values():
                                proc.terminate()
                            executor.shutdown(wait=False, cancel_futures=True)
                            break

                        if result.success:
                            data.append(result.data)
                            pbar.set_postfix({"success": len(data), "errors": len(errors_data)})
                        else:
                            errors_data.append(result.error)
                            pbar.set_postfix({"success": len(data), "errors": len(errors_data)})

                        pbar.update(1)
                        processed_count += 1

                        # Update progress tracker
                        progress_tracker.increment_progress()

                        # Log performance every 1000 processed items
                        if processed_count % 1000 == 0:
                            elapsed_time = time.time() - start_time
                            rate = processed_count / elapsed_time if elapsed_time > 0 else 0
                            eta = progress_tracker.get_eta()
                            eta_str = f", ETA: {eta / 60:.1f}min" if eta else ""
                            logger.info(f"Processed {processed_count:,} items at {rate:.1f} items/sec{eta_str}")
                            # Force save progress every 1000 items
                            progress_tracker.save_progress(force=True)
                    else:
                        continue
                    break

                pbar.close()

        except KeyboardInterrupt:
            logger.info(f"\nKeyboard interrupt detected! Returning {len(data)} computed rows...")
            # Force save progress on interrupt
            progress_tracker.save_progress(force=True)
            logger.info(f"Progress saved at permutation {progress_tracker.current_index:,}")
            try:
                pbar.close()
            except Exception:
                pass
            return data, errors_data

        if not data:
            logger.warning(f"No data for {model.__name__}!")
            return [], []

        # Log summary of results
        total_processed = len(data) + len(errors_data)
        success_rate = (len(data) / total_processed * 100) if total_processed > 0 else 0
        logger.info(f"Completed {model.__name__}: {len(data):,} successful, {len(errors_data):,} errors ({success_rate:.1f}% success rate)")

        # Clear progress file on successful completion
        progress_tracker.clear_progress()

        return data, errors_data


# Module configurations
MODULE_CONFIGS = {
    "Grassland": {  # Compute # DONE
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
    "Livestock": {  # Compute # DONE
        "fields": {
            "livestock_category_type": models.LivestockCategoryType.objects.all(),
            "livestock_production_type_start": models.LivestockProductionType.objects.all(),
            "livestock_production_type_w": models.LivestockProductionType.objects.all(),
            "heads_number_start": [1],
            "heads_number_w": [1],
        },
        "config_name": "livestock",
    },
    "AnnualCropland": {  # DONE
        "fields": {
            "land_use_type_start": [models.LandUseType.objects.get(name="Default")],
            "land_use_type_w": [models.LandUseType.objects.get(name="Default")],
            "tillage_management_type_start": models.TillageManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "tillage_management_type_w": models.TillageManagementType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "organic_input_type_start": models.OrganicInputType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "organic_input_type_w": models.OrganicInputType.objects.all(),  # NOTE: To be used in LandUseChange permutation
            "residue_management_type_start": models.ResidueManagementType.objects.all(),
            "residue_management_type_w": models.ResidueManagementType.objects.all(),
        },
        "config_name": "annual_cropland",
    },
    "FloodedRice": {  # Skip
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
    "PerennialCropland": {  # Skip # DONE
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
        "config_name": "perennial_cropland",
    },
    "ForestManagement": {  # Compute
        "fields": {
            "land_use_type_start": models.LandUseType.objects.filter(module_types__name="Forest Management").all(),
            "forest_type": models.ForestType.objects.all(),
            "forest_condition_type": models.ForestConditionType.objects.all(),
            "average_yearly_degradation_percentage_start": [0],
            "average_yearly_degradation_percentage_w": [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5],  # 1% to 5% and then 10% to 50%
        },
        "config_name": "forest_management",
    },
    "SmallFishery": {  # Compute # DONE
        "fields": {
            "gear_type_start": models.SmallFisheryGearType.objects.all(),
            "gear_type_w": models.SmallFisheryGearType.objects.all(),
            "fishery_type": models.FisheryType.objects.all(),
        },
        "config_name": "small_fishery",
    },
    "LargeFishery": {  # Skip # DONE
        "fields": {
            "gear_type_start": models.LargeFisheryGearType.objects.all(),
            "gear_type_w": models.LargeFisheryGearType.objects.all(),
            "fish_type": models.FishType.objects.all(),
        },
        "config_name": "large_fishery",
    },
    "CoastalWetland": {  # Skip
        "fields": {
            "land_use_type": models.LandUseType.objects.filter(module_types__name="Coastal Wetland").all(),
            "area_under_drainage_start": [1, 0],
            "area_under_drainage_w": [1, 0],
            "drained_area_excavated_start": [1, 0],
            "drained_area_excavated_w": [1, 0],
            "area_not_drained_or_rewetted_start": [1, 0],
            "area_not_drained_or_rewetted_w": [1, 0],
            "area_w_restored_vegetation_start": [1, 0],
            "area_w_restored_vegetation_w": [1, 0],
        },
        "config_name": "coastal_wetland",
    },
    "Input": {  # Compute # BUG: ZERO RESULTS
        "fields": {
            "input_type": models.InputType.objects.all(),
            "value_start": [1, 0],
            "value_w": [1, 0],
        },
        "config_name": "input",
    },
    "Waterbody": {  # Compute # DONE
        "fields": {
            "waterbody_type": models.WaterbodyType.objects.all(),
            "trophic_type_start": models.TrophicType.objects.all(),
            "trophic_type_w": models.TrophicType.objects.all(),
        },
        "config_name": "waterbody",
    },
}

"""
# NOTE: Not needed
"Aquaculture": {
    "fields": {
        "annual_production_start": [1],
        "annual_production_w": [1],
    },
    "enabled": CONFIG["aquaculture"],
},
"OtherLand": {
    # TODO: I don't think this makes much sense.
    "fields": {
        "is_degraded_land_start": [True, False],
        "is_degraded_land_w": [True, False],
    },
},
"SetAside": {
    # TODO: I don't think this makes much sense.
    "fields": {
        "is_set_aside_start": [True, False],
        "is_set_aside_w": [True, False],
    },
},
TODO: Missing all Value Chain modules.
"""


def run_minitool(resume: bool = False):
    """Main execution function"""
    # Set logging level to INFO to see progress messages
    logging.getLogger().setLevel(logging.INFO)
    logger.info("Running script with progress logging...")

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
                data, errors = permutation_computer.compute_permutations(
                    config["fields"], model_class, chunk_size=CONFIG["chunk_size"], stop_at=CONFIG["max_rows"], max_workers=CONFIG["max_workers"], resume=resume
                )
                if data or errors:
                    data_manager.save_data(data, errors, module_name, local=True)

    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt detected in main run function!")
        logger.info("Script terminated by user. Any completed computations have been saved.")
        return


# Django runscript entry point
def run(*args):
    """Django runscript entry point that handles command line arguments"""

    resume = False

    if len(args) > 0:
        resume = "resume" in args
        clear_progress = "clear-progress" in args

        print(f"Resume: {resume}")
        print(f"Clear progress: {clear_progress}")

        if clear_progress:
            clear_all_progress()

        print(f"Running minitool with resume: {resume}")

    return run_minitool(resume=resume)


def clear_all_progress():
    """Clear all progress files"""
    progress_dir = Path("scripts/minitool/progress")
    if progress_dir.exists():
        for progress_file in progress_dir.glob("*_progress.json"):
            progress_file.unlink()
            logger.info(f"Cleared progress file: {progress_file}")
        logger.info("All progress files cleared. Starting fresh computation.")
    else:
        logger.info("No progress files found to clear.")
