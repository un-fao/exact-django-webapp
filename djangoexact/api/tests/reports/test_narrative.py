"""Guards for the analyst narrative request boundary.

Milestone 3 is the first time user-supplied prose reaches the PDF engine, which
is version-pinned under a CVE exemption. Escaping happens in the template; what
happens here is everything that must fail *loudly* rather than quietly:

  - an over-cap value is a 400, never a truncation;
  - a misspelled field name is a 400, because DRF would otherwise drop it and
    the analyst would receive an un-editable PDF missing a passage they wrote,
    with nothing to notice;
  - narrative keyed to an activity the report does not contain is a 400, for
    the same reason;
  - a report whose template does not read narrative refuses it outright.

Run with:
    python manage.py test api.tests.reports.test_narrative
"""
from __future__ import annotations

import datetime
from unittest.mock import Mock

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from api.reports.narrative import (
    CONTENT_MAX_LENGTH,
    clean_content,
    clean_narrative,
    content_from_request,
    narrative_from_request,
)


def _activities(*pks):
    return [Mock(pk=pk) for pk in pks]


def _request(body):
    return Mock(data=body)


class CleanNarrativeTestCase(SimpleTestCase):
    def test_full_payload_validates(self):
        narrative = clean_narrative(
            {
                "tier2_specification": "Dairy cattle productivity.",
                "data_limitations": "Tier 1 defaults for soil carbon.",
                "assumption_set_date": "2026-03-14",
                "top_activity_driver": "Avoided deforestation.",
                "additional_sources": ["Mwangi et al. (2021)."],
                "activities": {"41": {"wop": "Maize.", "wp": "Agroforestry.", "data_source": "PDR p. 37"}},
            },
            _activities(41, 42),
        )
        self.assertEqual(narrative["assumption_set_date"], datetime.date(2026, 3, 14))
        self.assertEqual(narrative["activities"]["41"]["data_source"], "PDR p. 37")

    def test_date_is_parsed_not_carried_as_text(self):
        """A real date cannot carry a payload, which takes one field off the boundary."""
        narrative = clean_narrative({"assumption_set_date": "2026-03-14"}, [])
        self.assertIsInstance(narrative["assumption_set_date"], datetime.date)

        with self.assertRaises(ValidationError):
            clean_narrative({"assumption_set_date": "<script>"}, [])

    def test_unknown_field_is_rejected_rather_than_dropped(self):
        with self.assertRaises(ValidationError) as caught:
            clean_narrative({"tier_2_specification": "typo"}, [])
        self.assertIn("tier_2_specification", str(caught.exception))

    def test_over_cap_values_are_rejected_not_truncated(self):
        for field, cap in (
            ("tier2_specification", 2000),
            ("data_limitations", 4000),
            ("top_activity_driver", 2000),
        ):
            with self.subTest(field=field):
                clean_narrative({field: "x" * cap}, [])
                with self.assertRaises(ValidationError):
                    clean_narrative({field: "x" * (cap + 1)}, [])

    def test_activity_field_caps(self):
        clean_narrative({"activities": {"41": {"wop": "x" * 4000}}}, _activities(41))
        with self.assertRaises(ValidationError):
            clean_narrative({"activities": {"41": {"wop": "x" * 4001}}}, _activities(41))
        with self.assertRaises(ValidationError):
            clean_narrative({"activities": {"41": {"data_source": "x" * 501}}}, _activities(41))

    def test_additional_sources_are_capped_in_count_and_length(self):
        clean_narrative({"additional_sources": ["s"] * 20}, [])
        with self.assertRaises(ValidationError):
            clean_narrative({"additional_sources": ["s"] * 21}, [])
        with self.assertRaises(ValidationError):
            clean_narrative({"additional_sources": ["x" * 501]}, [])

    def test_narrative_for_an_activity_not_in_the_report_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            clean_narrative({"activities": {"99": {"wop": "Lost prose."}}}, _activities(41, 42))
        self.assertIn("99", str(caught.exception))

    def test_non_numeric_activity_key_is_rejected(self):
        with self.assertRaises(ValidationError):
            clean_narrative({"activities": {"all": {"wop": "x"}}}, _activities(41))


