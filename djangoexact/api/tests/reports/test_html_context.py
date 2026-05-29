"""Unit tests for api.reports.html_context and the view-level error handling.

Covers four bug-fixes:
  Fix 1 – prefetch_related("modules") removal (activity queryset no longer uses it).
  Fix 2 – SoilOrganicCarbon.objects.get() guarded for None fields and DB exceptions.
  Fix 3 – _load_fao_logo uses context-manager (with open) for file handle safety.
  Fix 4 – Template views return a generic error message on unexpected exceptions.

Run with:
    python manage.py test api.tests.reports.test_html_context
"""
from __future__ import annotations

import base64
import unittest
from unittest.mock import MagicMock, Mock, patch, mock_open


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(*, climate=None, moisture=None, soil_type=None):
    """Return a minimal project mock that satisfies build_template_context."""
    project = Mock()
    project.climate = climate
    project.moisture = moisture
    project.soil_type = soil_type
    project.start_year_of_activities = 2020
    project.implementation_years = 5
    project.capitalization_years = 2
    project.last_year_of_accounting = 2025

    # activities.all() should return an empty queryset-like list (Fix 1: no
    # prefetch_related("modules") call must succeed).
    activities_qs = Mock()
    activities_qs.all.return_value = []
    project.activities = activities_qs

    return project


def _make_project_result(project=None):
    """Return a minimal ProjectResult mock that satisfies build_template_context."""
    if project is None:
        project = _make_project()

    aggregated = Mock()
    aggregated.yearly_balance_w = [10.0, 20.0]
    aggregated.yearly_balance_wo = [5.0, 10.0]

    result = Mock()
    result.project = project
    result.aggregated = aggregated
    result.activity_results = []
    result.duration = 5
    return result


# ---------------------------------------------------------------------------
# Fix 1 — prefetch_related("modules") removal
# ---------------------------------------------------------------------------

class TestBuildTemplateContextActivitiesQuery(unittest.TestCase):
    """Fix 1: build_template_context uses .all() instead of .prefetch_related("modules").all()."""

    def _call(self, result, lang="en"):
        from api.reports.html_context import build_template_context
        request = Mock()
        with (
            patch("api.reports.html_context._compute_gas_totals", return_value={
                "gas_totals_w": {g: 0.0 for g in ["CO2", "CH4", "N2O", "CO", "DOC", "OTHER"]},
                "gas_totals_wo": {g: 0.0 for g in ["CO2", "CH4", "N2O", "CO", "DOC", "OTHER"]},
                "primary_ghg": "CO2", "primary_ghg_emissions": 0.0,
                "secondary_ghg": "CH4", "secondary_ghg_emissions": 0.0,
                "tertiary_ghg": "N2O", "tertiary_ghg_emissions": 0.0,
            }),
            patch("api.reports.html_context._compute_activity_contexts", return_value=[]),
            patch("api.reports.html_context._compute_indicator_aggregates", return_value={
                "total_area": 0, "total_heads": 0, "total_tonnes_of_catch": 0,
                "livestock_heads": [], "small_fishery_types": [],
                "large_fishery_data": {}, "aquaculture_data": {},
                "land_types": [], "soc": None,
            }),
            patch("api.reports.html_context._build_chart_data", return_value=("b64chart", "b64gases")),
            patch("api.reports.html_context._load_fao_logo", return_value="b64logo"),
            patch("django.utils.translation.activate"),
        ):
            return build_template_context(result, request, lang)

    def test_no_field_error_raised_for_project_with_activities(self):
        """build_template_context does not raise FieldError when iterating activities."""
        project = _make_project()
        # Simulate a project that has some activity names in the queryset
        activity_a = Mock()
        activity_a.name = "Activity A"
        activity_b = Mock()
        activity_b.name = "Activity B"
        project.activities.all.return_value = [activity_a, activity_b]

        result = _make_project_result(project=project)

        # Must not raise — in particular must not raise FieldError
        try:
            ctx = self._call(result)
        except Exception as exc:
            self.fail(f"build_template_context raised an unexpected exception: {exc!r}")

        # Verify that activities.all() was called (not prefetch_related)
        project.activities.all.assert_called_once()
        project.activities.prefetch_related.assert_not_called()

    def test_activities_by_name_dict_reflects_queryset_results(self):
        """The returned context's activities_total is built from project.activities.all()."""
        project = _make_project()
        activity = Mock()
        activity.name = "Deforestation"
        project.activities.all.return_value = [activity]

        result = _make_project_result(project=project)

        # _compute_activity_contexts receives activities_by_name; verify
        # it is called with the dict built from .all() results.
        with (
            patch("api.reports.html_context._compute_gas_totals", return_value={
                "gas_totals_w": {g: 0.0 for g in ["CO2", "CH4", "N2O", "CO", "DOC", "OTHER"]},
                "gas_totals_wo": {g: 0.0 for g in ["CO2", "CH4", "N2O", "CO", "DOC", "OTHER"]},
                "primary_ghg": "CO2", "primary_ghg_emissions": 0.0,
                "secondary_ghg": "CH4", "secondary_ghg_emissions": 0.0,
                "tertiary_ghg": "N2O", "tertiary_ghg_emissions": 0.0,
            }),
            patch("api.reports.html_context._compute_activity_contexts") as mock_act_ctx,
            patch("api.reports.html_context._compute_indicator_aggregates", return_value={
                "total_area": 0, "total_heads": 0, "total_tonnes_of_catch": 0,
                "livestock_heads": [], "small_fishery_types": [],
                "large_fishery_data": {}, "aquaculture_data": {},
                "land_types": [], "soc": None,
            }),
            patch("api.reports.html_context._build_chart_data", return_value=("b64", "b64")),
            patch("api.reports.html_context._load_fao_logo", return_value="b64logo"),
            patch("django.utils.translation.activate"),
        ):
            mock_act_ctx.return_value = []
            from api.reports.html_context import build_template_context
            build_template_context(result, Mock(), "en")

        # The first positional arg to _compute_activity_contexts is result;
        # the second is activities_by_name.
        call_args = mock_act_ctx.call_args
        activities_by_name_arg = call_args[0][1]
        self.assertIn("Deforestation", activities_by_name_arg)
        self.assertIs(activities_by_name_arg["Deforestation"], activity)


