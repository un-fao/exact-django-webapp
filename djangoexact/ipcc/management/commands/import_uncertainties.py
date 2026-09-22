"""Join the 64 committed uncertainty CSVs onto the reference fixtures by natural key.

Stdlib only (csv/json/math/pathlib/re); never touches the database (see conftest.py) --
CSVs and fixtures are read and written as plain files. The mapping tables below are the
single hand-written input; everything else (ranged column groups, join keys, FK pk maps)
is derived from Django's model introspection and the committed fixtures themselves.
"""

import csv
import json
import math
import re
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.fixtures_manifest import MANIFEST

ALIAS = {
    "ipcc.forestmanagementbgb": "forestmanagementroottoshoot",
    "ipcc.totalbiomassafterdefo_from_agb_bgb": "totalbiomassafterdefo",
    "grasslandagb": "grasslandbiomass",
}

CP1252_FILES = {"inputemissionfactor.csv", "irrigationsystemdata.csv"}

NULL_TOKENS = {"", "N/A", "#N/A", "NA", "NULL", "-"}

# csv filename (lowercased) -> {csv base column: model field name}, for CSVs where the
# ranged pair's stem doesn't literally name the model field.
COLMAP = {
    "ipcc.atwood.csv": {"area_2014": "area_2014_km2"},
}

# csv filename (lowercased) -> ranged groups that replace default derivation entirely
# for that file. model_field -> (base_col, min_col, max_col); any side may be None.
GROUP_OVERRIDES = {
    "ipcc.forestmanagementagb.csv": {
        "agb_min": ("agb_min", "agb_min_min", None),
        "agb_max": ("agb_max", None, "agb_max_max"),
        "agb_growth_min": ("agb_growth_min", "agb_growth_min_min", None),
        "agb_growth_max": ("agb_growth_max", None, "agb_growth_max_max"),
    },
    "grasslandagb.csv": {
        "agb_t_dm_ha": ("value", "value_min", "value_max"),
    },
    "ipcc.totalbiomassafterdefo_from_agb_bgb.csv": {
        "value": ("totalbiomass", "totalbiomass_min", "totalbiomass_max"),
    },
    "ipcc.forestmanagementbgb.csv": {
        "value": ("value", "value_min", "value_max"),
    },
}

# csv filename (lowercased) -> {model_field: (base_idx, min_idx, max_idx)} for headers
# where the min/max pair isn't addressable by name.
POSITIONAL_GROUP_OVERRIDES = {
    "firescombustionfactor.csv": {
        "value": (2, 3, 4),
    },
}

INT_FIELD_TYPES = {
    "IntegerField", "BigIntegerField", "SmallIntegerField",
    "PositiveIntegerField", "PositiveSmallIntegerField", "PositiveBigIntegerField",
}
FLOAT_FIELD_TYPES = {"FloatField", "DecimalField"}

# Django's default relation __str__ ("EmissionType object (3)") and the organic-soil /
# peat-extraction "(24) Forest Management (LUC)" display format both carry a pk.
OBJ_PK_RE = re.compile(r"^\w+ object \((\d+)\)$")
PAREN_PK_RE = re.compile(r"^\((\d+)\)\s*(.+)$")

REPORT_COUNT_KEYS = (
    "csv_rows", "fixture_rows", "matched_unique", "written", "carrying_bound",
    "unmatched", "unresolved_fk", "ambiguous", "conflict", "base_mismatch",
)
SKIPPED_ROW_KEYS = ("unmatched", "unresolved_fk", "ambiguous", "conflict", "base_mismatch")

# Per bucket, per table. Skipped rows total ~1200 today; the cap only bounds a
# future drop that goes badly wrong, so --detail can never blow up in memory.
DETAIL_CAP = 200


def _is_null(raw):
    return raw.strip().upper() in NULL_TOKENS


def _to_float_or_none(raw):
    try:
        return float(raw)
    except ValueError:
        return None


