"""DB-free guard for the report catalog.

Report names arrive on requests. Before the catalog they were interpolated
straight into a template path, guarded only by an os.path.exists probe on two
paths and by nothing at all on the third. These tests are what keep the closed
set closed:

  - If resolution for FAO ever stops producing the exact paths it produced
    before the catalog existed, the FAO report's output has changed and
    test_fao_template_paths_are_unchanged fails. That is the whole of the
    "FAO output is provably unchanged" claim -- this change is a resolution
    refactor, so identical resolution is identical output.
  - If a report is registered without the template file it names, or a
    template is renamed out from under a registration,
    test_every_registered_pair_loads fails at test time instead of at render
    time in front of an analyst.

Known ceiling: get_template resolves the top-level file only. Django resolves
{% include %} at render time, so a broken partial still passes here. That is
closed by api/tests/reports/test_report_render.py, which renders every report
and asserts on the values that come out.

Run with:
    python manage.py test api.tests.reports.test_catalog
"""
from __future__ import annotations

from django.template.loader import get_template
from django.test import SimpleTestCase

from api.reports.catalog import REPORTS, UnknownReport, resolve_template


class ReportCatalogTestCase(SimpleTestCase):
    def test_fao_template_paths_are_unchanged(self):
        for lang in ("en", "es", "fr"):
            with self.subTest(lang=lang):
                self.assertEqual(resolve_template("fao", lang), f"reports/fao_{lang}.html")

    def test_every_registered_pair_loads(self):
        for report, langs in REPORTS.items():
            for lang in sorted(langs):
                with self.subTest(report=report, lang=lang):
                    get_template(resolve_template(report, lang))

    def test_unknown_report_raises(self):
        for name in ("nope", "", "fao_en", "../../../etc/passwd", "reports/fao"):
            with self.subTest(name=name):
                with self.assertRaises(UnknownReport):
                    resolve_template(name, "en")

    def test_unknown_language_for_known_report_raises(self):
        with self.assertRaises(UnknownReport):
            resolve_template("fao", "de")

    def test_message_does_not_echo_the_submitted_name(self):
        secret = "zzsentinelzz"
        with self.assertRaises(UnknownReport) as ctx:
            resolve_template(secret, "en")
        self.assertNotIn(secret, str(ctx.exception))

    def test_catalog_holds_exactly_the_shipped_reports(self):
        """A registration without a template behind it is worse than no
        registration, so this fails loudly when one is added ahead of its
        template. test_every_registered_pair_loads is what proves the template
        is really there; this only pins the set so a new report is a deliberate
        edit rather than a silent import."""
        self.assertEqual(sorted(REPORTS), ["fao", "ifad"])

    def test_ifad_is_english_only(self):
        """The IFAD template was delivered in English only. Without a per-report
        language set, ifad&lang=fr would 500 at render time instead of 400 here."""
        self.assertEqual(resolve_template("ifad", "en"), "reports/ifad_en.html")
        for lang in ("es", "fr"):
            with self.subTest(lang=lang), self.assertRaises(UnknownReport):
                resolve_template("ifad", lang)
