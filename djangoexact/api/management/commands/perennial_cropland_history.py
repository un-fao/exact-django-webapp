"""
Diagnostic management command to inspect the audit history of a
``PerennialCropland`` instance.

It walks the ``django-simple-history`` historical manager for the requested
primary key (oldest first), emits the full field snapshot taken at creation
time, and then emits the diff between each subsequent historical record and
its predecessor.

Output can be either human-readable (default) or JSON (``--json``).
"""

import json
from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Model

from api.models import PerennialCropland


HISTORY_TYPE_WORDS = {
    "+": "created",
    "~": "changed",
    "-": "deleted",
}


def _serialize_value(value):
    """Best-effort JSON-safe serialization of a tracked field value."""
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, float):
        return value
    if isinstance(value, Decimal):
        # Preserve precision as string; JSON has no native Decimal.
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Model):
        # Foreign key -> emit primary key only.
        return value.pk
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, str):
        return value
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _tracked_field_names(historical_record):
    """Return the list of tracked field names for a historical record.

    Uses simple-history's ``tracked_fields`` attribute (editable fields are
    normally what you diff against). We include *all* tracked fields to give a
    complete snapshot at creation.
    """
    return [f.attname for f in historical_record.tracked_fields]


def _snapshot(historical_record):
    """Collect all tracked field values from a historical record."""
    snapshot = {}
    for attname in _tracked_field_names(historical_record):
        try:
            snapshot[attname] = getattr(historical_record, attname)
        except Exception as exc:  # pragma: no cover - defensive fallback
            snapshot[attname] = f"<unreadable: {exc!r}>"
    return snapshot


def _history_user_repr(historical_record):
    """Username if available, otherwise the user id, otherwise None."""
    user = None
    try:
        user = historical_record.history_user
    except Exception:
        # FK to a now-missing user row, for instance.
        user = None
    if user is None:
        user_id = getattr(historical_record, "history_user_id", None)
        return user_id
    username = getattr(user, "username", None)
    if username:
        return username
    return getattr(user, "pk", None)


class Command(BaseCommand):
    help = (
        "Print the full modification history of a PerennialCropland, including "
        "the creation snapshot and the diff of each subsequent change."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "pk",
            type=int,
            help="Primary key of the PerennialCropland to inspect.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit machine-readable JSON instead of human-readable text.",
        )

    def handle(self, *args, **options):
        pk = options["pk"]
        as_json = options["as_json"]

        # Historical records survive live-row deletion, so query the historical
        # manager directly by object id rather than going through the live
        # model.
        history_qs = PerennialCropland.history.filter(id=pk).order_by("history_date")

        if not history_qs.exists():
            # Double-check: if the live row exists but somehow has no history
            # (e.g. created before history was enabled), we still want a
            # useful error.
            try:
                PerennialCropland.objects.get(pk=pk)
            except PerennialCropland.DoesNotExist:
                raise CommandError(
                    f"No PerennialCropland with id={pk} and no historical records either."
                )
            message = f"PerennialCropland id={pk} has no historical records."
            if as_json:
                self.stdout.write(json.dumps({"pk": pk, "entries": [], "message": message}))
            else:
                self.stdout.write(self.style.WARNING(message))
            return

        records = list(history_qs)
        entries = []
        previous = None

        for idx, record in enumerate(records):
            entry = {
                "index": idx,
                "history_id": record.history_id,
                "history_date": record.history_date.isoformat() if record.history_date else None,
                "history_type": record.history_type,
                "history_type_label": HISTORY_TYPE_WORDS.get(record.history_type, record.history_type),
                "history_user": _history_user_repr(record),
                "history_change_reason": record.history_change_reason,
            }

            if previous is None:
                # First record — treat as the creation snapshot regardless of
                # its history_type. (simple-history may log the first row as
                # '+' for creates or '~' if history was enabled on an existing
                # row — either way the snapshot is the baseline we need.)
                snapshot = _snapshot(record)
                entry["snapshot"] = {k: _serialize_value(v) for k, v in snapshot.items()}
            else:
                delta = record.diff_against(previous)
                entry["changes"] = [
                    {
                        "field": change.field,
                        "old": _serialize_value(change.old),
                        "new": _serialize_value(change.new),
                    }
                    for change in delta.changes
                ]

            entries.append(entry)
            previous = record

        if as_json:
            self.stdout.write(json.dumps({"pk": pk, "entries": entries}, indent=2, default=str))
            return

        self._render_human(pk, entries)

    # ------------------------------------------------------------------ #
    # Human-readable rendering
    # ------------------------------------------------------------------ #
    def _render_human(self, pk, entries):
        self.stdout.write(
            self.style.SUCCESS(
                f"History for PerennialCropland id={pk} ({len(entries)} record(s))"
            )
        )
        self.stdout.write("=" * 72)

        for entry in entries:
            header = (
                f"[{entry['index']}] {entry['history_date']}  "
                f"{entry['history_type_label']} ({entry['history_type']})"
            )
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(header))
            self.stdout.write(f"    history_id:            {entry['history_id']}")
            self.stdout.write(f"    history_user:          {entry['history_user']}")
            self.stdout.write(
                f"    history_change_reason: {entry['history_change_reason'] or '-'}"
            )

            if "snapshot" in entry:
                self.stdout.write("    snapshot (creation baseline):")
                for field, value in sorted(entry["snapshot"].items()):
                    self.stdout.write(f"        {field} = {value!r}")
            else:
                changes = entry.get("changes", [])
                if not changes:
                    self.stdout.write("    changes: (none detected by diff_against)")
                else:
                    self.stdout.write("    changes:")
                    for change in changes:
                        self.stdout.write(
                            f"        {change['field']}: {change['old']!r} -> {change['new']!r}"
                        )
