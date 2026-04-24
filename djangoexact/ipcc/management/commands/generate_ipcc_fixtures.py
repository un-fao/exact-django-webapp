#!/usr/bin/env python3
"""
Django management command to generate fixtures for all IPCC models and their dependencies.

This script methodically creates fixtures for all IPCC models in the correct order
to handle foreign key dependencies. It can also dump the latest API dependency
fixtures from the database to ensure all required reference data is up-to-date.

Usage:
    python manage.py generate_ipcc_fixtures
    python manage.py generate_ipcc_fixtures --include-dependencies
    python manage.py generate_ipcc_fixtures --output-dir /path/to/fixtures
    python manage.py generate_ipcc_fixtures --models GlobalWarmingPotential,SoilOrganicCarbon
    python manage.py generate_ipcc_fixtures --include-dependencies --dry-run
"""

import os
import json
import sys
from django.core.management.base import BaseCommand
from django.core import serializers
from django.db.models import Model

from ipcc.models import *


def _resolve_model_class(model_name: str):
    """Resolve a model name to its class within this module's namespace.

    Returns the class when it is a concrete Django Model subclass, otherwise None.
    Confining the lookup to this module prevents arbitrary name resolution.
    """
    candidate = getattr(sys.modules[__name__], model_name, None)
    if isinstance(candidate, type) and issubclass(candidate, Model):
        return candidate
    return None


