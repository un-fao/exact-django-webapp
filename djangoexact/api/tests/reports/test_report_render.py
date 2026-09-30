"""Rendering guards for the report templates.

Before this module, no test anywhere loaded a report template. A broken
include, a renamed context key or a typo in a filter shipped green, because the
only template-level coverage mocked ``render_to_string`` itself.

Two things make these assertions meaningful rather than decorative:

  * Django's ``string_if_invalid`` defaults to ``""``, so an unknown variable
    renders as nothing at all. "It rendered without raising" therefore proves
    almost nothing -- every assertion below checks for a *value*, not just a
    successful render.
  * The IFAD report is un-editable PDF output, so a passage that silently
    renders blank reaches the analyst with no opportunity to notice.

Ceiling: this exercises HTML, not PDF bytes. WeasyPrint is never invoked, so a
rule that breaks paged output still passes here. That is deliberate -- the FAO
templates pull Bootstrap from a CDN, and a PDF-level test would drag a live
network dependency into CI.

Run with:
    python manage.py test api.tests.reports.test_report_render
"""
from __future__ import annotations

from unittest.mock import Mock, patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase

IMPLEMENTATION_YEARS = 5
CAPITALIZATION_YEARS = 2
TOTAL_YEARS = IMPLEMENTATION_YEARS + CAPITALIZATION_YEARS

# Chosen so every derived figure is distinct and wide enough to exercise intcomma.
YEARLY_W = 100_000.0
YEARLY_WO = 40_000.0
EXPECTED_W = YEARLY_W * TOTAL_YEARS                              # 700,000
EXPECTED_WO = YEARLY_WO * TOTAL_YEARS                            # 280,000
EXPECTED_BALANCE = EXPECTED_W - EXPECTED_WO                      # 420,000
EXPECTED_DURING = (YEARLY_W - YEARLY_WO) * IMPLEMENTATION_YEARS  # 300,000
EXPECTED_AFTER = (YEARLY_W - YEARLY_WO) * CAPITALIZATION_YEARS   # 120,000

ALL_REPORT_TEMPLATES = ["fao_en", "fao_es", "fao_fr", "ifad_en"]


def _make_project():
    project = Mock()
    project.name = "Sample Resilience Project"
    project.country.name = "Kenya"
    # None keeps the SOC lookup from touching ipcc.models.
    project.climate = None
    project.moisture = None
    project.soil_type = None
    project.start_year_of_activities = 2020
    project.implementation_years = IMPLEMENTATION_YEARS
    project.capitalization_years = CAPITALIZATION_YEARS
    project.last_year_of_accounting = 2027
    project.activities.all.return_value = []
    return project


def _make_result(project, *, mitigating=False):
    w, wo = (YEARLY_WO, YEARLY_W) if mitigating else (YEARLY_W, YEARLY_WO)
    aggregated = Mock()
    aggregated.yearly_balance_w = [w] * TOTAL_YEARS
    aggregated.yearly_balance_wo = [wo] * TOTAL_YEARS

    result = Mock()
    result.project = project
    result.aggregated = aggregated
    result.activity_results = []
    result.duration = TOTAL_YEARS
    return result


def _build_context(*, mitigating=False, implementation_years=None):
    """Run the real build_template_context with only its I/O boundaries mocked."""
    from api.reports import html_context

    with (
        patch.object(html_context, "_build_chart_data", return_value=("", "")),
        patch.object(html_context, "_load_fao_logo", return_value=""),
        patch("api.models.LivestockCategoryType") as lct,
        patch("api.models.FisheryType") as ft,
        patch("api.models.ModuleType") as mt,
    ):
        lct.objects.all.return_value = []
        ft.objects.all.return_value = []
        mt.objects.filter.return_value.all.return_value = []
        project = _make_project()
        if implementation_years is not None:
            project.implementation_years = implementation_years
        result = _make_result(project, mitigating=mitigating)
        return html_context.build_template_context(result)


class TestEveryReportTemplateRenders(SimpleTestCase):
    """Every shipped report template loads and renders with a real context."""

    def test_all_templates_render(self):
        context = _build_context()
        for name in ALL_REPORT_TEMPLATES:
            with self.subTest(template=name):
                html = render_to_string(f"reports/{name}.html", context)
                self.assertGreater(len(html), 500, f"{name} rendered suspiciously little")


