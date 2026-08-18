"""Verify that reference primary keys mean the same row here as in the fixtures.

`.exactproject` v1 encodes every reference relation as a raw integer primary key
and resolves nothing on import, so an installation whose reference data was not
built from the committed fixtures silently mis-resolves those relations. This
command proves, per manifest model, that primary key N carries the same identity
in this database as the committed fixture assigns to it.

Exit code 1 when any model reports semantic drift (a shared pk whose identity
differs). Rows present on only one side are reported as warnings, mirroring the
dump guardrail semantics in docs/guides/fixtures-guide.md.

    python manage.py verify_reference_parity --app=all
    python manage.py verify_reference_parity --app=ipcc --json
"""

import json
import os
import sys
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.fixtures_manifest import filter_manifest
from api.reference_parity import diff_reference_identity

# order_by components that name the primary key rather than a stored field.
_PK_ALIASES = ("id", "pk")


class Command(BaseCommand):
    help = "Compare reference-data identity in the database against the committed fixtures."

    def add_arguments(self, parser):
        parser.add_argument("--app", default="all", choices=["api", "ipcc", "all"])
        parser.add_argument("--models", default=None, help="Comma-separated list of models to restrict to.")
        parser.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON.")

    def handle(self, *args, **options):
        models_arg = options["models"]
        selected = filter_manifest(
            app=options["app"],
            models=[m.strip() for m in models_arg.split(",")] if models_arg else None,
        )
        if not selected:
            raise CommandError("No manifest entries matched the given filters.")

        results = []
        skipped = []
        for spec in selected:
            try:
                model = apps.get_model(spec.model)
            except LookupError as exc:
                skipped.append(f"{spec.model}: {exc}")
                continue

            path = self._fixture_path(spec)
            if not path.exists():
                skipped.append(f"{spec.model}: missing fixture {path}")
                continue

            identity_fields = self._identity_fields(model, spec)
            fixture_rows = self._fixture_rows(path, identity_fields)
            db_rows = self._db_rows(model, identity_fields)
            results.append(diff_reference_identity(fixture_rows, db_rows, model=spec.model))

        fatal = [d for d in results if d.is_fatal]

        if options["as_json"]:
            self.stdout.write(json.dumps(
                {
                    "models": [d.as_dict() for d in results],
                    "skipped": skipped,
                    "fatal_models": [d.model for d in fatal],
                },
                indent=2,
            ))
        else:
            self._report(results, skipped, fatal)

        if fatal:
            sys.exit(1)

    # --- helpers -----------------------------------------------------------
    def _fixture_path(self, spec):
        """Resolve the fixture exactly as load_reference_data does."""
        base = Path(settings.BASE_DIR) if hasattr(settings, "BASE_DIR") else Path(os.getcwd())
        return base / spec.app / "fixtures" / spec.fixture_file

    def _identity_fields(self, model, spec):
        """Use the manifest order_by as the identity, enriched with `name`.

        `order_by` is already required to be a deterministic per-model identity
        by the manifest contract. Most ipcc entries order by `("id",)` alone,
        which would compare a pk against itself and detect nothing, so append the
        `name` column when the model has one. This is the base (untranslated)
        column, matching what the fixture stores.
        """
        fields = tuple(spec.order_by)
        if all(f in _PK_ALIASES for f in fields):
            concrete = {f.name for f in model._meta.concrete_fields}
            if "name" in concrete:
                fields = fields + ("name",)
        return fields

    def _fixture_rows(self, path, identity_fields):
        with open(path, "r", encoding="utf-8") as fh:
            entries = json.load(fh)

        rows = {}
        for entry in entries:
            pk = entry.get("pk")
            fields = entry.get("fields", {})
            rows[pk] = tuple(self._fixture_value(pk, fields, name) for name in identity_fields)
        return rows

    @staticmethod
    def _fixture_value(pk, fields, name):
        """Read one identity component out of a serialized fixture entry.

        Django's serializer writes the pk outside `fields` and writes FK columns
        under the relation name, so `module_type_id` in the manifest is stored as
        `module_type` in the fixture and already holds the integer pk.
        """
        if name in _PK_ALIASES:
            return pk
        if name in fields:
            return fields[name]
        if name.endswith("_id") and name[:-3] in fields:
            return fields[name[:-3]]
        return None

    @staticmethod
    def _db_rows(model, identity_fields):
        queryset = model.objects.all()
        # modeltranslation's MultilingualQuerySet rewrites `name` to the active
        # language column by default. Turn that off so the comparison reads the
        # same base column the fixture stores.
        if hasattr(queryset, "rewrite"):
            queryset = queryset.rewrite(False)
        return {
            row[0]: tuple(row[1:])
            for row in queryset.values_list("pk", *identity_fields)
        }

    def _report(self, results, skipped, fatal):
        for diff in results:
            if diff.is_clean:
                self.stdout.write(self.style.SUCCESS(f"ok       {diff.model}"))
                continue
            if diff.changed:
                self.stdout.write(self.style.ERROR(
                    f"DRIFT    {diff.model}: {len(diff.changed)} pk(s) map to a different row"
                ))
                for pk, fixture_identity, db_identity in diff.changed[:20]:
                    self.stdout.write(f"           pk={pk} fixture={fixture_identity} db={db_identity}")
                if len(diff.changed) > 20:
                    self.stdout.write(f"           ... and {len(diff.changed) - 20} more")
            if diff.missing_in_db or diff.extra_in_db:
                self.stdout.write(self.style.WARNING(
                    f"warn     {diff.model}: {len(diff.missing_in_db)} pk(s) missing in db, "
                    f"{len(diff.extra_in_db)} extra in db"
                ))

        for line in skipped:
            self.stdout.write(self.style.WARNING(f"skipped  {line}"))

        if fatal:
            self.stdout.write(self.style.ERROR(
                f"\n{len(fatal)} model(s) have reference-data identity drift: "
                f"{', '.join(d.model for d in fatal)}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nReference-data identity parity verified across {len(results)} model(s)."
            ))