class Command(BaseCommand):
    help = "Generate fixtures for all IPCC models in dependency order"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=str, default="ipcc/fixtures", help="Directory to save fixture files (default: ipcc/fixtures)")
        parser.add_argument("--models", type=str, help="Comma-separated list of specific models to generate fixtures for")
        parser.add_argument("--format", type=str, choices=["json", "xml", "yaml"], default="json", help="Output format for fixtures (default: json)")
        parser.add_argument("--indent", type=int, default=2, help="JSON indentation level (default: 2)")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without creating files")
        parser.add_argument("--include-dependencies", action="store_true", help="Also dump API dependency fixtures")
        parser.add_argument("--api-output-dir", type=str, default="api/fixtures", help="Directory to save API dependency fixtures (default: api/fixtures)")

    def handle(self, *args, **options):
        self.output_dir = options["output_dir"]
        self.api_output_dir = options["api_output_dir"]
        self.format = options["format"]
        self.indent = options["indent"]
        self.dry_run = options["dry_run"]
        self.include_dependencies = options["include_dependencies"]

        # Create output directories if they don't exist
        if not self.dry_run:
            os.makedirs(self.output_dir, exist_ok=True)
            if self.include_dependencies:
                os.makedirs(self.api_output_dir, exist_ok=True)

        # Generate API dependency fixtures first if requested
        api_generated_files = []
        if self.include_dependencies:
            self.stdout.write("Generating API dependency fixtures...")
            api_generated_files = self._generate_api_dependency_fixtures()

        # Validate API dependencies exist before generating IPCC fixtures
        if not self.dry_run:
            self._validate_api_dependencies()

        # Get models to process
        if options["models"]:
            model_names = [name.strip() for name in options["models"].split(",")]
            models_to_process = self._get_specific_models(model_names)
        else:
            models_to_process = self._get_all_ipcc_models()

        self.stdout.write(f"Processing {len(models_to_process)} IPCC models...")

        # Generate fixtures in dependency order
        generated_files = []
        for model_class in models_to_process:
            try:
                fixture_file = self._generate_fixture_for_model(model_class)
                if fixture_file:
                    generated_files.append(fixture_file)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error generating fixture for {model_class.__name__}: {e}"))

        # Generate combined fixture files
        if not self.dry_run:
            if api_generated_files:
                self._generate_combined_fixture(api_generated_files, self.api_output_dir, "all_api_dependencies")
            if generated_files:
                self._generate_combined_fixture(generated_files, self.output_dir, "all_ipcc_fixtures")

        total_files = len(api_generated_files) + len(generated_files)
        self.stdout.write(self.style.SUCCESS(f"Successfully generated {total_files} fixture files ({len(api_generated_files)} API, {len(generated_files)} IPCC)"))

    def _get_all_ipcc_models(self):
        """Get all IPCC models in dependency order."""
        # Define the order based on foreign key dependencies
        # Models with no dependencies first, then models that depend on them
        model_order = [
            # Models with no foreign key dependencies to other IPCC models
            "GlobalWarmingPotential",
            "EmissionFactorCategory",
            "EmissionType",
            # Models that depend on API models only (no IPCC dependencies)
            "DataOnMangrove",
            "ForestCombustionFactor",
            "AfforestationCombustionFactor",
            "LitterDeadwoodCarbonStock",
            "LandUseCarbonStockExchangeFactor",
            "SoilOrcanicCarbonCNRatio",
            "ForestManagementRootToShoot",
            "SoilOrganicCarbon",
            "ForestTotalBiomass",
            "AfforestationLandUseStockExchangeFactor",
            "ForestManagementAGBGrowth",
            "BurningEmissionFactor",
            "FiresCombustionFactor",
            "CropNitrousEstimationDefaultFactor",
            "TillageCarbonStockExchangeFactor",
            "OrganicInputCarbonStockExchangeFactor",
            "CoastalAGB",
            "CoastalBGB",
            "CoastalLitter",
            "CoastalDeadwood",
            "RewettingCarbonFactor",
            "RewettingMethaneFactor",
            "OtherConstructedWaterbodiesEmissionFactor",
            "Atwood",
            "DefaultSoilCarbonStock",
            "DrainageEmissionFactor",
            "PerennialAGB",
            "PerennialBGB",
            "PerennialMaxAGB",
            "CroplandFLU",
            "CroplandFMG",
            "CroplandFI",
            "AfforestationFLU",
            "GrasslandBiomass",
            "GrasslandSOC",
            "GrasslandStockExchangeFactor",
            "ElectricityEmission",
            "LargeFisheryFUI",
            "SmallFisheryFUI",
            "CropYieldStat",
            "InputReference",
            "InputEmissionFactor",
            "BuildingEmissionFactor",
            "RoadEmissionFactor",
            "LivestockEntericEF",
            "LivestockManureEF",
            "LivestockTAM",
            "LivestockVSER",
            "LivestockAWMS",
            "LivestockNER",
            "MethaneEntericFermentationFactor",
            "ManureManagementVolatilizationMultiplier",
            "EnergyDefaultEmissionFactor",
            "IrrigationSystemData",
            "IrrigationPhaseData",
            "IrrigationPressureRequirement",
            "RiceDefaultEmissionFactor",
            "RiceSFO",
            "RiceSFP",
            "RiceSFW",
            "RiceYield",
            "TrophicStateFactor",
            "OrganicSoilDrainageEmissionFactor",
            "PeatExtractionEmissionFactor",
            "PeatExtractionConversionFactor",
            "OrganicSoilFuelConsumption",
            "OrganicSoilGefEmissionFactor",
            "OrganicSoilRewettingEmissionFactor",
            "ForestManagementAGB",
            "FMGData",
            "FIData",
            "FLUData",
            "SettlementEF",
            "NitrousEmissionFactor",
            "InputsNitrousEmissionFactor",
            "ValueChainPackagingEmissionFactor",
            "ValueChainRefrigerantEmissionFactor",
            "ShadowPriceOfCarbon",
            "FRACarbonStock",
            "TotalBiomassAfterDefo",
        ]

        # Get model classes in the specified order
        models = []
        for model_name in model_order:
            model_class = _resolve_model_class(model_name)
            if model_class is not None:
                models.append(model_class)

        return models

    def _generate_api_dependency_fixtures(self):
        """Generate fixtures for all API models that IPCC models depend on."""
        # Define API models that IPCC models depend on, in dependency order
        api_model_order = [
            # Core reference models with no dependencies
            "Moisture",
            "Climate",
            "Region",
            "SoilType",
            "ForestType",
            "LandUseType",
            "ModuleType",
            "GLEAMRegion",
            "ForestConditionType",
            "SiteLocationType",
            "VegetationType",
            "ActivityType",
            "StatusType",
            "SettlementType",
            "ChangeRate",
            "ProjectStatus",
            "DataSource",
            "ForestDegradationLevel",
            "FireType",
            "PeatType",
            "WaterbodyType",
            "TrophicType",
            "FisheryType",
            "FishType",
            "MacroFuelType",
            "FuelUseType",
            "Unit",
            "ParentFuelType",
            "FuelType",
            "SalinityType",
            "MacroInputType",
            "InputType",
            "EmissionFactorSource",
            "IrrigationSystemType",
            "EnergySourceType",
            "BuildingType",
            "RoadType",
            "RefrigerantType",
            "PackagingMaterialType",
            # Models that depend on other API models
            "IPCCRegion",  # Must come before Country
            "Country",  # Depends on IPCCRegion
            # Management type models (depend on core models)
            "TillageType",
            "TillageManagementType",
            "OrganicInputType",
            "ResidueManagementType",
            "WaterRegimeType",
            "PreSeasonWaterRegimeType",
            "OrganicAmendmentType",
            "WaterManagementTypeBeforeCultivation",
            "WaterManagementTypeAfterCultivation",
            "GrasslandManagementType",
            "LivestockCategoryType",
            "LivestockProductionType",
            "ManureManagementType",
            "LargeFisheryGearType",
            "SmallFisheryGearType",
        ]

        generated_files = []

        for model_name in api_model_order:
            try:
                # Import the API model dynamically
                from django.apps import apps

                api_app = apps.get_app_config("api")
                model_class = api_app.get_model(model_name)

                if model_class:
                    fixture_file = self._generate_fixture_for_api_model(model_class)
                    if fixture_file:
                        generated_files.append(fixture_file)
                else:
                    self.stdout.write(self.style.WARNING(f"API model {model_name} not found"))

            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error processing API model {model_name}: {e}"))

        return generated_files

    def _validate_api_dependencies(self):
        """Validate that all required API models have data before generating IPCC fixtures."""
        from django.apps import apps

        required_api_models = [
            "Climate",
            "Moisture",
            "Region",
            "Country",
            "SoilType",
            "LandUseType",
            "ForestType",
            "ModuleType",
            "TillageManagementType",
            "OrganicInputType",
            "GrasslandManagementType",
            "ManureManagementType",
            "WaterRegimeType",
            "IrrigationSystemType",
            "LivestockCategoryType",
            "LivestockProductionType",
            "IPCCRegion",
            "FuelType",
            "InputType",
            "BuildingType",
            "RoadType",
            "SalinityType",
            "WaterbodyType",
            "TrophicType",
            "FisheryType",
            "FishType",
            "LargeFisheryGearType",
            "SmallFisheryGearType",
            "PeatType",
            "FireType",
            "SiteLocationType",
            "OrganicAmendmentType",
            "WaterManagementTypeBeforeCultivation",
            "WaterManagementTypeAfterCultivation",
            "PackagingMaterialType",
            "RefrigerantType",
        ]

        missing_models = []
        empty_models = []

        try:
            api_app = apps.get_app_config("api")
            for model_name in required_api_models:
                try:
                    model_class = api_app.get_model(model_name)
                    if not model_class.objects.exists():
                        empty_models.append(model_name)
                except LookupError:
                    missing_models.append(model_name)
        except LookupError:
            self.stdout.write(self.style.ERROR("API app not found. Make sure the API app is properly configured."))
            return

        if missing_models:
            self.stdout.write(self.style.WARNING(f"Missing API models: {', '.join(missing_models)}"))

        if empty_models:
            self.stdout.write(self.style.WARNING(f"Empty API models (no data): {', '.join(empty_models)}"))

        if missing_models or empty_models:
            self.stdout.write(self.style.WARNING("Some API dependencies are missing or empty. IPCC fixtures may fail to import."))
            self.stdout.write(self.style.WARNING("Consider running with --include-dependencies to dump latest API data."))

    def _generate_fixture_for_api_model(self, model_class):
        """Generate fixture for a specific API model."""
        model_name = model_class.__name__

        try:
            # Get all instances of the model
            instances = model_class.objects.all()

            if not instances.exists():
                self.stdout.write(f"No data found for API model {model_name}, skipping...")
                return None

            # Serialize the data
            serialized_data = serializers.serialize(self.format, instances, indent=self.indent)

            # Create filename
            filename = f"{model_name.lower()}.{self.format}"
            filepath = os.path.join(self.api_output_dir, filename)

            if self.dry_run:
                self.stdout.write(f"Would generate API fixture: {filepath} ({instances.count()} records)")
                return filepath

            # Write to file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(serialized_data)

            self.stdout.write(f"Generated API fixture: {filepath} ({instances.count()} records)")
            return filepath

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing API model {model_name}: {e}"))
            return None

    def _get_specific_models(self, model_names):
        """Get specific models by name."""
        models = []
        for model_name in model_names:
            model_class = _resolve_model_class(model_name)
            if model_class is not None:
                models.append(model_class)
            else:
                self.stdout.write(self.style.WARNING(f"Model {model_name} not found in IPCC app"))
        return models

    def _generate_fixture_for_model(self, model_class):
        """Generate fixture for a specific model."""
        model_name = model_class.__name__

        try:
            # Get all instances of the model
            instances = model_class.objects.all()

            if not instances.exists():
                self.stdout.write(f"No data found for {model_name}, skipping...")
                return None

            # Serialize the data
            serialized_data = serializers.serialize(self.format, instances, indent=self.indent)

            # Create filename
            filename = f"{model_name.lower()}.{self.format}"
            filepath = os.path.join(self.output_dir, filename)

            if self.dry_run:
                self.stdout.write(f"Would generate: {filepath} ({instances.count()} records)")
                return filepath

            # Write to file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(serialized_data)

            self.stdout.write(f"Generated: {filepath} ({instances.count()} records)")
            return filepath

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing {model_name}: {e}"))
            return None

    def _generate_combined_fixture(self, fixture_files, output_dir, filename_prefix):
        """Generate a combined fixture file with all models."""
        combined_filename = f"{filename_prefix}.{self.format}"
        combined_filepath = os.path.join(output_dir, combined_filename)

        if self.dry_run:
            self.stdout.write(f"Would generate combined fixture: {combined_filepath}")
            return

        all_data = []

        for filepath in fixture_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    if self.format == "json":
                        data = json.load(f)
                        all_data.extend(data)
                    else:
                        # For other formats, we'd need to parse them appropriately
                        all_data.append(f.read())
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error reading {filepath}: {e}"))

        # Write combined file
        with open(combined_filepath, "w", encoding="utf-8") as f:
            if self.format == "json":
                json.dump(all_data, f, indent=self.indent, ensure_ascii=False)
            else:
                f.write("\n".join(all_data))

        self.stdout.write(f"Generated combined fixture: {combined_filepath}")

    def _get_model_dependencies(self, model_class):
        """Get foreign key dependencies for a model."""
        dependencies = []
        for field in model_class._meta.get_fields():
            if hasattr(field, "related_model") and field.related_model:
                if field.related_model._meta.app_label == "ipcc":
                    dependencies.append(field.related_model)
        return dependencies
