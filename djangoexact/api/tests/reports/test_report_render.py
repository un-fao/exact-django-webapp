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

from datetime import date
from types import SimpleNamespace
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


def _build_context(*, mitigating=False, implementation_years=None, narrative=None, content=None):
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
        return html_context.build_template_context(result, narrative=narrative, content=content)


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


NARRATIVE = {
    "tier2_specification": "dairy cattle productivity from the national inventory",
    "data_limitations": "Tier 1 defaults were used for soil carbon.",
    "assumption_set_date": date(2026, 3, 14),
    "top_activity_driver": "avoided deforestation on the project boundary",
    "additional_sources": ["Mwangi et al. (2021), Agroforestry in Kenya, p. 44."],
}

# The placeholder strings milestone 2 renders when nothing is supplied. Each must
# survive an omitted field: a blank in an un-editable PDF is invisible.
PLACEHOLDERS = (
    "Tier 2 parameters",
    "Analyst input",
    "data limitations",
    "DD/MM/YYYY",
    "driver behind this activity",
    "additional literature",
)


def _section(html, start, end):
    """The slice of the document between two headings.

    Asserting placement needs this: a whole-document assertIn passes when a
    passage renders in the wrong section, which is exactly the defect that
    "correctly placed" names.
    """
    collapsed = " ".join(html.split())
    assert start in collapsed, "missing heading: %s" % start
    assert end in collapsed, "missing heading: %s" % end
    return collapsed[collapsed.index(start):collapsed.index(end)]


def _render_with(narrative, *, activities=None):
    context = _build_context(narrative=narrative)
    if activities is not None:
        context["activities_total"] = activities
        context["largest_contributing_activity"] = activities[0]
    return render_to_string("reports/ifad_en.html", context)


def _activity(name, balance, narrative=None):
    activity = Mock()
    activity.name = name
    activity.results = {"balance": balance}
    activity.modules_emissions = []
    activity.t2_overrides = []
    activity.narrative = narrative
    return activity


class TestNarrativeReachesThePage(SimpleTestCase):
    """Analyst free text renders, in the right section, or not at all."""

    def test_every_supplied_field_appears(self):
        html = " ".join(
            _render_with(NARRATIVE, activities=[_activity("Agroforestry", -12345.0)]).split()
        )
        for value in (
            "dairy cattle productivity from the national inventory",
            "Tier 1 defaults were used for soil carbon.",
            "14/03/2026",
            "avoided deforestation on the project boundary",
            "Mwangi et al. (2021), Agroforestry in Kenya, p. 44.",
        ):
            with self.subTest(value=value):
                self.assertIn(value, html)

    def test_each_field_lands_in_its_own_section(self):
        html = _render_with(NARRATIVE, activities=[_activity("Agroforestry", -12345.0)])
        assumptions = _section(html, "III. Assumptions and activities", "IV. Results")
        results = _section(html, "IV. Results", "Sources")

        self.assertIn("dairy cattle productivity", assumptions)
        self.assertIn("Tier 1 defaults were used", assumptions)
        self.assertIn("14/03/2026", assumptions)
        self.assertNotIn("avoided deforestation", assumptions)

        self.assertIn("avoided deforestation", results)
        self.assertNotIn("dairy cattle productivity", results)

        self.assertIn("Mwangi et al. (2021)", html[html.index("Sources</h2>"):])

    def test_omitted_fields_keep_their_placeholders(self):
        # One activity, so the top-activity driver branch is reachable at all.
        html = _render_with(None, activities=[_activity("Agroforestry", -12345.0)])
        for placeholder in PLACEHOLDERS:
            with self.subTest(placeholder=placeholder):
                self.assertIn(placeholder, html)

    def test_a_partial_narrative_leaves_the_rest_placeheld(self):
        html = _render_with({"data_limitations": "Only this one was supplied."})
        self.assertIn("Only this one was supplied.", html)
        self.assertIn("DD/MM/YYYY", html)
        self.assertIn("Tier 2 parameters", html)


