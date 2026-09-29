"""Guard: ?lang= must select the report language on every path.

The synchronous PDF path advertised a lang query parameter in its own swagger
schema and then discarded it: request.LANGUAGE_CODE, which comes from the
Accept-Language header, overwrote whatever was asked for. The async path let
the parameter win. An English-only IFAD annex hid the divergence, but a
Spanish FAO report requested with ?lang=es from a browser sending
Accept-Language: en came back in English.

All three call sites now read the same expression: the explicit parameter
first, the header as fallback, "en" last. An empty ?lang= counts as absent
rather than selecting a language that cannot exist.

Run with:
    python manage.py test api.tests.reports.test_report_language_selection
"""
from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import SimpleTestCase


def _request(*, lang=None, header_lang=None):
    query = {"template": "fao"}
    if lang is not None:
        query["lang"] = lang
    request = Mock()
    request.query_params = query
    if header_lang is None:
        del request.LANGUAGE_CODE
    else:
        request.LANGUAGE_CODE = header_lang
    return request


class SyncTemplateLanguageTestCase(SimpleTestCase):
    def _resolved_lang(self, request):
        from api.views import ProjectViewSet

        viewset = ProjectViewSet()
        viewset.kwargs = {"pk": 1}
        viewset.format_kwarg = None
        viewset.request = Mock()
        project = Mock()
        project.activities.filter.return_value = []
        viewset.get_object = Mock(return_value=project)

        with (
            patch("api.reports.compute_project_result", return_value=Mock()),
            patch("api.reports.html_context.build_template_context", return_value={}) as build,
            patch("api.views.render", return_value=Mock(content=b"<html></html>")),
        ):
            # WeasyPrint may not import here; the language is already decided by then.
            viewset.template(request, pk=1)
        return build.call_args.args[2]

    def test_query_parameter_beats_the_accept_language_header(self):
        self.assertEqual(self._resolved_lang(_request(lang="es", header_lang="en")), "es")

    def test_header_is_used_when_no_parameter_is_given(self):
        self.assertEqual(self._resolved_lang(_request(header_lang="fr")), "fr")

    def test_english_when_neither_is_given(self):
        self.assertEqual(self._resolved_lang(_request()), "en")

    def test_empty_parameter_counts_as_absent(self):
        self.assertEqual(self._resolved_lang(_request(lang="", header_lang="fr")), "fr")
