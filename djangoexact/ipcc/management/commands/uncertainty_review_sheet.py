"""Build the review workbook for every base-value disagreement that holds an IPCC
uncertainty table back from publishing.

A disagreement means the uncertainty CSV prints one default and the reference fixture
(a snapshot of the production database) holds another, so the CSV's range cannot be
shown beside the default. The workbook has one sheet per held-back table and one row per
disagreeing CSV line, laying the whole CSV line and the whole database row side by side,
field by field, so a reviewer never has to open the CSV or query the database.

    python manage.py uncertainty_review_sheet
"""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ipcc.management.commands import import_uncertainties as iu

DEFAULT_OUTPUT = Path("ipcc") / "data" / "uncertainties_review" / "base_mismatch_review.xlsx"

DECISIONS = {
    "keep_db": "The database value is right and the CSV range still applies to it. The CSV base is corrected to the database value; the range then publishes. Calculation results do not change.",
    "use_csv": "The CSV value is right and the database default is wrong. The database default changes, which changes results for every project using it, so it needs a pinned-number test and sign-off.",
    "drop_row": "The range cannot be trusted for this row. The CSV row is removed, so this default shows no range but the rest of the table can publish.",
    "needs_research": "Not settled yet. The table stays held back.",
}

# Only meanings stated by the cited IPCC tables; anything less certain is left blank
# rather than risk steering a reviewer with a wrong unit.
FIELD_MEANINGS = {
    ("ipcc.CropNitrousEstimationDefaultFactor", "rs_t"): "RS(T): below-ground to above-ground biomass ratio (IPCC 2019, table 11.1A)",
    ("ipcc.CropNitrousEstimationDefaultFactor", "n_bg_t"): "N_BG(T): N content of below-ground residues, kg N per kg dry matter (IPCC 2019, table 11.1A)",
    ("ipcc.ForestCombustionFactor", "co2"): "CO2 emission factor, g per kg dry matter burnt (IPCC 2019, table 2.5)",
    ("ipcc.ForestCombustionFactor", "ch4"): "CH4 emission factor, g per kg dry matter burnt (IPCC 2019, table 2.5)",
    ("ipcc.ForestCombustionFactor", "n2o"): "N2O emission factor, g per kg dry matter burnt (IPCC 2019, table 2.5)",
    ("ipcc.ForestCombustionFactor", "value"): "Combustion factor, fraction of biomass consumed (IPCC 2019, table 2.6)",
}

FIELD_BLOCK = ("CSV", "CSV min", "CSV max", "DB", "DB min", "DB max", "DB - CSV", "diff %", "DB in CSV range")
REVIEW_COLUMNS = ("decision", "source_checked", "reviewer_notes")
ZERO_VS_EMPTY = "DB empty, CSV 0 with no width"

BOLD = Font(bold=True)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
MISMATCH_FILL = PatternFill("solid", fgColor="F8CBAD")
CSV_FILL = PatternFill("solid", fgColor="DDEBF7")
DB_FILL = PatternFill("solid", fgColor="E2EFDA")
DECISION_FILL = PatternFill("solid", fgColor="FFF2CC")
HEADER_FILL = PatternFill("solid", fgColor="D9D9D9")
BLOCK_EDGE = Border(left=Side(style="medium"))
CELL_FILLS = {**dict.fromkeys(FIELD_BLOCK[:3], CSV_FILL), **dict.fromkeys(FIELD_BLOCK[3:6], DB_FILL)}


def read_numbered_rows(csv_path):
    """Data rows with their file line numbers, skipping blank rows as read_csv_rows does."""
    with open(csv_path, encoding=iu.csv_encoding(csv_path), newline="") as fh:
        reader = csv.reader(fh)
        next(reader)
        for row in reader:
            if any(c.strip() for c in row):
                yield reader.line_num, row


def in_csv_range(db_value, csv_value, lower, upper):
    if db_value is None:
        # Hundreds of not-applicable combinations look like this; naming them lets a
        # reviewer filter and settle them in one go instead of row by row.
        if csv_value == 0 and lower in (0, None) and upper in (0, None):
            return ZERO_VS_EMPTY
        return "DB empty"
    if csv_value is None:
        return "CSV empty"
    if lower is None or upper is None:
        return "no CSV range"
    return "yes" if lower <= db_value <= upper else "no"


