# Drop analysis purpose and project phase

**Date**: 2026-11-12
**Status**: accepted (product owner request)

## Context

NDC framing (#363) added two optional project lookups, `AnalysisPurpose` and `ProjectPhase`, with their own
endpoints, fixtures, Excel metadata rows (16, 17) and a frontend dropdown each. The product owner asked to remove them.

## Decision

Drop them entirely instead of hiding them: the two `Project` foreign keys (and their `HistoricalProject` copies), both
models and tables, the `analysis-purposes/` and `project-phases/` endpoints, the fixtures and their manifest entries,
and the Excel metadata rows. Activity conditionality, the other half of NDC framing, stays.

## Tradeoffs

- Values projects already saved are lost when migration `0323_remove_analysis_purpose_project_phase` runs. Reverting
  the migration recreates empty columns, not the data.
- Rejected: hiding the fields in the UI and the Excel only. Easy to undo, but it leaves dead schema, endpoints and
  fixtures behind with nothing reading them.
- Exports made before this change still import: the serializer ignores the unknown keys (pinned by
  `test_import_of_an_older_export_ignores_the_dropped_fields`).
