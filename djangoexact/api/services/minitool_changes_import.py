"""Import permutation results directly into ``minitool.ChangeRecord``.

This is the in-memory equivalent of the CSV round-trip performed by
``scripts/analyze_changes.py`` followed by
``minitool/management/commands/import_changes.py``.

The compile-scenarios pipeline (``compute_module_slice``) already has the
permutation results in memory as a ``list[dict]``; calling
``import_changes_from_data`` populates ``ChangeRecord`` directly so the
scenario UI and Excel export immediately see non-zero counts.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from django.db import transaction

from minitool.models import ChangeRecord


logger = logging.getLogger(__name__)


# Mirrors ``import_changes.import_individual_records`` so behaviour stays
# consistent across the legacy CSV path and the new in-memory path.
BATCH_SIZE = 1000

# Keys that are *never* treated as custom filters because they map to
# dedicated ChangeRecord columns or are derived (changes, csv_row_data).
# Matches ``import_changes.identify_filter_columns`` exactly.
_STANDARD_FIELDS: frozenset[str] = frozenset(
    {
        "module_type",
        "region",
        "climate",
        "moisture",
        "soil_type",
        "total",
        "changes",
        "csv_row_data",
    }
)

_FILTER_EXCLUDED_SUFFIXES: tuple[str, ...] = ("_start", "_w", "_wo")


def _coerce_scalar(value: Any) -> Any:
    """Coerce a single value to a JSON-serialisable scalar.

    ``compute_permutations`` builds dicts whose values are usually plain
    Python scalars (str / int / float / bool / None / list[str]). Region
    fields, however, are still ``api.models.Region`` instances at this
    point. Coerce model objects to ``str(obj)``; leave everything else
    alone so JSONField serialisation keeps native types.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_coerce_scalar(v) for v in value]
    if isinstance(value, dict):
        return {k: _coerce_scalar(v) for k, v in value.items()}
    # Django model instances and any other objects: stringify.
    return str(value)


def _build_csv_row_data(record: dict) -> dict:
    """Build the ``csv_row_data`` JSON blob for a record.

    ``analyze_changes`` stores the *full* CSV row. We do the same here
    using the raw input dict, after coercing values for JSON safety.
    """
    return {key: _coerce_scalar(value) for key, value in record.items()}


def _identify_filter_columns(data: list[dict]) -> list[str]:
    """Identify custom filter columns using the same rule as
    ``import_changes.identify_filter_columns``: non-numeric keys that
    don't end with ``_start``/``_w``/``_wo`` and aren't part of the
    standard ChangeRecord schema.
    """
    if not data:
        return []

    all_keys: set[str] = set()
    for record in data:
        all_keys.update(record.keys())

    custom_filters: list[str] = []
    sample = data[:10]

    for key in all_keys:
        if key in _STANDARD_FIELDS:
            continue
        if any(key.endswith(suffix) for suffix in _FILTER_EXCLUDED_SUFFIXES):
            continue

        # Treat as filter only if the column holds non-numeric values
        # in any of the sampled records. Pure-numeric columns (e.g.
        # heads_number) are *not* filters.
        is_numerical = True
        for record in sample:
            if key not in record:
                continue
            value = record[key]
            if value is None or value == "":
                continue
            try:
                float(value)
            except (ValueError, TypeError):
                is_numerical = False
                break

        if not is_numerical:
            custom_filters.append(key)

    # Sort for deterministic ordering -- otherwise set iteration order
    # could subtly affect logging output and tests.
    custom_filters.sort()
    return custom_filters


def _iter_column_pairs(record_keys: Iterable[str]) -> list[tuple[str, str, str]]:
    """Find ``(start_col, w_col, base_name)`` triples for change detection.

    Mirrors the column-pair discovery in ``analyze_changes.analyze_changes``
    but works on a dict's keys instead of a DataFrame's columns. Only
    ``_start``/``_w`` pairs are inspected for changes (matching the legacy
    behaviour -- ``_wo`` is the without-project counterfactual and is not
    a "change").
    """
    keys = list(record_keys)
    keys_set = set(keys)
    pairs: list[tuple[str, str, str]] = []
    for key in keys:
        if not key.endswith("_start"):
            continue
        base = key[: -len("_start")]
        w_key = f"{base}_w"
        if w_key in keys_set:
            pairs.append((key, w_key, base))
    return pairs