class TableReview:
    """One held-back table: its CSV and fixture joined row by row, for the review sheet."""

    def __init__(self, table, mismatches, fixture_cache):
        by_fixture = {s.fixture_file: s for s in iu.MANIFEST}
        self.by_model = {s.model.lower(): s for s in iu.MANIFEST}
        self.cache = fixture_cache
        self.table = table
        self.mismatches = mismatches
        self.spec = by_fixture[table["fixture"]]
        model = iu.django_apps.get_model(self.spec.model)
        self.csv_path = iu.data_dir() / table["csv"]
        self.field_map = {f.name: f for f in model._meta.concrete_fields}
        self.n2i, _rows = iu.read_csv_rows(self.csv_path)
        self.groups, ranged_names = iu.compute_ranged_groups(self.csv_path, self.n2i, self.field_map)
        colmap = iu.COLMAP.get(self.csv_path.name.lower(), {})
        self.key_cols = iu.derive_key_columns(self.n2i, colmap, self.field_map, set(self.groups), ranged_names)

        source_col = next((n for n in self.n2i if "source" in n.lower()), None)
        self.source = source_col.split(":", 1)[-1].strip() if source_col else ""
        key_names = {name for name, _, _ in self.key_cols}
        self.extra_csv_cols = [n for n in self.n2i if n not in key_names | ranged_names | {"id", source_col}]

        fixture_rows = iu.load_fixture(self.spec, fixture_cache)
        self.db_rows = {r["pk"]: r["fields"] for r in fixture_rows}
        covered = {mf for _, mf, _ in self.key_cols} | {
            name for f in self.groups for name in (f, f"{f}_min", f"{f}_max")
        }
        self.extra_db_fields = [
            name for name, value in (fixture_rows[0]["fields"].items() if fixture_rows else ())
            if name not in covered and not isinstance(value, list)
        ]

        fk = {mf: iu.build_fk_lookup(iu.spec_for_field(f, self.by_model), fixture_cache) for _, mf, f in self.key_cols if f.is_relation}
        index = iu.build_fixture_index(fixture_rows, self.key_cols)
        self.lines_by_pk = {}
        for line_no, row in read_numbered_rows(self.csv_path):
            key = iu.build_key(row, self.key_cols, self.n2i, fk)
            pks = index.get(key) if key is not None else None
            if pks and len(pks) == 1:
                self.lines_by_pk.setdefault(pks[0], []).append((line_no, row, key))

    def name_of(self, field, value):
        if value is None or not field.is_relation:
            return value
        rows = iu.load_fixture(iu.spec_for_field(field, self.by_model), self.cache)
        label = next((c for c in ("name", "value", "label") if rows and c in rows[0]["fields"]), None)
        names = {r["pk"]: r["fields"].get(label) for r in rows} if label else {}
        return names.get(value, value)

    def number(self, row, ref):
        raw = iu.get_cell(row, ref, self.n2i).strip()
        return None if iu._is_null(raw) else iu._to_float_or_none(raw)

    def csv_line(self, mismatch):
        """The CSV line joined to the mismatching pk whose bases are the reported ones."""
        for line_no, row, key in self.lines_by_pk.get(mismatch["pk"], []):
            if all(self.number(row, self.groups[f][0]) == csv_value for f, csv_value, _db in mismatch["f"]):
                return line_no, row, key
        raise LookupError(f"{self.csv_path.name}: no line joins pk {mismatch['pk']} with {mismatch['f']}")

    def headers(self):
        """(group label, column label) pairs, in sheet order."""
        cols = [("Row", "review_id"), ("Row", "csv_line"), ("Row", "csv_id"), ("Row", "db_pk")]
        cols += [("What the row describes", name) for name, _, _ in self.key_cols]
        cols += [("What the row describes", "fields that disagree")]
        for field in self.groups:
            meaning = FIELD_MEANINGS.get((self.table["model"], field))
            label = f"{field}: {meaning}" if meaning else field
            cols += [(label, part) for part in FIELD_BLOCK]
        cols += [("Other CSV columns", name) for name in self.extra_csv_cols]
        cols += [("Other DB fields", name) for name in self.extra_db_fields]
        cols += [("Review", name) for name in REVIEW_COLUMNS]
        return cols

    def rows(self, first_id):
        """Yields (cells, columns to highlight) per disagreeing CSV line."""
        for offset, mismatch in enumerate(self.mismatches):
            line_no, row, key = self.csv_line(mismatch)
            db = self.db_rows[mismatch["pk"]]
            disagreeing = [f for f, _csv, _db in mismatch["f"]]
            cells = [first_id + offset, line_no, iu.get_cell(row, "id", self.n2i).strip() or None, mismatch["pk"]]
            cells += [self.name_of(field, part) for (_, _, field), part in zip(self.key_cols, key)]
            cells.append(", ".join(disagreeing))
            highlight = []
            for field, (base_ref, min_ref, max_ref) in self.groups.items():
                csv_value, lower, upper = (self.number(row, ref) for ref in (base_ref, min_ref, max_ref))
                db_value = db.get(field)
                diff = None if db_value is None or csv_value is None else round(db_value - csv_value, 10)
                pct = None if diff is None or not csv_value else round(diff / abs(csv_value) * 100, 2)
                if field in disagreeing:
                    highlight += [len(cells) + 1, len(cells) + 4]
                cells += [csv_value, lower, upper, db_value, db.get(f"{field}_min"), db.get(f"{field}_max"),
                          diff, pct, in_csv_range(db_value, csv_value, lower, upper)]
            cells += [iu.get_cell(row, name, self.n2i).strip() or None for name in self.extra_csv_cols]
            cells += [self.name_of(self.field_map[name], db.get(name)) if name in self.field_map else db.get(name)
                      for name in self.extra_db_fields]
            cells += [None] * len(REVIEW_COLUMNS)
            yield cells, highlight


