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
