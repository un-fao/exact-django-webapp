import os
from django.core.management.base import BaseCommand
from .import_changes import Command as ImportChangesCommand


class Command(BaseCommand):
    help = "Import all change JSON files from data/changes (no subfolders)"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing data before importing")
        parser.add_argument("--no-progress", action="store_true", help="Disable progress output")

    def handle(self, *args, **options):
        show_progress = not options["no_progress"]
        clear_existing = options["clear"]

        importer = ImportChangesCommand()
        importer.stdout = self.stdout
        importer.stderr = self.stderr

        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        changes_dir = os.path.join(script_dir, "data", "changes")

        if not os.path.isdir(changes_dir):
            self.stdout.write(self.style.ERROR(f"Changes directory not found: {changes_dir}"))
            return

        files = [f for f in os.listdir(changes_dir) if f.endswith(".json") and os.path.isfile(os.path.join(changes_dir, f))]

        if not files:
            self.stdout.write(self.style.WARNING("No change files found to import"))
            return

        if clear_existing:
            if show_progress:
                self.stdout.write("Clearing all existing change data...")
            importer.fast_clear_all_data(show_progress)
            if show_progress:
                self.stdout.write("Existing data cleared")

        total_files = len(files)
        for idx, filename in enumerate(sorted(files), 1):
            file_path = os.path.join(changes_dir, filename)
            module_type = filename.replace("_changes.json", "")

            if show_progress:
                self.stdout.write(f"\nProcessing {filename} ({idx}/{total_files})")

            importer.import_single_module(
                file_path=file_path,
                module_type=module_type,
                clear_existing=False,
                aggregate_only=False,
                show_progress=show_progress,
            )
