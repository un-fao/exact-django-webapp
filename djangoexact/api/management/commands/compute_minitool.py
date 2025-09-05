"""
Django management command for computing minitool permutations
Converts the minitool.py script into a proper Django management command
"""

from django.core.management.base import BaseCommand, CommandError
import os
import logging

# Import the minitool components
from api.minitool import ModuleDataBuilderRegistry, ProcessorRegistry, DataManager, PermutationComputer, ConfigurationLoader, MODULE_CONFIGS
import api.models as models

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Compute minitool permutations for specified modules"

    def add_arguments(self, parser):
        # Module selection
        parser.add_argument("--modules", type=str, help='Comma-separated list of modules to process (e.g., "grassland,livestock,annual_cropland")', default="")

        # Individual module flags
        parser.add_argument("--annual-cropland", action="store_true", help="Process Annual Cropland module")
        parser.add_argument("--flooded-rice", action="store_true", help="Process Flooded Rice module")
        parser.add_argument("--grassland", action="store_true", help="Process Grassland module")
        parser.add_argument("--livestock", action="store_true", help="Process Livestock module")
        parser.add_argument("--perennial-cropland", action="store_true", help="Process Perennial Cropland module")
        parser.add_argument("--forest-management", action="store_true", help="Process Forest Management module")
        parser.add_argument("--small-fishery", action="store_true", help="Process Small Fishery module")
        parser.add_argument("--large-fishery", action="store_true", help="Process Large Fishery module")
        parser.add_argument("--coastal-wetland", action="store_true", help="Process Coastal Wetland module")
        parser.add_argument("--waterbody", action="store_true", help="Process Waterbody module")

        # Performance settings
        parser.add_argument("--max-rows", type=int, help="Maximum number of rows to process per module", default=10000)
        parser.add_argument("--max-workers", type=int, help="Maximum number of worker processes", default=None)
        parser.add_argument("--chunk-size", type=int, help="Chunk size for processing batches", default=10000)

        # Configuration options
        parser.add_argument("--config", type=str, help="Path to configuration file", default="minitool_config.yml")
        parser.add_argument("--local-config", action="store_true", help="Use local configuration file instead of GCP storage")
        parser.add_argument("--bucket", type=str, help="GCP storage bucket name", default=None)

        # Output options
        parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without actually processing")

    def handle(self, *args, **options):
        """Main command handler"""
        self.options = options

        # Configure logging
        if options["verbose"]:
            logging.basicConfig(level=logging.INFO)
            logger.setLevel(logging.INFO)
        else:
            logging.basicConfig(level=logging.WARNING)
            logger.setLevel(logging.WARNING)

        try:
            # Initialize components first to access Django models
            self._initialize_components(options)

            # Load configuration
            config = self._load_configuration(options)

            # Determine which modules to process (might use config if none explicitly provided)
            modules_to_process = self._determine_modules_to_process(options, config)

            if not modules_to_process:
                self.stdout.write(self.style.WARNING("No modules selected for processing. Use --modules, individual module flags, or enable modules in configuration file."))
                return

            if options["dry_run"]:
                self._show_dry_run(modules_to_process, options)
                return

            # Process modules
            self._process_modules(modules_to_process, config, options)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nKeyboard interrupt detected! Command terminated by user."))
            return
        except Exception as e:
            raise CommandError(f"Error during processing: {str(e)}")

    def _determine_modules_to_process(self, options, config=None):
        """Determine which modules to process based on command line arguments or configuration"""
        modules = set()

        # Check individual module flags
        module_flags = {
            "annual_cropland": options["annual_cropland"],
            "flooded_rice": options["flooded_rice"],
            "grassland": options["grassland"],
            "livestock": options["livestock"],
            "perennial_cropland": options["perennial_cropland"],
            "forest_management": options["forest_management"],
            "small_fishery": options["small_fishery"],
            "large_fishery": options["large_fishery"],
            "coastal_wetland": options["coastal_wetland"],
            "waterbody": options["waterbody"],
        }

        for module_name, enabled in module_flags.items():
            if enabled:
                modules.add(module_name)

        # Check --modules argument
        if options["modules"]:
            specified_modules = [m.strip() for m in options["modules"].split(",")]
            modules.update(specified_modules)

        # If no modules were explicitly specified, use configuration file
        if not modules and config:
            for module_name, enabled in config["modules"].items():
                if enabled:
                    modules.add(module_name)

        return list(modules)

    def _show_dry_run(self, modules_to_process, options):
        """Show what would be processed in dry run mode"""
        self.stdout.write(self.style.SUCCESS("DRY RUN - No actual processing will occur"))
        self.stdout.write(f"Modules to process: {', '.join(modules_to_process)}")
        self.stdout.write(f"Max rows per module: {options['max_rows']}")
        self.stdout.write(f"Max workers: {options['max_workers'] or 'auto'}")
        self.stdout.write(f"Chunk size: {options['chunk_size']}")
        self.stdout.write(f"Configuration: {options['config']}")
        self.stdout.write(f"Local config: {options['local_config']}")

        if options["bucket"]:
            self.stdout.write(f"Storage bucket: {options['bucket']}")

    def _initialize_components(self, options):
        """Initialize the minitool components"""
        self.stdout.write("Initializing minitool components...")

        # Set storage bucket if provided
        if options["bucket"]:
            os.environ["STORAGE_BUCKET"] = options["bucket"]

        # Initialize registries
        self.data_builder_registry = ModuleDataBuilderRegistry()
        self.processor_registry = ProcessorRegistry(self.data_builder_registry)
        self.data_manager = DataManager()
        self.permutation_computer = PermutationComputer(self.processor_registry)

        self.stdout.write(self.style.SUCCESS("Components initialized successfully"))

    def _load_configuration(self, options):
        """Load configuration from file or GCP storage"""
        self.stdout.write("Loading configuration...")

        config_loader = ConfigurationLoader()
        config = config_loader.load_config(config_name=options["config"], local=options["local_config"])

        # Override with command line options
        config["performance"]["max_rows"] = options["max_rows"]
        config["performance"]["max_workers"] = options["max_workers"]
        config["performance"]["chunk_size"] = options["chunk_size"]

        self.stdout.write(self.style.SUCCESS("Configuration loaded successfully"))

        return config

    def _process_modules(self, modules_to_process, config, options):
        """Process the specified modules"""
        self.stdout.write(f"Processing {len(modules_to_process)} modules...")

        # Extract configuration
        CONFIG = {**config["modules"], **config["performance"]}

        total_processed = 0
        total_errors = 0

        for module_name in modules_to_process:
            # Find the module configuration
            module_config = None
            for config_name, module_config_data in MODULE_CONFIGS.items():
                if module_config_data.get("config_name") == module_name:
                    module_config = module_config_data
                    break

            if not module_config:
                self.stdout.write(self.style.WARNING(f"Module configuration not found for: {module_name}"))
                continue

            # If modules were explicitly requested via command line, process them regardless of config
            # Otherwise, only process modules that are enabled in configuration file
            module_explicitly_requested = len(modules_to_process) > 0
            if not module_explicitly_requested and not CONFIG.get(module_name, False):
                self.stdout.write(self.style.WARNING(f"Module {module_name} is disabled in configuration"))
                continue

            self.stdout.write(f"Processing {module_name}...")

            try:
                # Get the model class
                model_class = getattr(models, config_name)

                # Compute permutations
                data, errors = self.permutation_computer.compute_permutations(
                    module_config["fields"], model_class, chunk_size=CONFIG["chunk_size"], stop_at=CONFIG["max_rows"], max_workers=CONFIG["max_workers"]
                )

                # Save results
                if data or errors:
                    self.data_manager.save_data(data, errors, config_name)

                    self.stdout.write(self.style.SUCCESS(f"Completed {config_name}: {len(data)} successful, {len(errors)} errors"))

                    total_processed += len(data)
                    total_errors += len(errors)
                else:
                    self.stdout.write(self.style.WARNING(f"No data generated for {config_name}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {module_name}: {str(e)}"))
                continue

        # Summary
        self.stdout.write(self.style.SUCCESS(f"\nProcessing complete! Total: {total_processed} successful, {total_errors} errors"))
