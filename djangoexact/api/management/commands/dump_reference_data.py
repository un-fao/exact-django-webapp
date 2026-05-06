"""Dump reference/lookup data to per-model fixture files in manifest order.

The manifest in `djangoexact/api/fixtures_manifest.py` is the single source of
truth for which models are dumped and in what order. This command is the
inverse of `load_reference_data`.

PK stability guardrail: before writing a fixture, the command compares the
existing committed fixture's {pk: order_by_tuple} map against the freshly
queried one. If any previously-committed PK would be reassigned to a different
row, the dump aborts with a diff summary. Use `--force` to override.
"""

import json
import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core import serializers

from api.fixtures_manifest import MANIFEST, filter_manifest


class Command(BaseCommand):
    help = "Dump reference data fixtures in manifest order with PK stability guardrail."

    def add_arguments(self, parser):
        parser.add_argument("--app", default="all", choices=["api", "ipcc", "all"])
        parser.add_argument("--models", default=None, help="Comma-separated list of models to restrict to.")
        parser.add_argument("--output-dir", default=None, help="Override output dir (useful for tests). Writes all fixtures flat here.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true", help="Bypass PK stability guardrail.")
        parser.add_argument("--no-combined", action="store_true", help="Skip writing all_reference_data.json combined output.")

    def handle(self, *args, **options):
        models_arg = options["models"]
        selected = filter_manifest(
            app=options["app"],
            models=[m.strip() for m in models_arg.split(",")] if models_arg else None,
        )
        if not selected:
            raise CommandError("No manifest entries matched the given filters.")

        output_dir_override = options["output_dir"]
        dry_run = options["dry_run"]
        force = options["force"]

        errors = []
        written = []
        combined_payload = []

        for spec in selected:
            try:
                model = apps.get_model(spec.model)
            except LookupError as exc:
                errors.append(f"{spec.model}: {exc}")
                continue

            qs = model.objects.all().order_by(*spec.order_by)
            serialized = serializers.serialize(
                "json", qs, indent=2, use_natural_primary_keys=False, use_natural_foreign_keys=False,
            )
            payload = json.loads(serialized)
            payload = self._normalize_m2m(payload, model)

            target_path = self._resolve_target(spec, output_dir_override)

            if not force and target_path.exists():
                try:
                    self._check_pk_stability(spec, payload, target_path)
                except CommandError as exc:
                    errors.append(str(exc))
                    continue

            if dry_run:
                self.stdout.write(f"[dry-run] would write {len(payload)} rows -> {target_path}")
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2, ensure_ascii=False)
                    fh.write("\n")
                self.stdout.write(f"wrote {len(payload):>6} rows -> {target_path}")
            written.append((spec, target_path))
            combined_payload.extend(payload)

        if not options["no_combined"] and not dry_run and output_dir_override is None:
            self._write_combined(combined_payload)

        if errors:
            self.stderr.write("\nErrors:")
            for err in errors:
                self.stderr.write(f"  - {err}")
            raise CommandError(f"dump_reference_data completed with {len(errors)} error(s).")

        self.stdout.write(self.style.SUCCESS(f"Dumped {len(written)} fixtures."))

    # --- helpers -----------------------------------------------------------
    def _normalize_m2m(self, payload, model):
        """Sort M2M PK lists ascending so dumps are stable across load->dump cycles.

        Django's JSON serializer emits M2M PK lists in whatever order the
        through-table SELECT returns, which depends on insertion order. After
        ``loaddata`` reinserts through rows in JSON list order, a subsequent
        dump may come back in a different order even though the content is
        identical. Normalizing to ascending PK order gives us a canonical
        form that survives round trips.
        """
        m2m_field_names = [f.name for f in model._meta.many_to_many]
        if not m2m_field_names:
            return payload
        for entry in payload:
            fields = entry.get("fields", {})
            for name in m2m_field_names:
                value = fields.get(name)
                if isinstance(value, list):
                    try:
                        fields[name] = sorted(value)
                    except TypeError:
                        # Mixed/natural-key values: fall back to stringified sort
                        fields[name] = sorted(value, key=lambda v: (str(type(v)), str(v)))
        return payload

    def _resolve_target(self, spec, override):
        if override is not None:
            return Path(override) / spec.fixture_file
        base = Path(settings.BASE_DIR) if hasattr(settings, "BASE_DIR") else Path(os.getcwd())
        # BASE_DIR points at the inner djangoexact/ package root; fixtures live
        # at <BASE_DIR>/<app>/fixtures/.
        return base / spec.app / "fixtures" / spec.fixture_file

    def _check_pk_stability(self, spec, new_payload, target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as fh:
                old_payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return

        def key_tuple(entry):
            fields = entry.get("fields", {})
            return tuple(fields.get(k) for k in spec.order_by)

        old_map = {e["pk"]: key_tuple(e) for e in old_payload}
        new_map = {e["pk"]: key_tuple(e) for e in new_payload}

        reassigned = []
        for pk, old_key in old_map.items():
            if pk in new_map and new_map[pk] != old_key:
                reassigned.append((pk, old_key, new_map[pk]))

        if reassigned:
            diff_lines = [f"PK stability violation for {spec.model} ({target_path.name}):"]
            for pk, old_key, new_key in reassigned[:20]:
                diff_lines.append(f"  pk={pk}: {old_key!r} -> {new_key!r}")
            if len(reassigned) > 20:
                diff_lines.append(f"  ... and {len(reassigned) - 20} more")
            diff_lines.append("Use --force to override (renumbering existing rows will break FKs).")
            raise CommandError("\n".join(diff_lines))

        removed = sorted(set(old_map) - set(new_map))
        if removed:
            self.stdout.write(self.style.WARNING(
                f"  warning: {spec.model} has {len(removed)} PK(s) in committed fixture missing from DB: {removed[:10]}"
            ))

    def _write_combined(self, payload):
        base = Path(settings.BASE_DIR) if hasattr(settings, "BASE_DIR") else Path(__file__).resolve().parents[3]
        target = base / "api" / "fixtures" / "all_reference_data.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        self.stdout.write(f"wrote combined fixture -> {target}")