class CleanContentTestCase(SimpleTestCase):
    """Analyst HTML is the one input rendered as markup, so this is the boundary."""

    # Each of these is a way to make the PDF engine read a file, call out, run
    # script or restyle the report around the analyst's notes.
    HOSTILE = (
        "<script>alert(1)</script>",
        '<img src="file:///etc/passwd">',
        "<img src=x onerror=alert(1)>",
        "<style>@import url(file:///etc/passwd);</style>",
        '<link rel="attachment" href="file:///etc/passwd">',
        '<a rel="attachment" href="file:///etc/passwd">x</a>',
        '<a href="javascript:alert(1)">x</a>',
        '<a href="JaVaScRiPt:alert(1)">x</a>',
        '<a href="data:text/html,x">x</a>',
        '<a href="/relative">x</a>',
        '<a href="//169.254.169.254/latest">x</a>',
        '<iframe src="http://169.254.169.254/"></iframe>',
        "<svg onload=alert(1)></svg>",
        '<object data="file:///etc/passwd"></object>',
        '<embed src="file:///etc/passwd">',
        '<base href="http://169.254.169.254/">',
        '<p style="position:fixed;top:0">x</p>',
        '<p onclick="alert(1)">x</p>',
        '<td style="background:url(file:///etc/passwd)">x</td>',
        '<p class="identity-table" id="x">x</p>',
    )
    FORBIDDEN = (
        "<script", "<img", "<style", "<link", "<iframe", "<svg", "<object", "<embed", "<base",
        "file:", "javascript:", "data:", "169.254", "/relative", "@import", "alert",
        "onerror", "onclick", "onload", "style=", "class=", "id=", "attachment",
    )

    def test_hostile_markup_does_not_survive(self):
        for payload in self.HOSTILE:
            cleaned = clean_content(payload).lower()
            for needle in self.FORBIDDEN:
                with self.subTest(payload=payload, needle=needle):
                    self.assertNotIn(needle, cleaned)

    def test_formatting_survives_unchanged(self):
        notes = "<h3>Soil</h3><p>CO<sub>2</sub> is <b>net</b> <em>negative</em>.</p><ul><li>one</li></ul>"
        self.assertEqual(clean_content(notes), notes)

    def test_absolute_links_survive(self):
        for href in ("https://www.ipcc.ch/report", "http://example.org/a", "mailto:EX-ACT@fao.org"):
            with self.subTest(href=href):
                self.assertIn(f'href="{href}"', clean_content(f'<a href="{href}">x</a>'))

    def test_tables_survive_with_bounded_spans(self):
        table = '<table><thead><tr><th colspan="2">Area</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table>'
        self.assertEqual(clean_content(table), table)
        # The last one is past Python's int-from-string digit limit: it must be
        # dropped like the others, not raise out of the sanitizer as a 500.
        for span in ("100000", "0", "-1", "x", "²", "9" * 5000):
            with self.subTest(span=span):
                self.assertNotIn("colspan", clean_content(f'<table><tr><td colspan="{span}">x</td></tr></table>'))

    def test_result_is_the_only_string_templates_will_not_escape(self):
        from django.utils.safestring import SafeString

        self.assertIsInstance(clean_content("<p>x</p>"), SafeString)

    def test_over_cap_is_rejected_not_truncated(self):
        clean_content("x" * CONTENT_MAX_LENGTH)
        with self.assertRaises(ValidationError):
            clean_content("x" * (CONTENT_MAX_LENGTH + 1))

    def test_non_string_is_rejected(self):
        for value in (["<p>x</p>"], {"html": "<p>x</p>"}, 7, True):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    clean_content(value)


class ContentFromRequestTestCase(SimpleTestCase):
    def test_absent_or_empty_content_is_none(self):
        self.assertIsNone(content_from_request(_request({}), "ifad"))
        self.assertIsNone(content_from_request(_request({"content": ""}), "ifad"))
        self.assertIsNone(content_from_request(Mock(spec=[]), "ifad"))

    def test_content_is_sanitized(self):
        content = content_from_request(_request({"content": "<p>ok</p><script>x()</script>"}), "ifad")
        self.assertEqual(content, "<p>ok</p>")

    def test_a_report_that_does_not_render_content_refuses_it(self):
        for template_name in ("fao", None):
            with self.subTest(template=template_name):
                with self.assertRaises(ValidationError):
                    content_from_request(_request({"content": "<p>x</p>"}), template_name)

    def test_a_non_string_body_value_is_rejected_not_ignored(self):
        with self.assertRaises(ValidationError):
            content_from_request(_request({"content": ["<p>x</p>"]}), "ifad")


class ReportEndpointsArePostOnlyTestCase(SimpleTestCase):
    def test_no_report_action_answers_get(self):
        from api.views import ProjectViewSet
        from public.views import PublicProjectViewSet

        for action in (ProjectViewSet.report, ProjectViewSet.report_async, PublicProjectViewSet.report):
            with self.subTest(action=action.__qualname__):
                self.assertEqual(list(action.mapping), ["post"])


class NarrativeFromRequestTestCase(SimpleTestCase):
    def test_no_body_means_no_narrative(self):
        self.assertEqual(narrative_from_request(_request({}), "ifad", []), (None, None))

    def test_get_request_without_data_is_tolerated(self):
        self.assertEqual(narrative_from_request(Mock(spec=[]), "ifad", []), (None, None))

    def test_raw_and_cleaned_differ_in_the_way_the_paths_need(self):
        raw, cleaned = narrative_from_request(
            _request({"narrative": {"assumption_set_date": "2026-03-14"}}), "ifad", [],
        )
        self.assertEqual(raw, {"assumption_set_date": "2026-03-14"})
        self.assertEqual(cleaned["assumption_set_date"], datetime.date(2026, 3, 14))

    def test_a_report_that_does_not_read_narrative_refuses_it(self):
        for template_name in ("fao", None):
            with self.subTest(template=template_name):
                with self.assertRaises(ValidationError):
                    narrative_from_request(
                        _request({"narrative": {"data_limitations": "x"}}), template_name, [],
                    )