# ---------------------------------------------------------------------------
# Fix 2 — SoilOrganicCarbon.objects.get() error handling
# ---------------------------------------------------------------------------

class TestComputeIndicatorAggregatesSOC(unittest.TestCase):
    """Fix 2: _compute_indicator_aggregates handles None fields and DB exceptions for SOC."""

    def _call(self, project, activities_by_name=None):
        from api.reports.html_context import _compute_indicator_aggregates
        if activities_by_name is None:
            activities_by_name = {}
        with (
            patch("api.models.LivestockCategoryType") as _lct,
            patch("api.models.FisheryType") as _ft,
            patch("api.models.ModuleType") as _mt,
        ):
            _lct.objects.all.return_value = []
            _ft.objects.all.return_value = []
            _mt.objects.filter.return_value.all.return_value = []
            return _compute_indicator_aggregates(activities_by_name, project)

    # --- None field guards ---------------------------------------------------

    def test_soc_is_none_when_climate_is_none(self):
        """soc is None when project.climate is None."""
        project = _make_project(climate=None, moisture="dry", soil_type="sandy")
        result = self._call(project)
        self.assertIsNone(result["soc"])

    def test_soc_is_none_when_moisture_is_none(self):
        """soc is None when project.moisture is None."""
        project = _make_project(climate="tropical", moisture=None, soil_type="sandy")
        result = self._call(project)
        self.assertIsNone(result["soc"])

    def test_soc_is_none_when_soil_type_is_none(self):
        """soc is None when project.soil_type is None."""
        project = _make_project(climate="tropical", moisture="dry", soil_type=None)
        result = self._call(project)
        self.assertIsNone(result["soc"])

    def test_soc_is_none_when_all_fields_are_none(self):
        """soc is None when all three lookup fields are None."""
        project = _make_project(climate=None, moisture=None, soil_type=None)
        result = self._call(project)
        self.assertIsNone(result["soc"])

    def test_soc_lookup_not_attempted_when_any_field_is_none(self):
        """SoilOrganicCarbon.objects.get is never called when a field is None."""
        project = _make_project(climate=None, moisture="dry", soil_type="sandy")
        with patch("ipcc.models.SoilOrganicCarbon") as mock_soc_cls:
            with (
                patch("api.models.LivestockCategoryType") as _lct,
                patch("api.models.FisheryType") as _ft,
                patch("api.models.ModuleType") as _mt,
            ):
                _lct.objects.all.return_value = []
                _ft.objects.all.return_value = []
                _mt.objects.filter.return_value.all.return_value = []
                from api.reports.html_context import _compute_indicator_aggregates
                _compute_indicator_aggregates({}, project)
            mock_soc_cls.objects.get.assert_not_called()

    # --- DoesNotExist --------------------------------------------------------

    def test_soc_is_none_on_does_not_exist(self):
        """soc is None when SoilOrganicCarbon.DoesNotExist is raised."""
        project = _make_project(climate="tropical", moisture="dry", soil_type="sandy")
        with patch("ipcc.models.SoilOrganicCarbon") as mock_soc_cls:
            mock_soc_cls.DoesNotExist = Exception
            mock_soc_cls.MultipleObjectsReturned = type("MultipleObjectsReturned", (Exception,), {})
            mock_soc_cls.objects.get.side_effect = mock_soc_cls.DoesNotExist("not found")
            with (
                patch("api.models.LivestockCategoryType") as _lct,
                patch("api.models.FisheryType") as _ft,
                patch("api.models.ModuleType") as _mt,
            ):
                _lct.objects.all.return_value = []
                _ft.objects.all.return_value = []
                _mt.objects.filter.return_value.all.return_value = []
                from api.reports.html_context import _compute_indicator_aggregates
                result = _compute_indicator_aggregates({}, project)
        self.assertIsNone(result["soc"])

    # --- MultipleObjectsReturned --------------------------------------------

    def test_soc_is_none_on_multiple_objects_returned(self):
        """soc is None when SoilOrganicCarbon.MultipleObjectsReturned is raised."""
        project = _make_project(climate="tropical", moisture="dry", soil_type="sandy")
        with patch("ipcc.models.SoilOrganicCarbon") as mock_soc_cls:
            mock_soc_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
            mock_soc_cls.MultipleObjectsReturned = Exception
            mock_soc_cls.objects.get.side_effect = mock_soc_cls.MultipleObjectsReturned("multiple")
            with (
                patch("api.models.LivestockCategoryType") as _lct,
                patch("api.models.FisheryType") as _ft,
                patch("api.models.ModuleType") as _mt,
            ):
                _lct.objects.all.return_value = []
                _ft.objects.all.return_value = []
                _mt.objects.filter.return_value.all.return_value = []
                from api.reports.html_context import _compute_indicator_aggregates
                result = _compute_indicator_aggregates({}, project)
        self.assertIsNone(result["soc"])

    # --- Happy path ---------------------------------------------------------

    def test_soc_is_set_when_all_fields_present_and_row_exists(self):
        """soc is the model instance returned by .get() when all fields are present."""
        project = _make_project(climate="tropical", moisture="dry", soil_type="sandy")
        expected_soc = Mock()
        expected_soc.value = 42.5

        with patch("ipcc.models.SoilOrganicCarbon") as mock_soc_cls:
            mock_soc_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
            mock_soc_cls.MultipleObjectsReturned = type("MultipleObjectsReturned", (Exception,), {})
            mock_soc_cls.objects.get.return_value = expected_soc
            with (
                patch("api.models.LivestockCategoryType") as _lct,
                patch("api.models.FisheryType") as _ft,
                patch("api.models.ModuleType") as _mt,
            ):
                _lct.objects.all.return_value = []
                _ft.objects.all.return_value = []
                _mt.objects.filter.return_value.all.return_value = []
                from api.reports.html_context import _compute_indicator_aggregates
                result = _compute_indicator_aggregates({}, project)

        self.assertIs(result["soc"], expected_soc)
        mock_soc_cls.objects.get.assert_called_once_with(
            climate="tropical",
            moisture="dry",
            soil_type="sandy",
        )


