"""
Modified minitool_hamming.py script that uses scenario-based configurations.

This script imports the scenario configurations from minitool_hamming_scenarios.py
and uses them instead of the default MODULE_CONFIGS. This allows for scenario-specific
permutation generation based on the emission scenarios defined in the compile_scenarios.py.
"""

import pandas as pd
from dataclasses import dataclass
import os
import sys
import logging
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

import api.models as models  # noqa: E402
import ipcc.models as ipcc_models  # noqa: E402

# Import Hamming functions
from .hamming import hamming_shell_rows  # noqa: E402

# Import scenario configurations
from .minitool_hamming_scenarios import MODULE_CONFIGS, get_all_scenarios, get_scenario_metadata  # noqa: E402

# Import all the classes and functions from the original hamming script
from .minitool_hamming import (  # noqa: E402
    extract_relevant_traceback,
    DataProcessorError,
    ProgressTracker,
    ProcessingResult,
    BaseData,
    FieldType,
    FieldMapping,
    FieldMappingBuilder,
    ModuleDataBuilder,
    AnnualCroplandDataBuilder,
    LivestockDataBuilder,
    GrasslandDataBuilder,
    FloodedRiceDataBuilder,
    PerennialCroplandDataBuilder,
    ForestManagementDataBuilder,
    SmallFisheryDataBuilder,
    LargeFisheryDataBuilder,
    InputDataBuilder,
    InputEntryDataBuilder,
    WaterbodyDataBuilder,
    CoastalWetlandDataBuilder,
    LandUseChangeDataBuilder,
    ModuleDataBuilderRegistry,
    ModuleProcessor,
    GrasslandProcessor,
    LivestockProcessor,
    AnnualCroplandProcessor,
    FloodedRiceProcessor,
    PerennialCroplandProcessor,
    ForestManagementProcessor,
    SmallFisheryProcessor,
    LargeFisheryProcessor,
    InputProcessor,
    WaterbodyProcessor,
    CoastalWetlandProcessor,
    LandUseChangeProcessor,
    ProcessorRegistry,
    ClimateMoistureValidator,
    SoilOrganicCarbonValidator,
    CombinationValidator,
    DefaultCombinationValidator,
    PerennialCroplandCombinationValidator,
    LandUseChangeCombinationValidator,
    GrasslandCombinationValidator,
    LivestockCombinationValidator,
    FisheryCombinationValidator,
    CroplandCombinationValidator,
    ForestManagementCombinationValidator,
    WetlandCombinationValidator,
    ValidatorRegistry,
    ConfigurationLoader,
    DataManager,
    HammingPermutationComputer,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_minitool_hamming_with_scenarios(resume: bool = False, count_only: bool = False):
    """
    Main execution function using scenario-based Hamming shell permutations.

    This function uses the scenario configurations from minitool_hamming_scenarios.py
    instead of the default MODULE_CONFIGS, allowing for scenario-specific processing.
    """
    # Set logging level to INFO to see progress messages
    logging.getLogger().setLevel(logging.INFO)

    if count_only:
        logger.info("Running scenario-based Hamming shell permutation count calculation...")
        return run_minitool_hamming_count_only_with_scenarios()
    else:
        logger.info("Running scenario-based Hamming shell permutation script with progress logging...")

    # Initialize components
    data_builder_registry = ModuleDataBuilderRegistry()
    processor_registry = ProcessorRegistry(data_builder_registry)
    data_manager = DataManager()  # Will use STORAGE_BUCKET from environment
    hamming_computer = HammingPermutationComputer(processor_registry)

    # Load configuration
    config_loader = ConfigurationLoader()
    config = config_loader.load_config(local=True)

    # Extract configuration
    CONFIG = {**config["modules"], **config["performance"]}

    # Print scenario information
    scenarios = get_all_scenarios()
    logger.info(f"Processing {len(scenarios)} scenarios across {len(MODULE_CONFIGS)} module types")

    for module_name, module_config in MODULE_CONFIGS.items():
        if "subsets" in module_config:
            logger.info(f"Module {module_name}: {len(module_config['subsets'])} scenarios")
            for subset in module_config["subsets"]:
                logger.info(f"  - {subset['category']}: {subset['name']}")

    try:
        for module_name, module_config in MODULE_CONFIGS.items():
            if CONFIG[module_config["config_name"]]:
                logger.info(f"Processing module: {module_name}")
                model_class = getattr(models, module_name)

                # Handle subsets logic - if no subsets key exists, create one with the config itself
                if module_config.get("subsets", None) is None:
                    module_config["subsets"] = [module_config]

                for subset_index, subset in enumerate(module_config["subsets"]):
                    logger.info(f"Processing scenario {subset_index + 1}/{len(module_config['subsets'])} for module: {module_name}")
                    logger.info(f"Scenario: {subset['name']} ({subset['category']})")

                    # Get filename for this subset if present
                    subset_filename = subset.get("filename", None)

                    # Create a descriptive filename if none provided
                    if not subset_filename:
                        # Create a safe filename from the scenario name
                        safe_name = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in subset["name"])
                        safe_name = safe_name.replace(" ", "_").lower()
                        subset_filename = f"{module_name.lower()}_{safe_name}"

                    data, errors = hamming_computer.compute_hamming_permutations(
                        subset["fields"], model_class, chunk_size=CONFIG["chunk_size"], stop_at=CONFIG["max_rows"], max_workers=CONFIG["max_workers"], resume=resume, filename=subset_filename
                    )

                    logger.info(f"Scenario {subset_index + 1}/{len(module_config['subsets'])} completed: {len(data)} data rows, {len(errors)} error rows")

                    # Save data immediately after each subset
                    # If using custom filename, each subset has its own progress tracking
                    # For custom filenames, only append if resuming that specific subset
                    # For default filenames, append for subsequent subsets
                    if subset_filename:
                        # Custom filename: when resuming, don't append - save entire dataset
                        should_append = False
                    else:
                        # Default filename: append for subsequent subsets
                        should_append = resume if subset_index == 0 else True

                    if data or errors:
                        # Use custom filename if provided in subset config, otherwise use module name
                        filename = subset.get("filename", subset_filename)
                        logger.info(f"Saving data for module: {module_name}, scenario {subset_index + 1} to file: {filename}")
                        data_manager.save_data(data, errors, filename, local=True, resume=should_append)
                        logger.info(f"Data saved for module: {module_name}, scenario {subset_index + 1} to file: {filename}")
                    else:
                        logger.warning(f"No data or errors to save for module: {module_name}, scenario {subset_index + 1}")

    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt detected in main run function!")
        logger.info("Script terminated by user. Any completed computations have been saved.")
        return


