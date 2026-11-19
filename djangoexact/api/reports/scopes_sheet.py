"""GHG Protocol scope sheets of the Excel report: "Scope Assignment", "Results by Scope" and the hidden "Scope Lists".

The rows come from `scope_rows`. Results by Scope only holds SUMIFS formulas over Scope Assignment, so a scope
picked in a dropdown moves its row's totals. The balance only appears as "Change in net" (with net minus without
net), never as scope emissions.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Sequence

from openpyxl import Workbook
from openpyxl.styles import Font, Protection
from openpyxl.utils import absolute_coordinate, get_column_letter, quote_sheetname
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from api.scopes import Scope
from api.utilities import ScenarioTypes

from .data_types import ProjectResult
from .excel_manager import write_literal_cell
from .scope_rows import REPORTED_SCENARIOS, ActivitySets, ScopeRow, build_scope_rows, collect_activity_sets

WS_SCOPE_ASSIGNMENT = "Scope Assignment"
WS_RESULTS_BY_SCOPE = "Results by Scope"
WS_SCOPE_LISTS = "Scope Lists"

SCOPE_LABELS: dict[Scope, str] = {
    Scope.SCOPE_1: "Scope 1",
    Scope.SCOPE_2: "Scope 2",
    Scope.SCOPE_3: "Scope 3",
    Scope.OUTSIDE_SCOPES: "Outside scopes",
    Scope.UNASSIGNED: "Unassigned",
}
ALWAYS_REPORTED_SCOPES = (Scope.SCOPE_1, Scope.SCOPE_2, Scope.SCOPE_3, Scope.OUTSIDE_SCOPES)
SCENARIO_LABELS = {ScenarioTypes.WITH: "With project", ScenarioTypes.WITHOUT: "Without project"}


class AssignmentCol(IntEnum):
    """Columns of the Scope Assignment sheet. The last three are hidden helper keys for the SUMIFS formulas."""

    ACTIVITY = 1
    MODULE = 2
    ENTRY = 3
    FLUX = 4
    GAS = 5
    SCENARIO = 6
    SCOPE = 7
    DEFAULT_SCOPE = 8
    USER_SELECTABLE = 9
    SCOPE3_CATEGORY = 10
    NOTE = 11
    EMISSIONS = 12
    REMOVALS = 13
    NET = 14
    SCENARIO_CODE = 15
    ACTIVITY_INDEX = 16
    MODULE_INDEX = 17


# (header, column width)
ASSIGNMENT_COLUMNS = {
    AssignmentCol.ACTIVITY: ("Activity", 24),
    AssignmentCol.MODULE: ("Module", 20),
    AssignmentCol.ENTRY: ("Entry", 28),
    AssignmentCol.FLUX: ("Flux", 30),
    AssignmentCol.GAS: ("Gas", 8),
    AssignmentCol.SCENARIO: ("Scenario", 16),
    AssignmentCol.SCOPE: ("Scope", 15),
    AssignmentCol.DEFAULT_SCOPE: ("Default scope", 15),
    AssignmentCol.USER_SELECTABLE: ("User-selectable", 15),
    AssignmentCol.SCOPE3_CATEGORY: ("Scope 3 category", 16),
    AssignmentCol.NOTE: ("Note", 60),
    AssignmentCol.EMISSIONS: ("Emissions (tCO2e)", 18),
    AssignmentCol.REMOVALS: ("Removals (tCO2e)", 18),
    AssignmentCol.NET: ("Net (tCO2e)", 18),
    AssignmentCol.SCENARIO_CODE: ("Scenario code", 14),
    AssignmentCol.ACTIVITY_INDEX: ("Activity index", 14),
    AssignmentCol.MODULE_INDEX: ("Module index", 14),
}
HELPER_COLUMNS = (AssignmentCol.SCENARIO_CODE, AssignmentCol.ACTIVITY_INDEX, AssignmentCol.MODULE_INDEX)

ASSIGNMENT_ROW_HEADER = 4
ASSIGNMENT_FIRST_DATA_ROW = 5

ASSIGNMENT_TITLE = (
    "GHG Protocol scope of each gross flux, per scenario: emissions are the positive yearly values and removals "
    "the negative ones, summed over the years of the Results sheet. Scopes never apply to the balance."
)
GROSS_SPLIT_NOTE = (
    "Gross figures are split per entry, so entries of opposite sign in the same year show larger emissions and "
    "removals than netting them at module level would; net is unaffected."
)
PROTECTION_NOTE = (
    "This sheet is protected (no password) only to prevent accidental edits; pick a scope in the Scope column "
    "where a list is offered. EX-ACT holds the authoritative values: choices made in this file are not saved "
    "back to EX-ACT."
)
NO_ROWS_NOTE = "This project has no emissions or removals to assign to a scope."
DROPDOWN_ERROR_TITLE = "Scope not allowed"
DROPDOWN_ERROR = "Pick one of the scopes offered in the list for this flux."

RESULTS_BY_SCOPE_TITLE = (
    "Gross emissions and removals by GHG Protocol scope (tCO2e), summed from the Scope Assignment sheet. "
    "Change in net is With net minus Without net."
)
# Each scenario block of a Results by Scope row: emissions, removals, then net.
SCENARIO_VALUE_HEADERS = ("Emissions", "Removals", "Net")
COLUMNS_PER_SCENARIO = len(SCENARIO_VALUE_HEADERS)
FIRST_VALUE_COLUMN = 2
CHANGE_IN_NET_COLUMN = FIRST_VALUE_COLUMN + COLUMNS_PER_SCENARIO * len(REPORTED_SCENARIOS)
RESULTS_HEADERS = (
    "Scope",
    *(f"{SCENARIO_LABELS[scenario]}: {header}" for scenario in REPORTED_SCENARIOS for header in SCENARIO_VALUE_HEADERS),
    "Change in net",
)
RESULTS_FIRST_BLOCK_ROW = 3
PROJECT_BLOCK_TITLE = "Project"
BY_ACTIVITY_TITLE = "By activity"
BY_MODULE_TITLE = "By module"
SECTION_TITLE_FONT_SIZE = 13
TOTAL_CHANGE_LABEL = "Total change in net (all scopes)"
TOTAL_CHANGE_NOTE = "Equals the cumulative balance of the last year on the Results sheet."
NUMBER_FORMAT = "#,##0.00"

Criteria = Sequence[tuple[AssignmentCol, str | int]]


def scope_list_ranges(rows: Sequence[ScopeRow]) -> dict[tuple[Scope, ...], str]:
    """The Scope Lists range of each distinct selectable scope set, one column per set in order of appearance.

    Dropdowns read a range, not an inline list: inline lists are capped at 255 characters and split on commas.
    """
    ranges: dict[tuple[Scope, ...], str] = {}
    for row in rows:
        allowed = row.rule.allowed
        if row.is_user_selectable and allowed not in ranges:
            letter = get_column_letter(len(ranges) + 1)
            coordinates = absolute_coordinate(f"{letter}1:{letter}{len(allowed)}")
            ranges[allowed] = f"{quote_sheetname(WS_SCOPE_LISTS)}!{coordinates}"
    return ranges


def _write_scope_lists(wb: Workbook, list_ranges: dict[tuple[Scope, ...], str]) -> None:
    ws = wb.create_sheet(WS_SCOPE_LISTS)
    ws.sheet_state = "hidden"
    for column, allowed in enumerate(list_ranges, start=1):
        for row_number, scope in enumerate(allowed, start=1):
            ws.cell(row=row_number, column=column, value=SCOPE_LABELS[scope])


def _write_assignment_row(ws: Worksheet, row_number: int, row: ScopeRow) -> None:
    rule = row.rule
    note = f"Pending review: {rule.note}" if rule.pending_review else rule.note
    for column, text in (
        (AssignmentCol.ACTIVITY, row.activity_title),
        (AssignmentCol.MODULE, row.module_title),
        (AssignmentCol.ENTRY, row.entry_label),
        (AssignmentCol.FLUX, row.flux_label),
        (AssignmentCol.GAS, row.gas_label),
        (AssignmentCol.NOTE, note),
    ):
        write_literal_cell(ws, row_number, column, str(text))
    ws.cell(row=row_number, column=AssignmentCol.SCENARIO, value=SCENARIO_LABELS[row.scenario])
    ws.cell(row=row_number, column=AssignmentCol.SCOPE, value=SCOPE_LABELS[rule.default])
    ws.cell(row=row_number, column=AssignmentCol.DEFAULT_SCOPE, value=SCOPE_LABELS[rule.default])
    ws.cell(row=row_number, column=AssignmentCol.USER_SELECTABLE, value="Yes" if row.is_user_selectable else "No")
    ws.cell(row=row_number, column=AssignmentCol.SCOPE3_CATEGORY, value=rule.scope3_category)
    ws.cell(row=row_number, column=AssignmentCol.EMISSIONS, value=row.emissions).number_format = NUMBER_FORMAT
    ws.cell(row=row_number, column=AssignmentCol.REMOVALS, value=row.removals).number_format = NUMBER_FORMAT
    emissions = f"{get_column_letter(AssignmentCol.EMISSIONS)}{row_number}"
    removals = f"{get_column_letter(AssignmentCol.REMOVALS)}{row_number}"
    ws.cell(row=row_number, column=AssignmentCol.NET, value=f"={emissions}+{removals}").number_format = NUMBER_FORMAT
    ws.cell(row=row_number, column=AssignmentCol.SCENARIO_CODE, value=row.scenario.value)
    ws.cell(row=row_number, column=AssignmentCol.ACTIVITY_INDEX, value=row.activity_index)
    ws.cell(row=row_number, column=AssignmentCol.MODULE_INDEX, value=row.module_index)


def _write_assignment(wb: Workbook, rows: Sequence[ScopeRow], list_ranges: dict[tuple[Scope, ...], str]) -> int:
    """Write the Scope Assignment sheet and return its last data row (the bound of every SUMIFS range)."""
    ws = wb.create_sheet(WS_SCOPE_ASSIGNMENT)
    for row_number, text in enumerate((ASSIGNMENT_TITLE, GROSS_SPLIT_NOTE, PROTECTION_NOTE), start=1):
        ws.cell(row=row_number, column=1, value=text)
    ws.cell(row=1, column=1).font = Font(bold=True)
    for column, (header, width) in ASSIGNMENT_COLUMNS.items():
        ws.cell(row=ASSIGNMENT_ROW_HEADER, column=column, value=header).font = Font(bold=True)
        ws.column_dimensions[get_column_letter(column)].width = width
    for column in HELPER_COLUMNS:
        ws.column_dimensions[get_column_letter(column)].hidden = True
    ws.freeze_panes = ws.cell(row=ASSIGNMENT_FIRST_DATA_ROW, column=1)

    if not rows:
        ws.cell(row=ASSIGNMENT_FIRST_DATA_ROW, column=1, value=NO_ROWS_NOTE)

    validations = {
        allowed: DataValidation(
            type="list", formula1=reference, allow_blank=False,
            showErrorMessage=True, errorTitle=DROPDOWN_ERROR_TITLE, error=DROPDOWN_ERROR,
        )
        for allowed, reference in list_ranges.items()
    }
    for row_number, row in enumerate(rows, start=ASSIGNMENT_FIRST_DATA_ROW):
        _write_assignment_row(ws, row_number, row)
        if row.is_user_selectable:
            scope_cell = ws.cell(row=row_number, column=AssignmentCol.SCOPE)
            scope_cell.protection = Protection(locked=False)
            validations[row.rule.allowed].add(scope_cell)
    for validation in validations.values():
        ws.add_data_validation(validation)
    ws.protection.sheet = True
    return ASSIGNMENT_FIRST_DATA_ROW + max(len(rows), 1) - 1


def sumifs_formula(sum_column: AssignmentCol, criteria: Criteria, last_row: int) -> str:
    """SUMIFS over bounded absolute Scope Assignment ranges, keyed on our own codes and labels only.

    User-entered names never become criteria: SUMIFS reads * ? < > = in a criterion as operators or wildcards.
    """
    def column_range(column: AssignmentCol) -> str:
        letter = get_column_letter(column)
        coordinates = absolute_coordinate(f"{letter}{ASSIGNMENT_FIRST_DATA_ROW}:{letter}{last_row}")
        return f"{quote_sheetname(WS_SCOPE_ASSIGNMENT)}!{coordinates}"

    def criterion(value: str | int) -> str:
        return f'"{value}"' if isinstance(value, str) else str(value)

    arguments = [column_range(sum_column)]
    for column, value in criteria:
        arguments += [column_range(column), criterion(value)]
    return f"=SUMIFS({','.join(arguments)})"


def _write_results_block(
    ws: Worksheet, first_row: int, title: str, criteria: Criteria, scopes: Sequence[Scope], last_row: int
) -> tuple[int, int]:
    """Write one block (title, headers, a row per scope); returns its first and last scope rows."""
    write_literal_cell(ws, first_row, 1, title).font = Font(bold=True)
    for column, header in enumerate(RESULTS_HEADERS, start=1):
        ws.cell(row=first_row + 1, column=column, value=header).font = Font(bold=True)
    first_scope_row = first_row + 2
    for row_number, scope in enumerate(scopes, start=first_scope_row):
        ws.cell(row=row_number, column=1, value=SCOPE_LABELS[scope])
        net_cells = []
        for block, scenario in enumerate(REPORTED_SCENARIOS):
            first_column = FIRST_VALUE_COLUMN + block * COLUMNS_PER_SCENARIO
            emissions, removals, net = (
                f"{get_column_letter(first_column + offset)}{row_number}" for offset in range(COLUMNS_PER_SCENARIO)
            )
            keys = [
                (AssignmentCol.SCOPE, SCOPE_LABELS[scope]), (AssignmentCol.SCENARIO_CODE, scenario.value), *criteria
            ]
            ws[emissions] = sumifs_formula(AssignmentCol.EMISSIONS, keys, last_row)
            ws[removals] = sumifs_formula(AssignmentCol.REMOVALS, keys, last_row)
            ws[net] = f"={emissions}+{removals}"
            net_cells.append(net)
        with_net, without_net = net_cells
        ws.cell(row=row_number, column=CHANGE_IN_NET_COLUMN, value=f"={with_net}-{without_net}")
        for value_column in range(FIRST_VALUE_COLUMN, CHANGE_IN_NET_COLUMN + 1):
            ws.cell(row=row_number, column=value_column).number_format = NUMBER_FORMAT
    return first_scope_row, first_scope_row + len(scopes) - 1


def _write_section_title(ws: Worksheet, row: int, title: str) -> None:
    ws.cell(row=row, column=1, value=title).font = Font(bold=True, size=SECTION_TITLE_FONT_SIZE)


def _write_results_by_scope(
    wb: Workbook, activities: Sequence[ActivitySets], rows: Sequence[ScopeRow], last_row: int
) -> None:
    ws = wb.create_sheet(WS_RESULTS_BY_SCOPE)
    ws.cell(row=1, column=1, value=RESULTS_BY_SCOPE_TITLE).font = Font(bold=True)
    ws.column_dimensions["A"].width = 34
    for column in range(FIRST_VALUE_COLUMN, CHANGE_IN_NET_COLUMN + 1):
        ws.column_dimensions[get_column_letter(column)].width = 18
    has_unassigned = any(row.rule.default is Scope.UNASSIGNED for row in rows)
    scopes = (*ALWAYS_REPORTED_SCOPES, Scope.UNASSIGNED) if has_unassigned else ALWAYS_REPORTED_SCOPES
    change_column = get_column_letter(CHANGE_IN_NET_COLUMN)

    first, last = _write_results_block(ws, RESULTS_FIRST_BLOCK_ROW, PROJECT_BLOCK_TITLE, [], scopes, last_row)
    total_row = last + 1
    ws.cell(row=total_row, column=1, value=TOTAL_CHANGE_LABEL).font = Font(bold=True)
    total = ws[f"{change_column}{total_row}"]
    total.value = f"=SUM({change_column}{first}:{change_column}{last})"
    total.number_format = NUMBER_FORMAT
    ws.cell(row=total_row + 1, column=1, value=TOTAL_CHANGE_NOTE)

    next_row = total_row + 3
    _write_section_title(ws, next_row, BY_ACTIVITY_TITLE)
    next_row += 1
    for activity in activities:
        criteria = [(AssignmentCol.ACTIVITY_INDEX, activity.index)]
        _, last = _write_results_block(ws, next_row, activity.title, criteria, scopes, last_row)
        next_row = last + 2

    _write_section_title(ws, next_row, BY_MODULE_TITLE)
    next_row += 1
    for activity in activities:
        for module in activity.modules:
            criteria = [(AssignmentCol.MODULE_INDEX, module.index)]
            title = f"{activity.title} / {module.title}"
            _, last = _write_results_block(ws, next_row, title, criteria, scopes, last_row)
            next_row = last + 2


def write_scope_sheets(wb: Workbook, result: ProjectResult) -> None:
    """Append Scope Assignment, Results by Scope and the hidden Scope Lists to the report workbook.

    The year window is the Results sheet's: one column per year from the start year to the last year.
    """
    activities = collect_activity_sets(result)
    rows = build_scope_rows(activities, year_count=result.last_year - result.start_year)
    list_ranges = scope_list_ranges(rows)
    assignment_last_row = _write_assignment(wb, rows, list_ranges)
    _write_results_by_scope(wb, activities, rows, assignment_last_row)
    _write_scope_lists(wb, list_ranges)
