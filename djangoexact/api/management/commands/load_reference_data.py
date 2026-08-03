"""Load reference/lookup fixtures in manifest order.

Replaces the scattered load_* / create_* / import_* commands with a single
entry point driven by `djangoexact/api/fixtures_manifest.py`.
"""

import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.fixtures_manifest import filter_manifest


class Command(BaseCommand):
    help = "Load reference data fixtures in dependency order."

    def add_arguments(self, parser):
        parser.add_argument("--app", default="all", choices=["api", "ipcc", "all"])
        parser.add_argument("--models", default=None, help="Comma-separated list of models to restrict to.")
        parser.add_argument("--clean-slate", action="store_true", help="Truncate reference tables in reverse manifest order first.")
        parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation for --clean-slate.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verify", action="store_true", help="After loading, run an in-process round-trip check against committed fixtures.")
        parser.add_argument("--continue-on-error", action="store_true")

    def handle(self, *args, **options):
        models_arg = options["models"]
        selected = filter_manifest(
            app=options["app"],
            models=[m.strip() for m in models_arg.split(",")] if models_arg else None,
        )
        if not selected:
            raise CommandError("No manifest entries matched the given filters.")

        # Pre-flight: every fixture file must exist.
        missing = []
        resolved = []
        for spec in selected:
            path = self._fixture_path(spec)
            if not path.exists():
                missing.append((spec, path))
            else:
                resolved.append((spec, path))

        if missing and not options["continue_on_error"]:
            lines = [f"  - {spec.model}: {path}" for spec, path in missing]
            raise CommandError("Missing fixture files:\n" + "\n".join(lines))
        for spec, path in missing:
            self.stderr.write(self.style.WARNING(f"missing (skipped): {spec.model} -> {path}"))

        if options["dry_run"]:
            for spec, path in resolved:
                self.stdout.write(f"[dry-run] would load {spec.model} <- {path}")
            return

        if options["clean_slate"]:
            self._clean_slate(selected, assume_yes=options["yes"], continue_on_error=options["continue_on_error"])

        failures = []
        for spec, path in resolved:
            try:
                call_command("loaddata", str(path), verbosity=0)
                self.stdout.write(self.style.SUCCESS(f"loaded {spec.model}"))
            except Exception as exc:
                msg = f"{spec.model}: {exc}"
                failures.append(msg)
                self.stderr.write(self.style.ERROR(f"failed: {msg}"))
                if not options["continue_on_error"]:
                    raise CommandError(f"load_reference_data aborted on {spec.model}") from exc

        if failures and options["continue_on_error"]:
            self.stderr.write(self.style.WARNING(f"completed with {len(failures)} failure(s)"))

        if options["verify"]:
            self._verify(resolved)

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(resolved) - len(failures)} fixtures."))

    # --- helpers -----------------------------------------------------------
    def _fixture_path(self, spec):
        base = Path(settings.BASE_DIR) if hasattr(settings, "BASE_DIR") else Path(os.getcwd())
        return base / spec.app / "fixtures" / spec.fixture_file

    def _clean_slate(self, selected, assume_yes, continue_on_error):
        if not assume_yes:
            self.stdout.write(self.style.WARNING("--clean-slate will DELETE all rows in every manifest model."))
            resp = input("Proceed? (type 'yes' to continue): ")
            if resp.strip().lower() != "yes":
                raise CommandError("Aborted by user.")

        with transaction.atomic():
            for spec in reversed(selected):
                try:
                    model = apps.get_model(spec.model)
                except LookupError as exc:
                    if continue_on_error:
                        self.stderr.write(self.style.WARNING(f"skip clean {spec.model}: {exc}"))
                        continue
                    raise
                deleted, _ = model.objects.all().delete()
                if deleted:
                    self.stdout.write(f"cleaned {spec.model} ({deleted} rows)")

    def _verify(self, resolved):
        import json as _json
        from django.core import serializers as _s

        drift = []
        for spec, path in resolved:
            try:
                model = apps.get_model(spec.model)
            except LookupError:
                continue
            qs = model.objects.all().order_by(*spec.order_by)
            regenerated = _json.loads(_s.serialize("json", qs, indent=2, use_natural_primary_keys=False))
            with open(path, "r", encoding="utf-8") as fh:
                committed = _json.load(fh)
            if regenerated != committed:
                drift.append(spec.model)

        if drift:
            raise CommandError(f"Round-trip verification failed for: {', '.join(drift)}")
        self.stdout.write(self.style.SUCCESS("Round-trip verification passed."))