def sheet_title(model, taken):
    title = model.split(".", 1)[-1][:31]
    while title in taken:
        title = title[:29] + f"{len(taken):02d}"
    taken.add(title)
    return title


def write_table_sheet(ws, review, first_id):
    headers = review.headers()
    groups = [g for g, _ in headers]
    for i, (group, label) in enumerate(headers, start=1):
        ws.cell(2, i, label)
    start = 1
    for i in range(2, len(groups) + 2):
        if i > len(groups) or groups[i - 1] != groups[start - 1]:
            ws.cell(1, start, groups[start - 1])
            if i - 1 > start:
                ws.merge_cells(start_row=1, start_column=start, end_row=1, end_column=i - 1)
            start = i
    for row in ws.iter_rows(min_row=1, max_row=2):
        for cell in row:
            cell.font, cell.alignment, cell.fill = BOLD, CENTER, HEADER_FILL

    count = 0
    for cells, highlight in review.rows(first_id):
        ws.append(cells)
        r = ws.max_row
        for i, (group, label) in enumerate(headers, start=1):
            fill = CELL_FILLS.get(label) or (DECISION_FILL if group == "Review" else None)
            if fill:
                ws.cell(r, i).fill = fill
        for col in highlight:
            ws.cell(r, col).fill = MISMATCH_FILL
        count += 1

    for i, (group, label) in enumerate(headers, start=1):
        if i > 1 and groups[i - 2] != group:
            for (cell,) in ws.iter_rows(min_col=i, max_col=i):
                cell.border = BLOCK_EDGE
        wide = group in ("Other CSV columns", "Other DB fields", "Review") or label == "fields that disagree"
        ws.column_dimensions[get_column_letter(i)].width = 28 if wide else 18 if group == "What the row describes" else 11
    ws.row_dimensions[1].height = 45
    ws.row_dimensions[2].height = 30

    first_field_col = next(i for i, (_g, label) in enumerate(headers, start=1) if label == FIELD_BLOCK[0])
    ws.freeze_panes = ws.cell(3, first_field_col)
    ws.auto_filter.ref = f"A2:{get_column_letter(len(headers))}{max(ws.max_row, 2)}"

    decision_col = get_column_letter(len(headers) - len(REVIEW_COLUMNS) + 1)
    choices = DataValidation(type="list", formula1='"' + ",".join(DECISIONS) + '"', allow_blank=True)
    ws.add_data_validation(choices)
    choices.add(f"{decision_col}3:{decision_col}{max(ws.max_row, 3)}")
    return count


