---
schema_version: 1
open_count: 2
waived_count: 0
fixed_count: 0
total_count: 2
last_updated: 2026-08-10T15:38:57.194Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 260810-nlo | unrun-verify | djangoexact/api/tests/test_project_results_cache_api.py |  | APITestCase suite for the project results cache (hit/miss equality, dedupe, stamp-driven recompute, cached=false bypass, activity-order collapsing, permission gate) needs Postgres and was not run in this sandbox | open |  | 2026-08-10T15:38:52.823Z |  |
| 2 | 260810-nlo | unrun-verify | djangoexact/api/tests/unit/project.py | 1404 | Finalized-project cache carve-out pinning test needs Postgres; new invalidate_project_result_caches mirrors the same is_finalized=False filter but was not exercised against this test in this sandbox | open |  | 2026-08-10T15:38:57.194Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "260810-nlo",
    "file": "djangoexact/api/tests/test_project_results_cache_api.py",
    "line": null,
    "description": "APITestCase suite for the project results cache (hit/miss equality, dedupe, stamp-driven recompute, cached=false bypass, activity-order collapsing, permission gate) needs Postgres and was not run in this sandbox",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-10T15:38:52.823Z",
    "resolved_at": null
  },
  {
    "id": 2,
    "kind": "unrun-verify",
    "phase": "260810-nlo",
    "file": "djangoexact/api/tests/unit/project.py",
    "line": 1404,
    "description": "Finalized-project cache carve-out pinning test needs Postgres; new invalidate_project_result_caches mirrors the same is_finalized=False filter but was not exercised against this test in this sandbox",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-10T15:38:57.194Z",
    "resolved_at": null
  }
]
````
