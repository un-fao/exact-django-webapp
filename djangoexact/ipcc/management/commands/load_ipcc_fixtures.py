#!/usr/bin/env python3
"""
Django management command to load IPCC fixtures in the correct dependency order.

This script methodically loads fixtures for all IPCC models and their API dependencies
in the correct order to handle foreign key constraints. It provides comprehensive
error handling and validation.

Usage:
    python manage.py load_ipcc_fixtures
    python manage.py load_ipcc_fixtures --include-dependencies
    python manage.py load_ipcc_fixtures --fixtures-dir /path/to/fixtures
    python manage.py load_ipcc_fixtures --models GlobalWarmingPotential,SoilOrganicCarbon
    python manage.py load_ipcc_fixtures --dry-run
"""

import os
import json
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction
from django.apps import apps


class Command(BaseCommand):
    help = "Load IPCC fixtures in dependency order with comprehensive validation"

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-dependencies",
            action="store_true",
            help="Also load API dependency fixtures before IPCC fixtures",
        )
        parser.add_argument(
            "--fixtures-dir",
            type=str,
            default="ipcc/fixtures",
            help="Directory containing IPCC fixture files (default: ipcc/fixtures)",
        )
        parser.add_argument(
            "--api-fixtures-dir",
            type=str,
            default="api/fixtures",
            help="Directory containing API fixture files (default: api/fixtures)",
        )
        parser.add_argument(
            "--models",
            type=str,
            help="Comma-separated list of specific IPCC models to load fixtures for",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be loaded without actually loading fixtures",
        )
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            help="Skip pre-load validation checks",
        )
        parser.add_argument(
            "--continue-on-error",
            action="store_true",
            help="Continue loading other fixtures if one fails",
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=["json", "xml", "yaml"],
            default="json",
            help="Expected fixture format (default: json)",
        )
        parser.add_argument(
            "--force-individual",
            action="store_true",
            help="Force loading individual fixtures even if combined fixtures exist",
        )
        parser.add_argument(
            "--clean-slate",
            action="store_true",
            help="Delete all existing data from models before loading fixtures",
        )

    def handle(self, *args, **options):
        self.fixtures_dir = options["fixtures_dir"]
        self.api_fixtures_dir = options["api_fixtures_dir"]
        self.include_dependencies = options["include_dependencies"]
        self.dry_run = options["dry_run"]
        self.skip_validation = options["skip_validation"]
        self.continue_on_error = options["continue_on_error"]
        self.format = options["format"]
        self.force_individual = options["force_individual"]
        self.clean_slate = options["clean_slate"]

        self.stdout.write("IPCC Fixture Loading Command")
        self.stdout.write("=" * 50)

        # Validate directories exist
        if not self._validate_directories():
            return

        # Clean slate: delete existing data if requested
        if self.clean_slate:
            self.stdout.write("Cleaning existing data...")
            if not self._clean_existing_data():
                if not self.continue_on_error:
                    return

        # Load API dependencies first if requested
        if self.include_dependencies:
            self.stdout.write("Loading API dependency fixtures...")
            if not self._load_api_dependencies():
                if not self.continue_on_error:
                    return

        # Pre-load validation (after API dependencies are loaded if requested)
        if not self.skip_validation:
            if not self._validate_dependencies():
                return

        # Load IPCC fixtures
        self.stdout.write("Loading IPCC fixtures...")
        if not self._load_ipcc_fixtures(options.get("models")):
            if not self.continue_on_error:
                return

        self.stdout.write(self.style.SUCCESS("IPCC fixture loading completed successfully!"))

    def _validate_directories(self):
        """Validate that fixture directories exist."""
        if not os.path.exists(self.fixtures_dir):
            self.stdout.write(self.style.ERROR(f"IPCC fixtures directory not found: {self.fixtures_dir}"))
            return False

        if self.include_dependencies and not os.path.exists(self.api_fixtures_dir):
            self.stdout.write(self.style.ERROR(f"API fixtures directory not found: {self.api_fixtures_dir}"))
            return False

        return True

    def _clean_existing_data(self):
        """Delete all existing data from models that will be loaded."""
        from django.apps import apps
        from django.db import transaction

        if self.dry_run:
            self.stdout.write("Would clean existing data from all IPCC and API models")
            return True

        try:
            with transaction.atomic():
                # Get all IPCC models
                ipcc_app = apps.get_app_config("ipcc")
                ipcc_models = [model for model in ipcc_app.get_models()]

                # Get all API models that IPCC depends on
                api_app = apps.get_app_config("api")
                api_models = [model for model in api_app.get_models()]

                # Delete IPCC models first (they depend on API models)
                ipcc_deleted = 0
                for model in ipcc_models:
                    count = model.objects.count()
                    if count > 0:
                        model.objects.all().delete()
                        ipcc_deleted += count
                        self.stdout.write(f"Deleted {count} records from {model.__name__}")

                # Delete API models in reverse dependency order
                # Start with models that other models depend on
                api_deletion_order = [
                    # Management types first (others depend on them)
                    "TillageManagementType",
                    "OrganicInputType",
                    "GrasslandManagementType",
                    "ManureManagementType",
                    "WaterRegimeType",
                    "IrrigationSystemType",
                    "LivestockCategoryType",
                    "LivestockProductionType",
                    "LargeFisheryGearType",
                    "SmallFisheryGearType",
                    "OrganicAmendmentType",
                    "WaterManagementTypeBeforeCultivation",
                    "WaterManagementTypeAfterCultivation",
                    # Models that depend on other API models (delete dependent first)
                    "Country",  # Depends on IPCCRegion
                    "IPCCRegion",  # Must come after Country
                    # Then specialized types
                    "RefrigerantType",
                    "PackagingMaterialType",
                    "BuildingType",
                    "RoadType",
                    "InputType",
                    "EmissionFactorSource",
                    "EnergySourceType",
                    "SalinityType",
                    "WaterbodyType",
                    "TrophicType",
                    "FisheryType",
                    "FishType",
                    "PeatType",
                    "FireType",
                    "SiteLocationType",
                    "ForestDegradationLevel",
                    "DataSource",
                    "ProjectStatus",
                    "ChangeRate",
                    "SettlementType",
                    "StatusType",
                    "ActivityType",
                    "VegetationType",
                    "ForestConditionType",
                    "GLEAMRegion",
                    # Then core reference models
                    "FuelType",
                    "ParentFuelType",
                    "Unit",
                    "FuelUseType",
                    "MacroFuelType",
                    "MacroInputType",
                    "LandUseType",  # Depends on ForestType
                    "ForestType",  # Must come after LandUseType
                    "ModuleType",
                    "SoilType",
                    "Region",
                    "Climate",
                    "Moisture",
                ]

                api_deleted = 0
                deleted_models = set()

                # Delete in specified order
                for model_name in api_deletion_order:
                    try:
                        model = api_app.get_model(model_name)
                        if model not in deleted_models:
                            count = model.objects.count()
                            if count > 0:
                                model.objects.all().delete()
                                api_deleted += count
                                self.stdout.write(f"Deleted {count} records from {model_name}")
                            deleted_models.add(model)
                    except LookupError:
                        # Model doesn't exist, skip
                        continue

                # Delete any remaining API models not in the ordered list
                for model in api_models:
                    if model not in deleted_models:
                        count = model.objects.count()
                        if count > 0:
                            model.objects.all().delete()
                            api_deleted += count
                            self.stdout.write(f"Deleted {count} records from {model.__name__}")

                self.stdout.write(self.style.SUCCESS(f"Clean slate completed: {ipcc_deleted} IPCC records, {api_deleted} API records deleted"))
                return True

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during clean slate operation: {e}"))
            return False

    def _validate_dependencies(self):
        """Validate that required API models exist before loading IPCC fixtures."""
        from django.apps import apps

        # Skip validation in dry-run mode since we can't connect to database
        if self.dry_run:
            self.stdout.write("Skipping dependency validation in dry-run mode")
            return True

        required_api_models = [
            "Moisture",
            "Climate",
            "Region",
            "SoilType",
            "ModuleType",
            "ForestType",
            "LandUseType",
            "GLEAMRegion",
            "ForestConditionType",
            "SiteLocationType",
            "VegetationType",
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
            "BuildingType",
            "RoadType",
            "RefrigerantType",
            "PackagingMaterialType",
            "IPCCRegion",
            "Country",
            "TillageType",
            "TillageManagementType",
            "OrganicInputType",
            "ResidueManagementType",
            "WaterRegimeType",
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
            return False

        if missing_models:
            self.stdout.write(self.style.WARNING(f"Missing API models: {', '.join(missing_models)}"))

        if empty_models:
            self.stdout.write(self.style.WARNING(f"Empty API models (no data): {', '.join(empty_models)}"))

        if missing_models or empty_models:
            self.stdout.write(self.style.WARNING("Some API dependencies are missing or empty. IPCC fixtures may fail to load."))

            # Only suggest --include-dependencies if it wasn't already used
            if not self.include_dependencies:
                self.stdout.write(self.style.WARNING("Consider using --include-dependencies to load API fixtures first."))
            else:
                self.stdout.write(self.style.WARNING("API dependencies were loaded but some models are still missing or empty."))

            if not self.continue_on_error:
                response = input("Continue anyway? (y/N): ")
                if response.lower() != "y":
                    return False

        return True

    def _load_api_dependencies(self):
        """Load API dependency fixtures in the correct order."""
        # Check if API fixtures directory has any files
        if not os.path.exists(self.api_fixtures_dir):
            self.stdout.write(self.style.ERROR(f"API fixtures directory not found: {self.api_fixtures_dir}"))
            return False

        api_files = [f for f in os.listdir(self.api_fixtures_dir) if f.endswith(f".{self.format}")]
        if not api_files:
            self.stdout.write(self.style.WARNING(f"No {self.format} fixture files found in {self.api_fixtures_dir}"))
            return False

        self.stdout.write(f"Found {len(api_files)} API fixture files")

        api_fixture_order = [
            # Core reference models with no dependencies
            "moisture",
            "climate",
            "region",
            "soiltype",
            "moduletype",
            "foresttype",
            "landusetype",
            "gleamregion",  # Must come before country
            "forestconditiontype",
            "sitelocationtype",
            "vegetationtype",
            "statustype",
            "settlementtype",
            "changerate",
            "projectstatus",
            "datasource",
            "forestdegradationlevel",
            "firetype",
            "peattype",
            "waterbodytype",
            "trophictype",
            "fisherytype",
            "fishtype",
            # Fuel-related models in dependency order
            "macrofueltype",  # Must come before fueltype
            "fuelusetype",  # Must come before fueltype
            "unit",  # Must come before fueltype
            "parentfueltype",  # Must come before fueltype
            "fueltype",  # Depends on above models
            "salinitytype",
            # Input-related models in dependency order
            "macroinputtype",  # Must come before inputtype
            "inputtype",  # Depends on macroinputtype
            "emissionfactorsource",
            "irrigationsystemtype",
            "buildingtype",
            "roadtype",
            "refrigeranttype",
            "packagingmaterialtype",
            # Models that depend on other API models
            "ipccregion",  # Must come before country
            "country",  # Depends on ipccregion AND gleamregion
            # Management type models (depend on core models)
            "tillagetype",
            "tillagemanagementtype",
            "organicinputtype",
            "residuemanagementtype",
            "waterregimetype",
            "organicamendmenttype",
            "watermanagementtypebeforecultivation",
            "watermanagementtypeaftercultivation",
            "grasslandmanagementtype",
            "livestockcategorytype",
            "livestockproductiontype",
            "manuremanagementtype",
            "largefisherygeartype",
            "smallfisherygeartype",
        ]

        # Check for combined API fixture first (unless forced to use individual)
        combined_api_fixture = os.path.join(self.api_fixtures_dir, f"all_api_dependencies.{self.format}")
        if os.path.exists(combined_api_fixture) and not self.force_individual:
            self.stdout.write("Using combined API dependencies fixture")
            return self._load_fixture_file(combined_api_fixture, "All API dependencies")
        else:
            if self.force_individual:
                self.stdout.write("Force individual loading enabled, loading individual files")
            else:
                self.stdout.write("Combined API dependencies fixture not found, loading individual files")

        # Load individual API fixtures
        success_count = 0
        total_count = len(api_fixture_order)

        for fixture_name in api_fixture_order:
            fixture_file = os.path.join(self.api_fixtures_dir, f"{fixture_name}.{self.format}")
            if os.path.exists(fixture_file):
                if self._load_fixture_file(fixture_file, f"API {fixture_name}"):
                    success_count += 1
                else:
                    # Check if it's due to missing dependencies (not a fatal error)
                    # Only return False if continue_on_error is False and it's not a dependency issue
                    if not self.continue_on_error:
                        # For now, continue loading other fixtures even if some fail due to dependencies
                        pass
            else:
                self.stdout.write(self.style.WARNING(f"API fixture not found: {fixture_file}"))

        self.stdout.write(f"Loaded {success_count}/{total_count} API fixtures")
        return success_count > 0

    def _load_ipcc_fixtures(self, specific_models=None):
        """Load IPCC fixtures in dependency order."""
        if specific_models:
            model_names = [name.strip() for name in specific_models.split(",")]
            return self._load_specific_ipcc_models(model_names)

        # Check for combined IPCC fixture first (unless forced to use individual)
        combined_ipcc_fixture = os.path.join(self.fixtures_dir, f"all_ipcc_fixtures.{self.format}")
        if os.path.exists(combined_ipcc_fixture) and not self.force_individual:
            self.stdout.write("Using combined IPCC fixtures")
            return self._load_fixture_file(combined_ipcc_fixture, "All IPCC fixtures")
        else:
            if self.force_individual:
                self.stdout.write("Force individual loading enabled, loading individual IPCC files")
            else:
                self.stdout.write("Combined IPCC fixtures not found, loading individual files")

        # Load individual IPCC fixtures in dependency order
        ipcc_fixture_order = [
            # Models with no foreign key dependencies to other IPCC models
            "globalwarmingpotential",
            "emissionfactorcategory",
            "emissiontype",
            # Models that depend on API models only (no IPCC dependencies)
            "dataonmangrove",
            "forestcombustionfactor",
            "afforestationcombustionfactor",
            "litterdeadwoodcarbonstock",
            "landusecarbonstockexchangefactor",
            "soilorcaniccarboncnratio",
            "forestmanagementbgb",
            "soilorganiccarbon",
            "foresttotalbiomass",
            "afforestationlandusestockexchangefactor",
            "forestmanagementagbgrowth",
            "burningemissionfactor",
            "firescombustionfactor",
            "cropnitrousestimationdefaultfactor",
            "tillagecarbonstockexchangefactor",
            "organicinputcarbonstockexchangefactor",
            "coastalagb",
            "coastalbgb",
            "coastallitter",
            "coastaldeadwood",
            "rewettingcarbonfactor",
            "rewettingmethanefactor",
            "otherconstructedwaterbodiesemissionfactor",
            "atwood",
            "defaultsoilcarbonstock",
            "drainageemissionfactor",
            "perennialagb",
            "perennialbgb",
            "perennialmaxagb",
            "croplandflu",
            "croplandfmg",
            "croplandfi",
            "afforestationflu",
            "grasslandbiomass",
            "grasslandsoc",
            "grasslandstockexchangefactor",
            "electricityemission",
            "largefisheryfui",
            "smallfisheryfui",
            "cropyieldstat",
            "inputreference",
            "inputemissionfactor",
            "buildingemissionfactor",
            "roademissionfactor",
            "livestockentericef",
            "livestockmanureef",
            "livestocktam",
            "livestockvser",
            "livestockawms",
            "livestockner",
            "methaneentericfermentationfactor",
            "manuremanagementvolatilizationmultiplier",
            "energydefaultemissionfactor",
            "irrigationsystemdata",
            "irrigationphasedata",
            "irrigationpressurerequirement",
            "ricedefaultemissionfactor",
            "ricesfo",
            "ricesfp",
            "ricesfw",
            "riceyield",
            "trophicstatefactor",
            "organicsoildrainageemissionfactor",
            "peatextractionemissionfactor",
            "peatextractionconversionfactor",
            "organicsoilfuelconsumption",
            "organicsoilgefemissionfactor",
            "organicsoilrewettingemissionfactor",
            "forestmanagementagb",
            "fmgdata",
            "fidata",
            "fludata",
            "settlementef",
            "nitrousemissionfactor",
            "inputsnitrousemissionfactor",
            "valuechainpackagingemissionfactor",
            "valuechainrefrigerantemissionfactor",
            "shadowpriceofcarbon",
            "fracarbonstock",
            "totalbiomassafterdefo",
        ]

        success_count = 0
        total_count = len(ipcc_fixture_order)

        for fixture_name in ipcc_fixture_order:
            fixture_file = os.path.join(self.fixtures_dir, f"{fixture_name}.{self.format}")
            if os.path.exists(fixture_file):
                if self._load_fixture_file(fixture_file, f"IPCC {fixture_name}"):
                    success_count += 1
                elif not self.continue_on_error:
                    return False
            else:
                self.stdout.write(self.style.WARNING(f"IPCC fixture not found: {fixture_file}"))

        self.stdout.write(f"Loaded {success_count}/{total_count} IPCC fixtures")
        return success_count > 0

    def _load_specific_ipcc_models(self, model_names):
        """Load fixtures for specific IPCC models."""
        success_count = 0
        total_count = len(model_names)

        for model_name in model_names:
            fixture_name = model_name.lower()
            fixture_file = os.path.join(self.fixtures_dir, f"{fixture_name}.{self.format}")

            if os.path.exists(fixture_file):
                if self._load_fixture_file(fixture_file, f"IPCC {model_name}"):
                    success_count += 1
                elif not self.continue_on_error:
                    return False
            else:
                self.stdout.write(self.style.ERROR(f"Fixture not found for model {model_name}: {fixture_file}"))

        self.stdout.write(f"Loaded {success_count}/{total_count} specified IPCC fixtures")
        return success_count == total_count

    def _load_fixture_file(self, fixture_path, description):
        """Load a single fixture file."""
        if self.dry_run:
            self.stdout.write(f"Would load: {fixture_path} ({description})")
            return True

        try:
            self.stdout.write(f"Loading: {description}...")

            # Use Django's loaddata command
            call_command("loaddata", fixture_path, verbosity=0)

            self.stdout.write(self.style.SUCCESS(f"✓ Loaded: {description}"))
            return True

        except Exception as e:
            error_msg = str(e)
            self.stdout.write(self.style.ERROR(f"✗ Failed to load {description}: {e}"))

            # Check if it's a foreign key constraint error due to missing dependencies
            if "matching query does not exist" in error_msg:
                self.stdout.write(self.style.WARNING(f"Skipping {description} due to missing dependencies"))
                return False  # Return False but don't treat as fatal error

            return False

    def _get_fixture_info(self, fixture_path):
        """Get information about a fixture file."""
        try:
            with open(fixture_path, "r", encoding="utf-8") as f:
                if self.format == "json":
                    data = json.load(f)
                    return len(data)
                else:
                    # For other formats, we'd need to parse them appropriately
                    return "unknown"
        except Exception:
            return "error"
