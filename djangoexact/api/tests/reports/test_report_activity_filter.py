"""Guard: ?activities= must mean the same thing on every path that accepts it.

report() and the async worker both narrowed the carbon balance to the selected
activities. template(), which serves the PDF, called compute_project_result
with no activities at all, so the same request produced a different document
depending on whether it was served synchronously or from a job.

The parse itself was hand-rolled in five places. It lives in
api.utilities.requested_activity_ids now, so a change to what counts as a valid
id cannot apply to some endpoints and not others.

Run with:
    python manage.py test api.tests.reports.test_report_activity_filter
"""
from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from api.utilities import requested_activity_ids


def _request(activities=None, **params):
    query = dict(params)
    if activities is not None:
        query["activities"] = activities
    request = Mock()
    request.query_params = query
    del request.LANGUAGE_CODE
    return request


class RequestedActivityIdsTestCase(SimpleTestCase):
    def test_absent_parameter_selects_nothing_explicitly(self):
        self.assertEqual(requested_activity_ids(_request()), [])
        self.assertEqual(requested_activity_ids(_request(activities="")), [])

    def test_ids_are_parsed_and_whitespace_trimmed(self):
        self.assertEqual(requested_activity_ids(_request(activities="41, 42 ,43")), ["41", "42", "43"])

    def test_non_numeric_entries_are_dropped(self):
        """Preserved from the five copies this replaced, not endorsed."""
        self.assertEqual(requested_activity_ids(_request(activities="41,abc,,42")), ["41", "42"])


class TemplateHonoursTheActivityFilterTestCase(SimpleTestCase):
    """The sync PDF path must narrow the computation the way the other paths do."""

    def _call_template(self, activities):
        from api.views import ProjectViewSet

        viewset = ProjectViewSet()
        viewset.kwargs = {"pk": 1}
        viewset.format_kwarg = None
        viewset.request = Mock()

        project = Mock()
        project.activities.filter.return_value = ["activity-41", "activity-42"]
        viewset.get_object = Mock(return_value=project)

        request = _request(activities=activities, template="fao", lang="en")
        with (
            patch("api.reports.compute_project_result", return_value=Mock()) as compute,
            patch("api.reports.html_context.build_template_context", return_value={}),
            patch("api.views.render", return_value=Mock(content=b"<html></html>")),
        ):
            # WeasyPrint cannot be imported on every dev machine, so the call may
            # fall into the view's own error path. What matters is the argument
            # compute_project_result was handed before that.
            viewset.template(request, pk=1)
        return project, compute

    def test_selected_activities_are_passed_to_the_computation(self):
        project, compute = self._call_template("41,42")
        project.activities.filter.assert_called_once_with(pk__in=["41", "42"])
        self.assertEqual(compute.call_args.args[1], ["activity-41", "activity-42"])

    def test_no_filter_still_computes_the_whole_project(self):
        project, compute = self._call_template(None)
        project.activities.filter.assert_not_called()
        self.assertIsNone(compute.call_args.args[1])