# ---------------------------------------------------------------------------
# Fix 3 — _load_fao_logo file handle safety
# ---------------------------------------------------------------------------

class TestLoadFaoLogo(unittest.TestCase):
    """Fix 3: _load_fao_logo uses a context-manager so the file handle is always closed."""

    def _call(self, lang="en"):
        from api.reports.html_context import _load_fao_logo
        return _load_fao_logo(lang)

    def test_returns_base64_string_when_file_exists(self):
        """_load_fao_logo returns a non-empty base64 string when the logo file can be read."""
        svg_bytes = b"<svg>fake</svg>"
        expected_b64 = base64.b64encode(svg_bytes).decode("utf-8")

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=svg_bytes)),
        ):
            result = self._call("en")

        self.assertEqual(result, expected_b64)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_file_handle_is_closed_after_read(self):
        """The file opened by _load_fao_logo is closed when the read succeeds."""
        svg_bytes = b"<svg>logo</svg>"
        m = mock_open(read_data=svg_bytes)

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", m),
        ):
            self._call("en")

        # mock_open's handle has a close() that is called by the context manager
        m().close.assert_called()

    def test_file_handle_is_closed_on_read_error(self):
        """The context-manager ensures close() is called even when read() raises."""
        m = mock_open()
        m.return_value.__enter__.return_value.read.side_effect = OSError("disk error")
        m.return_value.__exit__.return_value = False  # do not suppress the exception

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", m),
        ):
            with self.assertRaises(OSError):
                self._call("en")

        m.return_value.__exit__.assert_called_once()

    def test_raises_when_neither_lang_nor_fallback_file_exists(self):
        """_load_fao_logo raises FileNotFoundError when no file path exists."""
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                self._call("fr")

    def test_uses_lang_specific_path_when_it_exists(self):
        """_load_fao_logo prefers the lang-specific file path over the fallback."""
        svg_bytes = b"<svg>fr</svg>"
        opened_paths: list[str] = []

        def fake_exists(path: str) -> bool:
            # Only the lang-specific path exists
            return path.endswith("faologo_fr.svg")

        def fake_open(path, mode="r", *args, **kwargs):
            opened_paths.append(path)
            return mock_open(read_data=svg_bytes)()

        with (
            patch("os.path.exists", side_effect=fake_exists),
            patch("builtins.open", side_effect=fake_open),
        ):
            self._call("fr")

        self.assertTrue(
            any("faologo_fr.svg" in p for p in opened_paths),
            msg=f"Expected lang-specific path to be opened, got: {opened_paths}",
        )

    def test_falls_back_to_generic_logo_when_lang_file_missing(self):
        """_load_fao_logo uses faologo.svg when the lang-specific file is absent."""
        svg_bytes = b"<svg>generic</svg>"
        opened_paths: list[str] = []

        def fake_exists(path: str) -> bool:
            # Lang-specific path does not exist; fallback does
            return path.endswith("faologo.svg") and "faologo_" not in path

        def fake_open(path, mode="r", *args, **kwargs):
            opened_paths.append(path)
            return mock_open(read_data=svg_bytes)()

        with (
            patch("os.path.exists", side_effect=fake_exists),
            patch("builtins.open", side_effect=fake_open),
        ):
            self._call("de")

        self.assertTrue(
            any(p.endswith("faologo.svg") and "faologo_" not in p for p in opened_paths),
            msg=f"Expected fallback path to be opened, got: {opened_paths}",
        )


