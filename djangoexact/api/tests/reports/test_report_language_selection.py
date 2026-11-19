"""Guard: ?lang= must select the report language on every path.

The synchronous PDF path advertised a lang query parameter in its own swagger
schema and then discarded it: request.LANGUAGE_CODE, which comes from the
Accept-Language header, overwrote whatever was asked for. The async path let
the parameter win. An English-only IFAD annex hid the divergence, but a
Spanish FAO report requested with ?lang=es from a browser sending
Accept-Language: en came back in English.

Every path now reads the same expression: the explicit parameter first, the
header as fallback, "en" last. The synchronous Excel report was the last to
ignore it. An empty ?lang= counts as absent rather than selecting a language
that cannot exist.

Run with:
    python manage.py test api.tests.reports.test_report_language_selection
"""
from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock, patch

import openpyxl
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

import api.utilities as utils
from api.models import AnnualCropland
from api.reports.constants import WS_METADATA
from api.tests.unit import base_module
from api.tests.unit.factories import UnitTestAnnualCroplandFactory


def _request(*, lang=None, header_lang=None):
    query = {"template": "fao"}
    if lang is not None:
        query["lang"] = lang
    request = Mock()
    request.query_params = query
    # Without this a bare Mock hands content_from_request a truthy payload.
    request.data = {}
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

    def test_compute_runs_in_the_requested_language(self):
        """Module titles are read from translated names during the compute; under the
        header language they came out in English in an otherwise Spanish report."""
        from django.utils.translation import get_language

        from api.views import ProjectViewSet

        viewset = ProjectViewSet()
        viewset.kwargs = {"pk": 1}
        viewset.format_kwarg = None
        project = Mock()
        project.activities.filter.return_value = []
        viewset.get_object = Mock(return_value=project)
        seen = []

        with (
            patch("api.reports.compute_project_result", side_effect=lambda *a: seen.append(get_language())),
            patch("api.reports.html_context.build_template_context", return_value={}),
            patch("api.views.render", return_value=Mock(content=b"<html></html>")),
        ):
            viewset.template(_request(lang="es", header_lang="en"), pk=1)
        self.assertEqual(seen, ["es"])

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


class SyncExcelLanguageTestCase(base_module.BaseModuleTestCase):
    """Sent through the client so LocaleMiddleware activates the header language,
    which is what the Excel used to come out in."""

    # Inherited from BaseModuleTestCase, it tests module defaults and lock holders, not
    # report language; None keeps the runner from collecting it a second time here.
    test_defaults_visible_with_different_lock_holder = None

    FRENCH_SOIL_TYPE = "Sol de reference en francais"

    def setUp(self):
        self.ModuleClass = AnnualCropland
        super().setUp()
        self.edit_module(self.module, self.user, UnitTestAnnualCroplandFactory.get_validated_data())
        soil_type = self.project.soil_type
        soil_type.name_fr = self.FRENCH_SOIL_TYPE
        soil_type.save()
        self.client.force_authenticate(self.user)

    def _post_report(self, path, lang):
        return self.client.post(
            f"/api/projects/{self.project.pk}/{path}?lang={lang}", {}, format="json", HTTP_ACCEPT_LANGUAGE="en",
        )

    def test_query_parameter_beats_the_accept_language_header(self):
        response = self._post_report("report/", "fr")
        self.assertEqual(response.status_code, 200)
        metadata = openpyxl.load_workbook(BytesIO(response.content))[WS_METADATA]
        written = {cell.value for row in metadata.iter_rows() for cell in row}
        self.assertIn(self.FRENCH_SOIL_TYPE, written)

    def test_unsupported_language_is_rejected_like_the_async_path(self):
        sync = self._post_report("report/", "de")
        queued = self._post_report("report/async/", "de")
        self.assertEqual(sync.status_code, 400)
        self.assertEqual((sync.status_code, sync.data), (queued.status_code, queued.data))