class TestNarrativeIsEscaped(SimpleTestCase):
    """The PDF engine is version-pinned under a CVE exemption.

    These assertions are what stops a later `|safe` -- added to make some
    formatting work -- from silently turning analyst prose into markup. Each
    checks the raw string is ABSENT as well as that the escaped one is present:
    asserting only the latter passes even when a raw copy is also in the page.
    """

    HOSTILE = '<script>alert(1)</script>" onload="x'

    def test_markup_is_escaped_in_every_field(self):
        html = _render_with(
            {
                "tier2_specification": self.HOSTILE,
                "data_limitations": self.HOSTILE,
                "top_activity_driver": self.HOSTILE,
                "additional_sources": [self.HOSTILE],
            },
            activities=[_activity("Agroforestry", -1.0)],
        )
        self.assertNotIn("<script>", html)
        self.assertNotIn('" onload="', html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_per_activity_markup_is_escaped(self):
        activity = _activity(
            "Agroforestry", -1.0,
            narrative={"wop": self.HOSTILE, "wp": self.HOSTILE, "data_source": self.HOSTILE},
        )
        html = _render_with(None, activities=[activity])
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_linebreaksbr_adds_breaks_without_opening_a_hole(self):
        html = _render_with({"data_limitations": "first line\n<i>second</i>"})
        self.assertIn("first line<br>", html)
        self.assertIn("&lt;i&gt;second&lt;/i&gt;", html)
        self.assertNotIn("<i>second</i>", html)


class TestAnalystContent(SimpleTestCase):
    """HTML notes render as markup only after the sanitizer has marked them safe."""

    def _render(self, content):
        return render_to_string("reports/ifad_en.html", _build_context(content=content))

    def test_sanitized_content_renders_as_markup(self):
        from api.reports.narrative import clean_content

        html = self._render(clean_content('<p>Soil <b>carbon</b></p><img src="file:///etc/passwd">'))
        self.assertIn("Analyst notes", html)
        self.assertIn("<p>Soil <b>carbon</b></p>", html)
        self.assertNotIn("file:", html)

    def test_content_that_skipped_the_sanitizer_is_escaped(self):
        """Fails if a `|safe` is ever added to the partial."""
        html = self._render("<script>alert(1)</script><b>raw</b>")
        self.assertNotIn("<script>alert(1)", html)
        self.assertNotIn("<b>raw</b>", html)
        self.assertIn("&lt;b&gt;raw&lt;/b&gt;", html)

    def test_no_content_means_no_section(self):
        self.assertNotIn("Analyst notes", self._render(None))


class TestPerActivityNarrative(SimpleTestCase):
    """Narrative keyed by activity id reaches the right activity, and only it."""

    def test_attached_by_string_id(self):
        from api.reports import html_context

        first, second = _activity("Agroforestry", -5.0), _activity("Rice", 3.0)
        first.pk, second.pk = 41, 42
        with patch.object(html_context, "_compute_activity_contexts", return_value=[first, second]):
            context = _build_context(narrative={"activities": {"41": {"wop": "Continuous maize."}}})

        self.assertEqual(first.narrative, {"wop": "Continuous maize."})
        self.assertIsNone(second.narrative)
        self.assertEqual(context["narrative"]["activities"], {"41": {"wop": "Continuous maize."}})

    def test_one_activity_does_not_inherit_its_neighbours_prose(self):
        described = _activity(
            "Agroforestry", -5.0,
            narrative={
                "wop": "Degraded grazing land.",
                "wp": "Trees on 4,000 ha.",
                "data_source": "PDR p. 37",
            },
        )
        bare = _activity("Rice intensification", 3.0)
        html = " ".join(_render_with(None, activities=[described, bare]).split())

        self.assertIn("Degraded grazing land.", html)
        self.assertIn("Trees on 4,000 ha.", html)
        self.assertIn("PDR p. 37", html)
        self.assertIn(
            "Rice intensification</span> WOP situation, WP practice change, "
            "and data source to be supplied by the analyst.",
            html,
        )

    def test_instructions_box_disappears_once_activities_are_described(self):
        with_text = _render_with({"activities": {"41": {"wop": "x"}}})
        self.assertNotIn("For each activity assessed, describe", with_text)
        self.assertIn("For each activity assessed, describe", _render_with(None))


class TestComputedTier2Parameters(SimpleTestCase):
    """The seven activity-level Tier 2 overrides fill the sentence the analyst used to type.

    They were already computed for the Excel report and carried on
    ActivityResult.t2_overrides; nothing read them on the HTML side.

    An empty list is not the same as "not applicable". Only these seven
    parameters are detectable, so a module that overrode its own parameters
    leaves no trace here, and the placeholder has to survive that case.
    """

    def _context_with_overrides(self, *label_sets):
        from api.reports import html_context

        activities = []
        for labels in label_sets:
            activity = _activity("Activity %d" % len(activities), -1.0)
            activity.t2_overrides = [SimpleNamespace(label=lbl) for lbl in labels]
            activities.append(activity)
        with patch.object(html_context, "_compute_activity_contexts", return_value=activities):
            return _build_context()

    def test_labels_are_deduplicated_and_sorted_across_activities(self):
        context = self._context_with_overrides(["SOC", "Climate"], ["Climate", "Soil type"])
        self.assertEqual(context["tier2_parameters"], ["Climate", "SOC", "Soil type"])

    def test_no_overrides_yields_an_empty_list(self):
        self.assertEqual(self._context_with_overrides([])["tier2_parameters"], [])

    def test_computed_list_replaces_the_placeholder(self):
        context = self._context_with_overrides(["Climate", "SOC"])
        html = " ".join(render_to_string("reports/ifad_en.html", context).split())
        self.assertIn("Tier 2 parameters were used for Climate, SOC", html)
        self.assertNotIn("specify, or state", html)

    def test_analyst_text_is_appended_not_replaced(self):
        from api.reports import html_context

        activity = _activity("Agroforestry", -1.0)
        activity.t2_overrides = [SimpleNamespace(label="Climate")]
        with patch.object(html_context, "_compute_activity_contexts", return_value=[activity]):
            context = _build_context(narrative={"tier2_specification": "manure management factors"})
        html = " ".join(render_to_string("reports/ifad_en.html", context).split())
        self.assertIn("used for Climate; manure management factors", html)

    def test_placeholder_survives_when_nothing_is_detected(self):
        context = self._context_with_overrides([])
        html = render_to_string("reports/ifad_en.html", context)
        self.assertIn("specify, or state", html)
