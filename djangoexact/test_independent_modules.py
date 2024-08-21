import os
import sys
import django
from django.core.management import call_command
import logging as log

log.basicConfig(level=log.INFO)

# Set up the Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
django.setup()

# Run the tests
if __name__ == "__main__":
    log.info("========================================\n\n")
    log.info("Running tests\n\n")
    log.info("========================================\n\n")
    # Get all filenames in the api.tests directory
    test_labels = [f"api.tests.modules.{filename[:-3]}" for filename in os.listdir("api/tests/modules") if filename.endswith(".py") and filename != "__init__.py"]

    for test_label in test_labels:
        log.info("========================================\n\n")
        log.info(f"Running test {test_label}\n\n")
        log.info("========================================\n\n")
        call_command("test", test_label)
        log.info("========================================\n\n")
        log.info(f"Finished test {test_label}\n\n")
        log.info("========================================\n\n")