class TestBalanceSplitReconciles(SimpleTestCase):
    """The implementation/post-implementation halves must sum to the headline total.

    build_template_context derives the split from the with/without pair rather
    than from aggregated.yearly_balance, because that property sums a different
    field set. If someone 'simplifies' it back to slicing yearly_balance, the two
    halves stop adding up to the figure the report prints, and nothing else in
    the suite would notice.
    """

    def test_halves_sum_to_total(self):
        context = _build_context()
        self.assertAlmostEqual(
            context["balance_during_implementation"] + context["balance_after_implementation"],
            context["total_carbon_balance"],
            places=6,
        )

    def test_split_values(self):
        context = _build_context()
        self.assertAlmostEqual(context["total_carbon_balance"], EXPECTED_BALANCE, places=6)
        self.assertAlmostEqual(context["balance_during_implementation"], EXPECTED_DURING, places=6)
        self.assertAlmostEqual(context["balance_after_implementation"], EXPECTED_AFTER, places=6)

    def test_zero_implementation_years_puts_everything_after(self):
        context = _build_context(implementation_years=0)
        self.assertEqual(context["balance_during_implementation"], 0.0)
        self.assertAlmostEqual(context["balance_after_implementation"], EXPECTED_BALANCE, places=6)


class TestIfadReportContent(SimpleTestCase):
    """Computed figures actually reach the IFAD page, in the right places."""

    def _render(self, *, mitigating=False):
        return render_to_string("reports/ifad_en.html", _build_context(mitigating=mitigating))

    def test_sections_present(self):
        html = self._render()
        for heading in (
            "Green House Gas accounting for investments in agriculture",
            "I. Purpose and scope of the assessment",
            "II. Methodology",
            "III. Assumptions and activities considered",
            "IV. Results",
            "Sources",
            "Table 2: MDB-aligned indicators",
            "Table 3: Carbon balance by GHG",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, html)

    def test_identity_table_is_populated(self):
        html = " ".join(self._render().split())
        self.assertIn("Sample Resilience Project", html)
        self.assertIn("Kenya", html)
        self.assertIn(
            f"{TOTAL_YEARS} years total = {IMPLEMENTATION_YEARS} years implementation",
            html,
        )

    def test_computed_figures_appear(self):
        html = self._render()
        for value in ("420,000", "300,000", "120,000", "700,000", "280,000"):
            with self.subTest(value=value):
                self.assertIn(value, html)

    def test_no_docx_placeholders_survive(self):
        """The bracketed fill-ins from the source .docx must all be resolved."""
        html = self._render()
        for leftover in ("[X,XXX,XXX]", "[XXX,XXX]", "[Project Name]", "[Country]", "[link]"):
            with self.subTest(leftover=leftover):
                self.assertNotIn(leftover, html)

    def test_no_dangling_punctuation_when_totals_are_empty(self):
        """A project with no area, heads or catch must not render 'a total of .'"""
        html = " ".join(self._render().split())
        self.assertNotIn("total of .", html)

    def test_free_text_renders_as_visible_placeholder(self):
        """Milestone 2 accepts no user input; every gap must be visibly labelled."""
        html = self._render()
        self.assertIn("analyst-input", html)
        self.assertIn("IFAD region", html)
        self.assertIn("Analyst input", html)

    def test_balance_direction_follows_sign(self):
        self.assertIn("is a source of GHG emissions", self._render())
        self.assertIn("contributes to emission reduction", self._render(mitigating=True))


class TestIfadReportWithActivities(SimpleTestCase):
    """Branches that only render when the project has activities and gas totals."""

    def _context_with_activities(self):
        context = _build_context()
        activity = Mock()
        activity.name = "Agroforestry establishment"
        activity.results = {"balance": -12_345.0}
        context["activities_total"] = [activity]
        context["largest_contributing_activity"] = activity
        context["modules_used"] = ["Cropland", "Livestock"]
        context["ghg_rows"] = [
            {"gas": "CO2", "w": 500_000.0, "wo": 200_000.0, "balance": 300_000.0},
            {"gas": "CH4", "w": 150_000.0, "wo": 60_000.0, "balance": 90_000.0},
            {"gas": "N2O", "w": 50_000.0, "wo": 20_000.0, "balance": 30_000.0},
        ]
        return context

    def test_activity_and_module_details_render(self):
        rendered = render_to_string("reports/ifad_en.html", self._context_with_activities())
        html = " ".join(rendered.split())
        self.assertIn("Agroforestry establishment", html)
        self.assertIn("-12,345", html)
        self.assertIn("Cropland, Livestock", html)
        self.assertIn("1 project activity", html)

    def test_ghg_table_rows_render(self):
        html = render_to_string("reports/ifad_en.html", self._context_with_activities())
        for value in ("500,000", "200,000", "300,000", "150,000", "90,000", "30,000"):
            with self.subTest(value=value):
                self.assertIn(value, html)
