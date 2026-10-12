"""DB-free guard for the WeasyPrint not-affected exemption.

WeasyPrint is deliberately held at 68.0 in requirements.txt despite
CVE-2026-49452. That advisory is only reachable when the
presentational_hints option is passed to WeasyPrint's HTML renderer; this
codebase never enables it, so the vulnerable code path is unreachable.

This test is what keeps that not-affected claim honest: if any source file
under the Django root starts enabling presentational_hints, the exemption
in requirements.txt is no longer valid and weasyprint must be bumped to
69.0 (or the call site otherwise mitigated) before this test is allowed to
pass again.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

PRESENTATIONAL_HINTS_FLAG = "presentational_hints"

SKIP_DIR_NAMES = {
    "node_modules",
    "venv",
    "env",
    ".venv",
    ".git",
    "__pycache__",
    "static",
    "media",
    "locale",
    "logs",
}


class WeasyPrintPresentationalHintsGuardTests(SimpleTestCase):
    def _scan(self):
        """Walk the Django root for .py files mentioning the flag.

        Returns a tuple of (offending paths relative to BASE_DIR, count of
        files scanned). Vendored/generated trees are skipped so the guard
        stays fast and cannot trip on third-party code. The guard file
        itself is excluded, since it necessarily names the option.
        """
        base_dir = Path(settings.BASE_DIR)
        this_file = Path(__file__).resolve()

        offenders = []
        scanned = 0

        for path in base_dir.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.resolve() == this_file:
                continue

            scanned += 1
            content = path.read_text(encoding="utf-8", errors="replace")
            if PRESENTATIONAL_HINTS_FLAG in content:
                offenders.append(str(path.relative_to(base_dir)))

        return offenders, scanned

    def test_no_source_enables_presentational_hints(self):
        offenders, _ = self._scan()
        self.assertEqual(
            offenders,
            [],
            "CVE-2026-49452 not-affected claim in requirements.txt is invalid: these files "
            "mention presentational_hints and must be re-triaged: {}. Bump weasyprint to 69.0 "
            "or otherwise mitigate the call site.".format(offenders),
        )

    def test_guard_scans_a_meaningful_file_set(self):
        _, scanned = self._scan()
        self.assertGreater(
            scanned,
            200,
            "Guard scanned only {} files; the directory walk may be broken and silently "
            "collapsed to nothing.".format(scanned),
        )