# ---------------------------------------------------------------------------
# Fix 4 — Generic error message in views
# ---------------------------------------------------------------------------

class TestPublicProjectViewSetTemplateErrorHandling(unittest.TestCase):
    """Fix 4 (public view): template() returns a generic message and calls log.exception."""

    def _make_viewset(self):
        from public.views import PublicProjectViewSet
        vs = PublicProjectViewSet()
        vs.kwargs = {}
        vs.format_kwarg = None
        return vs

    def _make_request(self, template_name="report", lang="en"):
        request = Mock()
        request.query_params = {"template": template_name, "lang": lang}
        if hasattr(request, "LANGUAGE_CODE"):
            del request.LANGUAGE_CODE  # avoid the hasattr branch overriding lang
        return request

    def test_returns_generic_error_message_not_raw_exception_text(self):
        """public template() response body contains generic text, not the raw exception message."""
        viewset = self._make_viewset()
        request = self._make_request()

        secret_message = "internal db credentials leaked here"

        with (
            patch("os.path.exists", return_value=True),
            patch("api.reports.compute_project_result", side_effect=RuntimeError(secret_message)),
            patch("api.models.Project") as mock_project_cls,
            patch("public.views.get_object_or_404") as mock_get_obj,
            patch("public.views.log") as mock_log,
        ):
            mock_get_obj.return_value = Mock()
            response = viewset.template(request, pk=1)

        # Response body must NOT contain the raw exception text
        response_body = str(response.data)
        self.assertNotIn(secret_message, response_body)

        # Response body MUST contain the generic error message
        self.assertIn("unexpected error", response_body.lower())

    def test_log_exception_is_called_on_unexpected_error(self):
        """public template() calls log.exception() when build_template_context raises."""
        viewset = self._make_viewset()
        request = self._make_request()
        exc = RuntimeError("boom")

        with (
            patch("os.path.exists", return_value=True),
            patch("api.reports.compute_project_result", side_effect=exc),
            patch("public.views.get_object_or_404", return_value=Mock()),
            patch("public.views.log") as mock_log,
        ):
            viewset.template(request, pk=1)

        mock_log.exception.assert_called_once_with(exc)

    def test_returns_500_status_on_unexpected_error(self):
        """public template() returns HTTP 500 when an unexpected exception is raised."""
        viewset = self._make_viewset()
        request = self._make_request()

        with (
            patch("os.path.exists", return_value=True),
            patch("api.reports.compute_project_result", side_effect=RuntimeError("crash")),
            patch("public.views.get_object_or_404", return_value=Mock()),
            patch("public.views.log"),
        ):
            response = viewset.template(request, pk=1)

        self.assertEqual(response.status_code, 500)


