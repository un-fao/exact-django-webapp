"""Catalog of the reports this app can render.

Report selection is a closed set, not a filesystem lookup. Callers pass a
report name that arrived on a request; without this module they interpolated
it straight into a template path, so the only thing standing between user
input and the template loader was an os.path.exists probe -- which on the
public, unauthenticated path doubled as a file-existence oracle.

Adding a report is one entry in REPORTS and LABELS plus the template file it
names.
"""
from __future__ import annotations

import re

REPORTS: dict[str, frozenset[str]] = {
    "fao": frozenset({"en", "es", "fr"}),
    "ifad": frozenset({"en"}),
}

# Display names for the frontend select. English only: the frontend can map
# the id to its own translation and fall back to this.
LABELS: dict[str, str] = {
    "fao": "EX-ACT report",
    "ifad": "IFAD annex",
}


class UnknownReport(Exception):
    """Requested report name or language is not in the catalog."""


def options() -> list[dict]:
    """Return the catalog as select options: id (the `template` value), label, languages."""
    return [
        {"id": report, "label": LABELS[report], "languages": sorted(langs)}
        for report, langs in sorted(REPORTS.items())
    ]


def report_filename(project_name: str, report: str | None) -> str:
    """Download filename shared by the sync and async paths: `{name}-{report}-report.pdf`, or the Excel results.

    Separators and control characters become "-" so the name stays one file
    name. Quoting and non-ASCII are left to django.utils.http.content_disposition_header.
    """
    name = re.sub(r"[\\/\x00-\x1f\x7f]", "-", project_name or "").strip() or "project"
    if report:
        return f"{name}-{report}-report.pdf"
    return f"{name}-results-report.xlsx"


def resolve_template(report: str, lang: str) -> str:
    """Return the template path for a report, or raise UnknownReport.

    The failure messages deliberately do not echo `report` back: it is
    unvalidated user input and these strings reach both the API response body
    and the logs.
    """
    langs = REPORTS.get(report)
    if langs is None:
        raise UnknownReport(f"Unknown report. Available: {', '.join(sorted(REPORTS))}")
    if lang not in langs:
        raise UnknownReport(f"Report is not available in '{lang}'. Available: {', '.join(sorted(langs))}")
    return f"reports/{report}_{lang}.html"
