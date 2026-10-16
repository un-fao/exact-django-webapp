"""Guards for the analyst notes request boundary.

``content`` is the only user-supplied input that reaches the PDF engine, which
is version-pinned under a CVE exemption. What happens here is everything that
must fail *loudly* rather than quietly:

  - hostile markup is stripped by the allowlist sanitizer;
  - an over-cap or non-string value is a 400, never a truncation;
  - a report whose template does not render the notes refuses them outright;
  - the retired ``narrative`` key is a 400, because dropping it would hand
    back an un-editable PDF missing prose the analyst wrote.

Run with:
    python manage.py test api.tests.reports.test_narrative
"""
from __future__ import annotations

from unittest.mock import Mock

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from api.reports.narrative import (
    CONTENT_MAX_LENGTH,
    clean_content,
    content_from_request,
    sources_from_request,
)


def _request(body):
    return Mock(data=body)


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

    def test_the_retired_narrative_key_is_refused_not_dropped(self):
        for template_name in ("ifad", "fao", None):
            for value in ({"data_limitations": "x"}, {}, None):
                with self.subTest(template=template_name, value=value):
                    with self.assertRaises(ValidationError) as caught:
                        content_from_request(_request({"narrative": value}), template_name)
                    self.assertIn("content", str(caught.exception))


class SourcesFromRequestTestCase(SimpleTestCase):
    def test_absent_or_empty_sources_are_none(self):
        self.assertIsNone(sources_from_request(_request({}), "ifad"))
        self.assertIsNone(sources_from_request(_request({"additional_sources": ""}), "ifad"))

    def test_sources_are_sanitized(self):
        sources = sources_from_request(
            _request({"additional_sources": '<ul><li>FAO 2021</li></ul><img src="file:///etc/passwd">'}), "ifad",
        )
        self.assertEqual(sources, "<ul><li>FAO 2021</li></ul>")

    def test_a_report_that_does_not_render_sources_refuses_them(self):
        for template_name in ("fao", None):
            with self.subTest(template=template_name):
                with self.assertRaises(ValidationError) as caught:
                    sources_from_request(_request({"additional_sources": "<p>x</p>"}), template_name)
                self.assertIn("additional_sources", str(caught.exception))


class ReportEndpointsArePostOnlyTestCase(SimpleTestCase):
    def test_no_report_action_answers_get(self):
        from api.views import ProjectViewSet
        from public.views import PublicProjectViewSet

        for action in (ProjectViewSet.report, ProjectViewSet.report_async, PublicProjectViewSet.report):
            with self.subTest(action=action.__qualname__):
                self.assertEqual(list(action.mapping), ["post"])