def run_minitool_hamming_count_only_with_scenarios():
    """Calculate and display the number of permutations for each scenario without processing them"""
    import api.models as models

    logger.info("Calculating permutation counts for all scenarios...")

    # Initialize components
    data_builder_registry = ModuleDataBuilderRegistry()
    processor_registry = ProcessorRegistry(data_builder_registry)
    hamming_computer = HammingPermutationComputer(processor_registry)

    # Load configuration
    config_loader = ConfigurationLoader()
    config = config_loader.load_config(local=True)

    # Extract configuration
    CONFIG = {**config["modules"], **config["performance"]}

    total_permutations = 0
    scenario_counts = []

    for module_name, module_config in MODULE_CONFIGS.items():
        if CONFIG[module_config["config_name"]]:
            logger.info(f"\nModule: {module_name}")
            model_class = getattr(models, module_name)

            # Handle subsets logic
            if module_config.get("subsets", None) is None:
                module_config["subsets"] = [module_config]

            module_total = 0
            for subset_index, subset in enumerate(module_config["subsets"]):
                try:
                    # Calculate expected count for this scenario
                    expected_count = hamming_computer.expected_count(subset["fields"])
                    module_total += expected_count

                    scenario_info = {"module": module_name, "scenario": subset["name"], "category": subset["category"], "count": expected_count}
                    scenario_counts.append(scenario_info)

                    logger.info(f"  Scenario {subset_index + 1}: {subset['name']} - {expected_count:,} permutations")

                except Exception as e:
                    logger.error(f"  Error calculating count for scenario {subset['name']}: {str(e)}")
                    scenario_info = {"module": module_name, "scenario": subset["name"], "category": subset["category"], "count": 0, "error": str(e)}
                    scenario_counts.append(scenario_info)

            logger.info(f"Module {module_name} total: {module_total:,} permutations")
            total_permutations += module_total

    logger.info(f"\nTotal permutations across all scenarios: {total_permutations:,}")

    # Print summary by category
    categories = {}
    for scenario in scenario_counts:
        category = scenario["category"]
        if category not in categories:
            categories[category] = 0
        categories[category] += scenario.get("count", 0)

    logger.info("\nPermutations by category:")
    for category, count in sorted(categories.items()):
        logger.info(f"  {category}: {count:,} permutations")

    return total_permutations, scenario_counts


def run(*args):
    """Entry point for the script"""
    import argparse

    parser = argparse.ArgumentParser(description="Run scenario-based Hamming shell permutations")
    parser.add_argument("--resume", action="store_true", help="Resume from previous progress")
    parser.add_argument("--count-only", action="store_true", help="Only calculate permutation counts")

    parsed_args = parser.parse_args(args)

    run_minitool_hamming_with_scenarios(resume=parsed_args.resume, count_only=parsed_args.count_only)


if __name__ == "__main__":
    run()