def get_cell(row, ref, name_to_index):
    """ref is a column name (str), a positional index (int), or None."""
    if ref is None:
        return ""
    idx = ref if isinstance(ref, int) else name_to_index.get(ref)
    if idx is None or idx >= len(row):
        return ""
    return row[idx]


def resolve_fixture_name(csv_path):
    stem = csv_path.stem.lower()
    name = ALIAS.get(stem)
    if name is None:
        name = stem[len("ipcc."):] if stem.startswith("ipcc.") else stem
    return name


def read_csv_rows(csv_path):
    encoding = "cp1252" if csv_path.name.lower() in CP1252_FILES else "utf-8-sig"
    with open(csv_path, encoding=encoding, newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        raise CommandError(f"{csv_path.name}: empty file")
    header = [c.strip() for c in rows[0]]
    name_to_index = {}
    for i, name in enumerate(header):
        if name and name not in name_to_index:
            name_to_index[name] = i
    data_rows = [r for r in rows[1:] if any(c.strip() for c in r)]
    return name_to_index, data_rows


def compute_ranged_groups(csv_path, name_to_index, field_map):
    """Returns (groups, names_used): groups is model_field -> (base_ref, min_ref, max_ref);
    names_used is the set of literal CSV column names spent on ranged groups, excluded
    from the join key so a future migration adding `<field>_min` can't turn a ranged
    column into a phantom key column."""
    key = csv_path.name.lower()

    if key in POSITIONAL_GROUP_OVERRIDES:
        groups = {
            field: refs for field, refs in POSITIONAL_GROUP_OVERRIDES[key].items()
        }
        return groups, set()

    if key in GROUP_OVERRIDES:
        groups = dict(GROUP_OVERRIDES[key])
        names_used = {n for refs in groups.values() for n in refs if n}
        return groups, names_used

    colmap = COLMAP.get(key, {})
    groups = {}
    names_used = set()
    for name in name_to_index:
        if not name.endswith("_min"):
            continue
        base = name[:-4]
        max_name = base + "_max"
        if max_name not in name_to_index:
            continue
        model_field = colmap.get(base, base)
        field = field_map.get(model_field)
        if field is None or field.is_relation:
            continue
        if base in name_to_index:
            base_col = base
        elif colmap.get(base, base) in name_to_index:
            base_col = colmap.get(base, base)
        else:
            base_col = None
        groups[model_field] = (base_col, name, max_name)
        names_used.update(n for n in (base_col, name, max_name) if n)
    return groups, names_used


def derive_key_columns(name_to_index, colmap, field_map, ranged_model_fields, ranged_names_used):
    keys = []
    for name in name_to_index:
        if name in ("id", "unit") or name.endswith("_unit"):
            continue
        if name in ranged_names_used:
            continue
        model_field = colmap.get(name, name)
        if model_field in ranged_model_fields:
            continue
        field = field_map.get(model_field)
        if field is None:
            continue
        keys.append((name, model_field, field))
    return keys


def spec_for_field(field, manifest_by_model):
    label = field.related_model._meta.label_lower
    spec = manifest_by_model.get(label)
    if spec is None:
        raise CommandError(f"no MANIFEST entry for related model {label!r}")
    return spec


def load_fixture(spec, fixture_cache):
    if spec.fixture_file not in fixture_cache:
        path = Path(settings.BASE_DIR) / spec.app / "fixtures" / spec.fixture_file
        with open(path, encoding="utf-8") as fh:
            fixture_cache[spec.fixture_file] = json.load(fh)
    return fixture_cache[spec.fixture_file]


def build_fk_lookup(related_spec, fixture_cache):
    rows = load_fixture(related_spec, fixture_cache)
    name_field = None
    for candidate in ("name", "value", "label"):
        if rows and candidate in rows[0]["fields"]:
            name_field = candidate
            break
    by_name = {}
    pk_set = set()
    for row in rows:
        pk_set.add(row["pk"])
        if name_field is not None:
            display = row["fields"].get(name_field)
            if display is not None:
                key = str(display).strip().lower()
                # A name two rows share can't pick one of them; leaving it unresolved beats
                # letting row order decide (FuelType has two "Motor Gasoline" rows).
                by_name[key] = None if key in by_name else row["pk"]
    return by_name, pk_set


def build_key(row, key_cols, name_to_index, fk_lookups):
    """Returns the join key tuple, or None if any component failed to resolve."""
    parts = []
    for name, model_field, field in key_cols:
        raw = get_cell(row, name, name_to_index).strip()
        if _is_null(raw):
            parts.append(None)
            continue
        if field.is_relation:
            by_name, pk_set = fk_lookups[model_field]
            m = OBJ_PK_RE.match(raw) or PAREN_PK_RE.match(raw)
            if m:
                pk = int(m.group(1))
                if pk not in pk_set:
                    return None
                parts.append(pk)
                continue
            pk = by_name.get(raw.lower())
            if pk is None:
                return None
            parts.append(pk)
            continue
        try:
            itype = field.get_internal_type()
            if itype in INT_FIELD_TYPES:
                parts.append(int(float(raw)))
            elif itype in FLOAT_FIELD_TYPES:
                parts.append(float(raw))
            else:
                parts.append(raw)
        except ValueError:
            return None
    return tuple(parts)


def explain_unresolved(row, key_cols, name_to_index, fk_lookups):
    """Which key columns build_key could not resolve, as [(csv column, raw value)]."""
    bad = []
    for name, model_field, field in key_cols:
        raw = get_cell(row, name, name_to_index).strip()
        if _is_null(raw):
            continue
        if field.is_relation:
            by_name, pk_set = fk_lookups[model_field]
            m = OBJ_PK_RE.match(raw) or PAREN_PK_RE.match(raw)
            if m:
                if int(m.group(1)) not in pk_set:
                    bad.append((name, raw))
            elif by_name.get(raw.lower()) is None:
                bad.append((name, raw))
            continue
        itype = field.get_internal_type()
        if itype in INT_FIELD_TYPES or itype in FLOAT_FIELD_TYPES:
            try:
                float(raw)
            except ValueError:
                bad.append((name, raw))
    return bad


def key_display(row, key_cols, name_to_index):
    """The row's natural key as the CSV spells it -- names, not resolved pks."""
    return {name: get_cell(row, name, name_to_index).strip() for name, _, _ in key_cols}


def build_fixture_index(fixture_rows, key_cols):
    index = {}
    for row in fixture_rows:
        parts = tuple(row["fields"].get(model_field) for _, model_field, _ in key_cols)
        index.setdefault(parts, []).append(row["pk"])
    return index


def process_csv(csv_path, spec, model, manifest_by_model, fixture_cache, detail=None):
    field_map = {f.name: f for f in model._meta.concrete_fields}
    name_to_index, data_rows = read_csv_rows(csv_path)
    ranged_groups, ranged_names_used = compute_ranged_groups(csv_path, name_to_index, field_map)
    ranged_model_fields = set(ranged_groups)
    colmap = COLMAP.get(csv_path.name.lower(), {})
    key_cols = derive_key_columns(name_to_index, colmap, field_map, ranged_model_fields, ranged_names_used)

    fk_lookups = {
        model_field: build_fk_lookup(spec_for_field(field, manifest_by_model), fixture_cache)
        for _, model_field, field in key_cols if field.is_relation
    }

    fixture_rows = load_fixture(spec, fixture_cache)
    fixture_index = build_fixture_index(fixture_rows, key_cols)
    fixture_by_pk = {row["pk"]: row["fields"] for row in fixture_rows}

    counts = dict.fromkeys(REPORT_COUNT_KEYS, 0)
    counts["csv_rows"] = len(data_rows)
    counts["fixture_rows"] = len(fixture_rows)
    patches = {}
    # pk -> {model_field: csv base value} for written rows only, so tests can re-prove
    # the join independently of this function's own bookkeeping.
    base_values = {}
    conflicts_detail = []

    def note(bucket, **extra):
        if detail is None:
            return
        bucket_rows = detail.setdefault(bucket, [])
        if len(bucket_rows) < DETAIL_CAP:
            bucket_rows.append({"k": key_display(row, key_cols, name_to_index), **extra})

    for row in data_rows:
        key = build_key(row, key_cols, name_to_index, fk_lookups)
        if key is None:
            counts["unresolved_fk"] += 1
            note("unresolved_fk", bad=explain_unresolved(row, key_cols, name_to_index, fk_lookups))
            continue

        pks = fixture_index.get(key)
        if not pks:
            counts["unmatched"] += 1
            note("unmatched")
            continue
        if len(pks) > 1:
            counts["ambiguous"] += 1
            note("ambiguous", pks=pks)
            continue

        counts["matched_unique"] += 1
        pk = pks[0]
        fixture_fields = fixture_by_pk[pk]

        row_values = {}
        row_base_values = {}
        mismatch = False
        mismatched_fields = []
        for model_field, (base_ref, min_ref, max_ref) in ranged_groups.items():
            base_raw = get_cell(row, base_ref, name_to_index).strip()
            if not _is_null(base_raw):
                base_val = _to_float_or_none(base_raw)
                if base_val is not None:
                    row_base_values[model_field] = base_val
                fixture_val = fixture_fields.get(model_field)
                if base_val is None:
                    pass
                elif fixture_val is None:
                    # The CSV bounds a value this row doesn't have; a bound beside an empty
                    # base value would describe a number nobody can see.
                    mismatch = True
                    mismatched_fields.append([model_field, base_val, None])
                elif isinstance(fixture_val, (int, float)) and not isinstance(fixture_val, bool):
                    if not math.isclose(base_val, fixture_val, rel_tol=1e-6, abs_tol=1e-9):
                        mismatch = True
                        mismatched_fields.append([model_field, base_val, fixture_val])

            if min_ref is not None:
                min_raw = get_cell(row, min_ref, name_to_index).strip()
                row_values[f"{model_field}_min"] = None if _is_null(min_raw) else _to_float_or_none(min_raw)
            if max_ref is not None:
                max_raw = get_cell(row, max_ref, name_to_index).strip()
                row_values[f"{model_field}_max"] = None if _is_null(max_raw) else _to_float_or_none(max_raw)

        if mismatch:
            counts["base_mismatch"] += 1
            note("base_mismatch", pk=pk, f=mismatched_fields)
            continue

        existing = patches.get(pk)
        if existing is not None:
            conflict = any(
                existing.get(col) is not None and val is not None
                and not math.isclose(existing[col], val, rel_tol=1e-9, abs_tol=1e-9)
                for col, val in row_values.items()
            )
            if conflict:
                counts["conflict"] += 1
                conflicts_detail.append({"pk": pk, "existing": existing, "new": row_values})
                continue
            for col, val in row_values.items():
                if val is not None:
                    existing[col] = val
        else:
            patches[pk] = row_values

        base_values.setdefault(pk, {}).update(row_base_values)
        counts["written"] += 1
        if any(v is not None for v in row_values.values()):
            counts["carrying_bound"] += 1

    new_columns = sum(1 for refs in ranged_groups.values() for r in refs[1:] if r is not None)
    table = {
        "model": spec.model,
        "csv": csv_path.name,
        "fixture": spec.fixture_file,
        "ranged_groups": len(ranged_groups),
        "new_columns": new_columns,
        **counts,
        "conflicts_detail": conflicts_detail,
    }
    return table, patches, ranged_groups, base_values


def aggregate_totals(tables):
    totals = dict.fromkeys(("ranged_groups", "new_columns", *REPORT_COUNT_KEYS), 0)
    for table in tables:
        for key in totals:
            totals[key] += table.get(key, 0)
    return totals


def data_dir():
    return Path(settings.BASE_DIR) / "ipcc" / "data" / "uncertainties"


def iter_mapped_columns():
    """Yields (spec, model, column_name) for every _min/_max column the mapping table
    derives across all 64 CSVs -- the single source of truth models.py must match."""
    manifest_by_fixture = {spec.fixture_file: spec for spec in MANIFEST}
    for csv_path in sorted(data_dir().glob("*.csv")):
        name = resolve_fixture_name(csv_path)
        spec = manifest_by_fixture[f"{name}.json"]
        model = django_apps.get_model(spec.model)
        field_map = {f.name: f for f in model._meta.concrete_fields}
        name_to_index, _data_rows = read_csv_rows(csv_path)
        groups, _names_used = compute_ranged_groups(csv_path, name_to_index, field_map)
        for model_field, (_base_ref, min_ref, max_ref) in groups.items():
            if min_ref is not None:
                yield spec, model, f"{model_field}_min"
            if max_ref is not None:
                yield spec, model, f"{model_field}_max"


def is_publishable(table):
    """Bounds ship per table, all or nothing: one skipped row holds the whole table back
    until its data is fixed, so no table is published with partial coverage."""
    return table["carrying_bound"] > 0 and not any(table[k] for k in SKIPPED_ROW_KEYS)


def compute_all(csv_paths, fixture_cache=None, details=None):
    """Runs the full join across the given CSVs. Returns (tables, results) where
    results is fixture_file -> (spec, patches, groups, base_values), and patches is
    empty for every table that isn't publishable. Writes nothing -- the whole point is
    to let the writer fail loudly before touching a single file (CONTEXT).

    `fixture_cache` (fixture file -> rows in fixture shape) is the join's only data
    source for any file it holds; `apply_uncertainty_ranges` fills it from a database."""
    manifest_by_fixture = {spec.fixture_file: spec for spec in MANIFEST}
    manifest_by_model = {spec.model.lower(): spec for spec in MANIFEST}
    if fixture_cache is None:
        fixture_cache = {}

    tables = []
    results = {}
    for csv_path in csv_paths:
        name = resolve_fixture_name(csv_path)
        spec = manifest_by_fixture.get(f"{name}.json")
        if spec is None:
            raise CommandError(f"{csv_path.name}: resolves to {name}.json, which is not in MANIFEST")
        model = django_apps.get_model(spec.model)
        detail = {} if details is not None else None
        table, patches, groups, base_values = process_csv(
            csv_path, spec, model, manifest_by_model, fixture_cache, detail
        )
        if details is not None:
            detail["groups"] = sorted(groups)
            details[csv_path.name] = detail
        table["published"] = is_publishable(table)
        tables.append(table)
        results[spec.fixture_file] = (spec, patches if table["published"] else {}, groups, base_values)
    return tables, results


def new_columns_for_groups(groups):
    return [
        col
        for model_field, (_base_ref, min_ref, max_ref) in groups.items()
        for col in ((f"{model_field}_min",) if min_ref is not None else ())
        + ((f"{model_field}_max",) if max_ref is not None else ())
    ]


def apply_patches(spec, patches, groups, fixture_cache):
    """Returns the patched fixture payload: every mapped column set on every row (to
    its bound where matched, null otherwise), key order following `_meta.concrete_fields`
    so new keys land after the existing ones exactly as `dump_reference_data` would emit
    them. Reads the pre-run payload from `fixture_cache` -- populated by `compute_all`
    before anything was written -- never from disk post-write."""
    model = django_apps.get_model(spec.model)
    field_order = [f.name for f in model._meta.concrete_fields if not f.primary_key]
    new_columns = new_columns_for_groups(groups)

    new_rows = []
    for row in load_fixture(spec, fixture_cache):
        row_patch = patches.get(row["pk"], {})
        fields = dict(row["fields"])
        for col in new_columns:
            fields[col] = row_patch.get(col)
        ordered_fields = {name: fields[name] for name in field_order if name in fields}
        new_rows.append({"model": row["model"], "pk": row["pk"], "fields": ordered_fields})
    return new_rows


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def fixture_path(spec):
    return Path(settings.BASE_DIR) / spec.app / "fixtures" / spec.fixture_file


def rebuild_combined():
    """Mirrors `dump_reference_data._write_combined`: the concatenation of every
    MANIFEST fixture's current on-disk payload, in MANIFEST order. Reads fresh from
    disk (not the pre-run `fixture_cache`) so it picks up what this run just wrote."""
    combined = []
    for spec in MANIFEST:
        with open(fixture_path(spec), encoding="utf-8") as fh:
            combined.extend(json.load(fh))
    write_json(Path(settings.BASE_DIR) / "api" / "fixtures" / "all_reference_data.json", combined)


class Command(BaseCommand):
    help = "Join the committed IPCC uncertainty CSVs onto the reference fixtures by natural key (D-01/D-02/D-03)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Compute and report only; write nothing.")
        parser.add_argument("--json", dest="json_path", default=None, help="Write the full report as JSON to this path.")
        parser.add_argument("--check", dest="check_path", default=None, help="Compare the computed report against a committed one; exit nonzero on any difference.")
        parser.add_argument("--only", dest="only", default=None, help="Restrict to a single CSV filename.")
        parser.add_argument("--detail", dest="detail_path", default=None, help="Write per-row detail for every skipped row as JSON to this path.")

    def handle(self, *args, **options):
        uncertainties_dir = data_dir()
        csv_paths = sorted(uncertainties_dir.glob("*.csv"))
        if options["only"]:
            csv_paths = [p for p in csv_paths if p.name == options["only"]]
            if not csv_paths:
                raise CommandError(f"no CSV named {options['only']!r} in {uncertainties_dir}")

        fixture_cache = {}
        details = {} if options["detail_path"] else None
        tables, results = compute_all(csv_paths, fixture_cache, details)

        # Compute every patched payload in memory before writing anything -- a
        # failure here must never leave a partial write on disk (CONTEXT).
        new_payloads = {
            fixture_file: (spec, apply_patches(spec, patches, groups, fixture_cache))
            for fixture_file, (spec, patches, groups, _base_values) in results.items()
        }

        totals = aggregate_totals(tables)
        report = {"tables": tables, "totals": totals}
        self._print_report(tables, totals)

        if options["json_path"]:
            write_json(Path(options["json_path"]), report)

        if options["detail_path"]:
            write_json(Path(options["detail_path"]), {"tables": details, "cap": DETAIL_CAP})

        if options["check_path"]:
            with open(options["check_path"], encoding="utf-8") as fh:
                committed = json.load(fh)
            if report != committed:
                raise CommandError(f"report differs from committed baseline at {options['check_path']}")

        if not options["dry_run"]:
            for spec, rows in new_payloads.values():
                write_json(fixture_path(spec), rows)
            rebuild_combined()
            self.stdout.write(self.style.SUCCESS(f"wrote {len(new_payloads)} fixtures + combined."))

    def _print_report(self, tables, totals):
        header = f"{'model':<45}{'groups':>7}{'cols':>6}{'rows':>8}{'written':>9}{'unmatch':>9}{'unres_fk':>9}{'ambig':>7}{'conflict':>9}{'basemis':>9}{'bound':>8}  published"
        self.stdout.write(header)
        for t in tables:
            self.stdout.write(
                f"{t['model']:<45}{t['ranged_groups']:>7}{t['new_columns']:>6}{t['csv_rows']:>8}"
                f"{t['written']:>9}{t['unmatched']:>9}{t['unresolved_fk']:>9}{t['ambiguous']:>7}"
                f"{t['conflict']:>9}{t['base_mismatch']:>9}{t['carrying_bound']:>8}  {'yes' if t['published'] else '-'}"
            )
        self.stdout.write(
            f"{'TOTAL':<45}{totals['ranged_groups']:>7}{totals['new_columns']:>6}{totals['csv_rows']:>8}"
            f"{totals['written']:>9}{totals['unmatched']:>9}{totals['unresolved_fk']:>9}{totals['ambiguous']:>7}"
            f"{totals['conflict']:>9}{totals['base_mismatch']:>9}"
        )
        self.stdout.write(f"tables={len(tables)} matched_unique={totals['matched_unique']} carrying_bound={totals['carrying_bound']}")
