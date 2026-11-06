"""Guard: a module that cannot be calculated is a 422 on the PDF path too.

The Excel path (report/) already answered NotReadyError with a 422 naming
the module. The PDF path (template/) folded it into a generic 500, "An
unexpected error occurred while generating the PDF", so users could not
tell which activity to fix (project 9908 on review).

Run with:
    python manage.py test api.tests.reports.test_template_not_ready
"""
from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import SimpleTestCase


class TemplateNotReadyTestCase(SimpleTestCase):
    def test_not_ready_module_is_a_422_with_its_message(self):
        from api.reports import NotReadyError
        from api.views import ProjectViewSet

        viewset = ProjectViewSet()
        viewset.kwargs = {"pk": 1}
        viewset.format_kwarg = None
        viewset.request = Mock()
        project = Mock()
        project.activities.filter.return_value = []
        viewset.get_object = Mock(return_value=project)

        request = Mock()
        request.query_params = {"template": "ifad"}
        request.data = {}
        del request.LANGUAGE_CODE

        message = "Cannot calculate report for module Grassland in activity 3-Activity: Fire interval must be greater than 0 if fire is used"
        with patch("api.reports.compute_project_result", side_effect=NotReadyError(message)):
            response = viewset.template(request, pk=1)

        self.assertEqual(response.status_code, 422)
        self.assertIn(message, str(response.data))
