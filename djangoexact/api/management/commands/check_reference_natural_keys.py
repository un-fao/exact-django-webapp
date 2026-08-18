"""Detect reference rows that break their declared natural key.

Run this BEFORE deploying the uniqueness constraints that back the natural keys
in `api/natural_keys.py`, and before trusting a `.exactproject` import on any
installation. Two failure shapes are reported:

- **duplicates**: two or more rows share a natural key, so the key cannot
  identify a row and the uniqueness migration will fail on this data.
- **empty components**: a key component is NULL or blank, most often an
  unpopulated `name_en`. That breaks resolution exactly as badly as a duplicate
  and is invisible to a uniqueness constraint.

Exit code 1 when anything is reported.

    python manage.py check_reference_natural_keys
    python manage.py check_reference_natural_keys --json

Reference data is database-truth (docs/guides/fixtures-guide.md). If this command
reports anything, do NOT dedupe, rename, merge or delete rows to make it pass:
that silently changes what existing projects point at. Report the finding and
decide deliberately.
"""

import json
import sys
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand

from api.natural_keys import NATURAL_KEY_SPECS


class Command(BaseCommand):
    help = "Report reference rows whose declared natural key is duplicated, NULL or blank."

    def add_arguments(self, parser):
        parser.add_argument("--models", default=None, help="Comma-separated list of models to restrict to.")
        parser.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON.")

    def handle(self, *args, **options):
        wanted = None
        if options["models"]:
            wanted = {m.strip() for m in options["models"].split(",")}

        findings = []
        skipped = []

        for label, spec in NATURAL_KEY_SPECS.items():
            if wanted is not None and label not in wanted and label.split(".", 1)[1] not in wanted:
                continue
            try:
                model = apps.get_model(label)
            except LookupError as exc:
                skipped.append(f"{label}: {exc}")
                continue

            findings.extend(self._inspect(model, spec))

        if options["as_json"]:
            self.stdout.write(json.dumps({"findings": findings, "skipped": skipped}, indent=2, ensure_ascii=False))
        else:
            self._report(findings, skipped)

        if findings:
            sys.exit(1)

    # --- helpers -----------------------------------------------------------
    def _inspect(self, model, spec):
        rows = list(model.objects.values_list("pk", *spec.fields).order_by("pk"))

        by_key = defaultdict(list)
        empties = []
        for row in rows:
            pk, key = row[0], tuple(row[1:])
            if any(part is None or (isinstance(part, str) and not part.strip()) for part in key):
                # A nullable composite member is a legitimate part of the identity;
                # only report it when the whole key is unusable.
                if all(part is None or (isinstance(part, str) and not part.strip()) for part in key):
                    empties.append(pk)
                    continue
            by_key[key].append(pk)

        findings = []
        for key, pks in sorted(by_key.items(), key=lambda item: item[1][0]):
            if len(pks) > 1:
                findings.append({
                    "model": spec.label,
                    "kind": "duplicate",
                    "fields": list(spec.fields),
                    "key": [None if part is None else str(part) for part in key],
                    "pks": pks,
                })
        if empties:
            findings.append({
                "model": spec.label,
                "kind": "empty_key",
                "fields": list(spec.fields),
                "key": None,
                "pks": empties,
            })
        return findings

    def _report(self, findings, skipped):
        if not findings:
            self.stdout.write(self.style.SUCCESS(
                f"No duplicate or empty natural keys across {len(NATURAL_KEY_SPECS)} registered model(s)."
            ))
        for finding in findings:
            if finding["kind"] == "duplicate":
                key = " / ".join("" if part is None else part for part in finding["key"])
                self.stdout.write(self.style.ERROR(
                    f"DUPLICATE  {finding['model']} ({', '.join(finding['fields'])}) "
                    f"= '{key}' -> pks {finding['pks']}"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"EMPTY KEY  {finding['model']} ({', '.join(finding['fields'])}) "
                    f"-> pks {finding['pks']}"
                ))

        for line in skipped:
            self.stdout.write(self.style.WARNING(f"skipped    {line}"))

        if findings:
            self.stdout.write(self.style.ERROR(
                f"\n{len(findings)} finding(s). Do not dedupe reference data to silence this: "
                f"reference data is database-truth and existing projects point at these rows."
            ))