def write_instructions(ws):
    lines = [
        ("Why this file exists", True),
        ("Each uncertainty CSV publishes a range (min, max) for an IPCC default. A range is only shown beside a default when the CSV prints the same default the tool calculates with, so it describes the number users see. One disagreement holds its whole table back. Same-number-different-precision cases (2.11 vs 2.1) already count as agreeing and are not listed.", False),
        ("", False),
        ("How a table sheet is laid out", True),
        ("One row per CSV line that disagrees with the database. Left to right:", False),
        ("Row: review_id (refer to the row by it), csv_line (line in the CSV, header is line 1), csv_id (the CSV's own id), db_pk (database row it was joined to).", False),
        ("What the row describes: every natural-key column with references shown by name, then which fields disagree.", False),
        (f"One block per field, side by side: {', '.join(FIELD_BLOCK)}. Blue cells come from the uncertainty CSV, green cells from the database (reference fixture refreshed from production), red cells are the values that disagree.", False),
        (f"DB in CSV range: yes / no; '{ZERO_VS_EMPTY}' (no database default, CSV prints 0 with a 0 to 0 range, usually a combination that does not apply); 'DB empty'; 'no CSV range'.", False),
        ("Other CSV columns and Other DB fields: the rest of both rows, so nothing needs looking up.", False),
        ("Review: decision (dropdown), source_checked, reviewer_notes.", False),
        ("", False),
        ("How to review a row", True),
        ("1. Look the value up in the IPCC source listed on the Summary sheet.", False),
        ("2. Compare it with the blue (CSV) and green (DB) values in the red-marked field.", False),
        ("3. Pick a decision and note where you checked in source_checked.", False),
        (f"Tip: filter 'DB in CSV range' on '{ZERO_VS_EMPTY}' to settle the not-applicable rows together.", False),
        ("", False),
        ("Decisions", True),
        *((f"{name}: {meaning}", False) for name, meaning in DECISIONS.items()),
        ("", False),
        ("Regenerate with: python manage.py uncertainty_review_sheet (from djangoexact/). Decisions typed here are not carried over, so copy them out first.", False),
    ]
    for text, heading in lines:
        ws.append([text])
        cell = ws.cell(ws.max_row, 1)
        cell.font, cell.alignment = Font(bold=heading), WRAP
    ws.column_dimensions["A"].width = 140


def write_summary(ws, entries):
    ws.append(["sheet", "table", "csv_file", "rows_to_review", "ranges_held_back", "ipcc_source"])
    for cell in ws[1]:
        cell.font, cell.fill = BOLD, HEADER_FILL
    for title, review, count in entries:
        ws.append([title, review.table["model"], review.table["csv"], count, review.table["carrying_bound"], review.source])
        link = ws.cell(ws.max_row, 1)
        link.hyperlink, link.style = f"#'{title}'!A1", "Hyperlink"
        ws.cell(ws.max_row, 6).alignment = WRAP
    for letter, width in zip("ABCDEF", (32, 40, 42, 15, 17, 100)):
        ws.column_dimensions[letter].width = width


class Command(BaseCommand):
    help = "Write the review workbook for every base-value disagreement holding an IPCC uncertainty table back."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Workbook path, relative to djangoexact/.")

    def handle(self, *args, **options):
        fixture_cache, details = {}, {}
        cap = iu.DETAIL_CAP
        iu.DETAIL_CAP = 10**9  # The committed detail report is capped; a review needs every row.
        try:
            tables, _results = iu.compute_all(sorted(iu.data_dir().glob("*.csv")), fixture_cache, details)
        finally:
            iu.DETAIL_CAP = cap

        wb = Workbook()
        wb.active.title = "How to review"
        write_instructions(wb.active)
        summary = wb.create_sheet("Summary")

        entries, taken, next_id = [], set(), 1
        for table in tables:
            mismatches = details[table["csv"]].get("base_mismatch", [])
            if table["carrying_bound"] == 0 or not mismatches:
                continue
            review = TableReview(table, mismatches, fixture_cache)
            title = sheet_title(table["model"], taken)
            count = write_table_sheet(wb.create_sheet(title), review, next_id)
            entries.append((title, review, count))
            next_id += count
        write_summary(summary, entries)

        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output)
        self.stdout.write(self.style.SUCCESS(f"{next_id - 1} rows across {len(entries)} tables written to {output}"))