class TestApiProjectViewSetTemplateErrorHandling(unittest.TestCase):
    """Fix 4 (api view): template() returns a generic message and calls log.exception."""

    def _make_viewset(self, project=None):
        from api.views import ProjectViewSet
        vs = ProjectViewSet()
        vs.kwargs = {"pk": 1}
        vs.format_kwarg = None
        vs.request = Mock()
        vs.request.user = Mock()
        if project is None:
            project = Mock()
        vs.get_object = Mock(return_value=project)
        return vs

    def _make_request(self, template_name="report", lang="en"):
        request = Mock()
        request.query_params = {"template": template_name, "lang": lang}
        return request

    def test_returns_generic_error_message_not_raw_exception_text(self):
        """api template() response body contains generic text, not the raw exception message."""
        viewset = self._make_viewset()
        request = self._make_request()

        secret_message = "secret db password exposed"

        with (
            patch("os.path.exists", return_value=True),
            patch("api.reports.compute_project_result", side_effect=RuntimeError(secret_message)),
            patch("api.views.log", create=True) as mock_log,
        ):
            response = viewset.template(request, pk=1)

        response_body = str(response.data)
        self.assertNotIn(secret_message, response_body)
        self.assertIn("unexpected error", response_body.lower())

    def test_returns_500_status_on_unexpected_error(self):
        """api template() returns HTTP 500 when an unexpected exception is raised."""
        viewset = self._make_viewset()
        request = self._make_request()

        with (
            patch("os.path.exists", return_value=True),
            patch("api.reports.compute_project_result", side_effect=RuntimeError("crash")),
            patch("api.views.log", create=True),
        ):
            response = viewset.template(request, pk=1)

        self.assertEqual(response.status_code, 500)

    def test_log_exception_called_on_unexpected_error(self):
        """api template() calls log.exception() when build_template_context raises."""
        viewset = self._make_viewset()
        request = self._make_request()
        exc = RuntimeError("boom")

        with (
            patch("os.path.exists", return_value=True),
            patch("api.reports.compute_project_result", side_effect=exc),
            patch("api.views.log", create=True) as mock_log,
        ):
            viewset.template(request, pk=1)

        mock_log.exception.assert_called_once_with(exc)
