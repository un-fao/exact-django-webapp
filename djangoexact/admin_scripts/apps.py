import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AdminScriptsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "admin_scripts"

    def ready(self):
        import os

        # validate_catalog imports api.minitool, which runs DB queries at
        # module import. That fails during django.setup() before the test DB
        # exists. This startup catalog check is a dev/admin safety net, so it
        # is skipped under the SQLite test settings (unset elsewhere).
        if os.getenv("SKIP_STARTUP_CATALOG_VALIDATION", "").lower() in ("1", "true", "yes"):
            return

        from pathlib import Path
        from admin_scripts.catalog import load_catalog, validate_catalog, ValidationError

        catalog_path = Path(__file__).resolve().parent / "catalog" / "scenario_catalog.yaml"
        if not catalog_path.exists():
            logger.warning("Scenario catalog not found at %s", catalog_path)
            return

        try:
            modules = load_catalog(str(catalog_path))
            errors = validate_catalog(modules)
            if errors:
                for error in errors:
                    logger.warning("Catalog validation: %s", error)
        except ValidationError as e:
            logger.warning("Catalog load failed: %s", e)
