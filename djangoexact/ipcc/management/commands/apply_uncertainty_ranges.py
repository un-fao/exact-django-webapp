"""Write the published IPCC uncertainty bounds straight into this database.

The database is the source of truth: the natural-key join and base-value gate that
`import_uncertainties` runs against the fixture files run here against this database's
own rows, so a bound is only ever written beside the base value it was checked against.
Only publishable tables are written (`is_publishable`), and only their
`<field>_min`/`<field>_max` columns; every other column is left exactly as it is.

    APP_MODE=review python manage.py apply_uncertainty_ranges --dry-run
    APP_MODE=review python manage.py apply_uncertainty_ranges
"""

import math

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from ipcc.management.commands import import_uncertainties as iu


def db_payload(model):
    """This database's rows, shaped like the fixture entries the join reads."""
    qs = model._base_manager.all()
    if hasattr(qs, "rewrite"):
        # modeltranslation would otherwise swap `name` for the active-language column,
        # while the CSVs (and the fixtures) carry the base column.
        qs = qs.rewrite(False)
    fields = [f for f in model._meta.concrete_fields if not f.primary_key]
    pk = model._meta.pk.attname
    return [
        {"model": model._meta.label_lower, "pk": row[pk], "fields": {f.name: row[f.attname] for f in fields}}
        for row in qs.order_by("pk").values(pk, *(f.attname for f in fields))
    ]


def load_join_input(csv_paths):
    """Every table the join reads -- each CSV's model and every model its FKs point at --
    so `load_fixture` never falls back to a file on disk and mixes the two sources."""
    by_fixture = {spec.fixture_file: spec for spec in iu.MANIFEST}
    by_label = {spec.model.lower(): spec for spec in iu.MANIFEST}
    cache = {}
    for csv_path in csv_paths:
        spec = by_fixture[f"{iu.resolve_fixture_name(csv_path)}.json"]
        model = iu.django_apps.get_model(spec.model)
        related = [f.related_model for f in model._meta.concrete_fields if f.is_relation]
        for m in (model, *related):
            fixture_file = by_label[m._meta.label_lower].fixture_file
            if fixture_file not in cache:
                cache[fixture_file] = db_payload(m)
    return cache


def plan_writes(current, patches):
    """Split `patches` ({pk: {column: bound}}) against `current` ({pk: {column: value}})
    into the writes to make and the conflicts to report. A null bound is never written,
    and an existing value that differs is never overwritten."""
    writes, conflicts = {}, []
    for pk, bounds in patches.items():
        for column, new in bounds.items():
            if new is None:
                continue
            old = current[pk][column]
            if old is None:
                writes.setdefault(pk, {})[column] = new
            elif not math.isclose(old, new, rel_tol=1e-9, abs_tol=1e-12):
                conflicts.append((pk, column, old, new))
    return writes, conflicts


class Command(BaseCommand):
    help = "Write published IPCC uncertainty bounds into this database, touching only the bound columns."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would be written; write nothing.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        db = connection.settings_dict
        self.stdout.write(f"database {db['NAME']} at {db.get('HOST') or 'localhost'}:{db.get('PORT') or ''}")

        csv_paths = sorted(iu.data_dir().glob("*.csv"))
        tables, results = iu.compute_all(csv_paths, load_join_input(csv_paths))
        iu.Command(stdout=self.stdout, stderr=self.stderr)._print_report(tables, iu.aggregate_totals(tables))

        rows_written = cells_written = conflicts_seen = 0
        with transaction.atomic():
            for spec, patches, _groups, _base_values in results.values():
                if not patches:
                    continue
                model = iu.django_apps.get_model(spec.model)
                objs = model._base_manager.in_bulk(list(patches))
                columns = sorted({c for bounds in patches.values() for c in bounds})
                current = {pk: {c: getattr(obj, c) for c in columns} for pk, obj in objs.items()}
                writes, conflicts = plan_writes(current, patches)

                for pk, column, old, new in conflicts:
                    self.stderr.write(self.style.WARNING(f"  kept {spec.model} pk={pk} {column}={old} (bound says {new})"))
                for pk, bounds in writes.items():
                    for column, value in bounds.items():
                        setattr(objs[pk], column, value)
                if writes and not dry_run:
                    written_columns = sorted({c for bounds in writes.values() for c in bounds})
                    model._base_manager.bulk_update([objs[pk] for pk in writes], written_columns, batch_size=500)

                cells = sum(len(b) for b in writes.values())
                self.stdout.write(f"{spec.model:<45} rows={len(writes):>6} cells={cells:>6} conflicts={len(conflicts)}")
                rows_written += len(writes)
                cells_written += cells
                conflicts_seen += len(conflicts)

        verb = "would write" if dry_run else "wrote"
        published = sum(1 for t in tables if t["published"])
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {cells_written} bounds on {rows_written} rows across {published} published tables; "
            f"{conflicts_seen} existing values kept"
        ))