def _build_change_record_models(
    data: list[dict],
    module_type: str,
    filter_columns: list[str],
) -> tuple[list[ChangeRecord], int]:
    """Walk ``data`` and produce unsaved ChangeRecord instances.

    Returns ``(records, skipped_no_change)`` where ``skipped_no_change``
    counts input rows whose ``_start``/``_w`` pairs were all equal (no
    change to record).
    """
    records: list[ChangeRecord] = []
    skipped_no_change = 0

    for row in data:
        column_pairs = _iter_column_pairs(row.keys())

        row_changes: list[dict] = []
        for start_col, w_col, base_name in column_pairs:
            start_value = row.get(start_col)
            w_value = row.get(w_col)
            if start_value != w_value:
                row_changes.append(
                    {"field": base_name, "from": start_value, "to": w_value}
                )

        if not row_changes:
            skipped_no_change += 1
            continue

        region = _coerce_scalar(row.get("region", "")) or ""
        climate = row.get("climate", "") or ""
        moisture = row.get("moisture", "") or ""
        soil_type = row.get("soil_type", "") or ""
        total_raw = row.get("total", 0)
        try:
            total = float(total_raw) if total_raw is not None else 0.0
        except (TypeError, ValueError):
            total = 0.0

        custom_filters = {
            column: _coerce_scalar(row.get(column, ""))
            for column in filter_columns
            if column in row
        }
        csv_row_data = _build_csv_row_data(row)

        for change in row_changes:
            field = change["field"]
            from_value = change["from"]
            to_value = change["to"]

            # Match the skip rule from ``import_individual_records``:
            # bail on missing field/None values, but allow falsy scalars
            # like 0 / False / empty-string-after-stringify.
            if not field or from_value is None or to_value is None:
                continue

            records.append(
                ChangeRecord(
                    module_type=module_type,
                    region=str(region),
                    climate=str(climate),
                    moisture=str(moisture),
                    soil_type=str(soil_type),
                    field=field,
                    from_value=str(from_value),
                    to_value=str(to_value),
                    custom_filters=custom_filters,
                    csv_row_data=csv_row_data,
                    total=total,
                )
            )

    return records, skipped_no_change


def import_changes_from_data(data: list[dict], module_type: str) -> dict:
    """Bulk-insert ``ChangeRecord`` rows from in-memory permutation data.

    Parameters
    ----------
    data:
        The ``data`` list returned by
        ``api.minitool.PermutationComputer.compute_permutations``. Each
        element is a flat dict with ``region`` / ``climate`` / ``moisture``
        / ``soil_type`` / ``total`` plus ``_start``/``_w``/``_wo`` field
        triples and any module-specific extras.
    module_type:
        Canonical module name (e.g. ``"Grassland"``). Used verbatim as
        the ``ChangeRecord.module_type`` value -- callers must pass the
        canonical PascalCase / spaced name, not the lowercase CSV-derived
        variant; this function does *not* apply the lowercase repair
        mapping that ``analyze_changes.py`` uses.

    Behavior
    --------
    * Rows with zero ``_start``/``_w`` differences are skipped.
    * Inserts run via ``bulk_create(update_conflicts=True, ...)`` against
      ``ChangeRecord``'s unique constraint, so re-running the same
      computation does not double-count rows -- the ``total`` field is
      refreshed in place.
    * The whole batch sequence is wrapped in ``transaction.atomic()``.

    Returns
    -------
    dict
        ``{"created_or_updated": int, "skipped_no_change": int}``.
        We do not distinguish created vs updated -- ``bulk_create`` with
        ``update_conflicts=True`` does not surface that information
        reliably.
    """
    if not data:
        logger.info(
            "import_changes_from_data: no data for module_type=%s, nothing to do",
            module_type,
        )
        return {"created_or_updated": 0, "skipped_no_change": 0}

    filter_columns = _identify_filter_columns(data)
    if filter_columns:
        logger.debug(
            "import_changes_from_data: identified custom filter columns for %s: %s",
            module_type,
            ", ".join(filter_columns),
        )

    records, skipped_no_change = _build_change_record_models(
        data, module_type, filter_columns
    )

    total_records = len(records)
    if total_records == 0:
        logger.info(
            "import_changes_from_data: %s produced 0 ChangeRecord rows "
            "(skipped_no_change=%d)",
            module_type,
            skipped_no_change,
        )
        return {"created_or_updated": 0, "skipped_no_change": skipped_no_change}

    created_or_updated = 0
    with transaction.atomic():
        for start in range(0, total_records, BATCH_SIZE):
            batch = records[start : start + BATCH_SIZE]
            ChangeRecord.objects.bulk_create(
                batch,
                update_conflicts=True,
                update_fields=["total"],
                unique_fields=[
                    "module_type",
                    "region",
                    "climate",
                    "moisture",
                    "soil_type",
                    "field",
                    "from_value",
                    "to_value",
                    "custom_filters",
                    "csv_row_data",
                ],
            )
            created_or_updated += len(batch)

    logger.info(
        "import_changes_from_data: %s wrote %d ChangeRecord rows "
        "(skipped_no_change=%d)",
        module_type,
        created_or_updated,
        skipped_no_change,
    )

    return {
        "created_or_updated": created_or_updated,
        "skipped_no_change": skipped_no_change,
    }
