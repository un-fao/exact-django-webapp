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
from rest_framework.exceptions import ValidationError

import api.utilities as utils


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

    def test_view_rejects_a_language_that_escapes_the_template_directory(self):
        """Proves the view routes through the guard rather than reading the raw
        parameter: inline the old expression again and this fails."""
        with self.assertRaises(ValidationError):
            self._resolved_lang(_request(lang="/../../etc/passwd"))


class RequestedLanguageValidationTestCase(SimpleTestCase):
    """Honouring ?lang= removed an accidental guard, and this replaces it.

    LocaleMiddleware sets request.LANGUAGE_CODE on every request, so the line
    this PR deleted -- an unconditional overwrite from that attribute -- meant
    lang could only ever be a code Django had already validated. Letting the
    query parameter win makes it raw user input, and it is interpolated into
    both the report template path and the logo filename that gets opened.
    """

    def test_configured_languages_pass_through(self):
        for lang in ("en", "fr", "es", "ru"):
            with self.subTest(lang=lang):
                self.assertEqual(utils.requested_language(_request(lang=lang)), lang)

    def test_header_and_default_still_apply(self):
        self.assertEqual(utils.requested_language(_request(header_lang="fr")), "fr")
        self.assertEqual(utils.requested_language(_request()), "en")

    def test_traversal_and_unconfigured_languages_are_rejected(self):
        for lang in (
            "/../../etc/passwd",   # escapes media/ in the logo path
            "/../fao_en",          # satisfies the .html existence gate while still traversing
            "../../x",
            "en/../../x",
            "de", "en-US", "EN", ".", "fao_en",
        ):
            with self.subTest(lang=lang), self.assertRaises(ValidationError):
                utils.requested_language(_request(lang=lang))

    def test_message_does_not_echo_the_submitted_value(self):
        secret = "zzsentinelzz"
        with self.assertRaises(ValidationError) as ctx:
            utils.requested_language(_request(lang=secret))
        self.assertNotIn(secret, str(ctx.exception))
