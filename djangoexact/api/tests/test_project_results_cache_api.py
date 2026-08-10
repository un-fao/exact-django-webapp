"""API-level tests for the project results cache (ProjectResultCache).

Requires Postgres: these are rest_framework.test.APITestCase, which needs Django's
TestCase transaction machinery against a real database. This sandbox has no local
Postgres/Docker, so this module is CI-gated / DB-equipped-machine-gated only, not
runnable here. See api/tests/test_results_cache.py for the database-free coverage of
build_cache_key and normalize_payload.

Run in CI with: python manage.py test api.tests.test_project_results_cache_api
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import force_authenticate

import api.models as models
from api.views import ProjectViewSet
from api.tests.unit.utils import APITestCaseMixin


class ProjectResultsCacheAPITestCase(APITestCaseMixin):
    def setUp(self):
        super().setUp()
        create_project_response = self.create_project()
        self.assertEqual(create_project_response.status_code, status.HTTP_201_CREATED)
        self.project = models.Project.objects.get(id=create_project_response.data["id"])

        create_activity_response = self.create_activity(self.project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        self.activity = models.Activity.objects.get(id=create_activity_response.data["id"])

    def _get_results(self, query_string=""):
        view = ProjectViewSet.as_view({"get": "results"})
        url = reverse("project-results", args=[self.project.id])
        if query_string:
            url = f"{url}?{query_string}"
        request = self.request_factory.get(url, format="json")
        force_authenticate(request, user=self.user)
        return view(request, pk=self.project.id)

    def test_two_consecutive_calls_return_equal_bodies_both_200(self):
        first = self._get_results()
        second = self._get_results()

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data, second.data)

    def test_second_call_creates_no_additional_cache_row(self):
        self._get_results()
        rows_after_first = models.ProjectResultCache.objects.filter(project=self.project).count()

        self._get_results()
        rows_after_second = models.ProjectResultCache.objects.filter(project=self.project).count()

        self.assertEqual(rows_after_first, 1)
        self.assertEqual(rows_after_second, 1)

    def test_editing_a_module_between_calls_advances_stamp_and_recomputes(self):
        first = self._get_results()
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        self.project.refresh_from_db()
        stamp_after_first = self.project.results_stamp

        module = self.activity.modules[0]
        module.save()  # touching last_modified-relevant fields via CachedResultMixin.save

        from api.models import invalidate_module_caches
        invalidate_module_caches(activity=self.activity)

        self.project.refresh_from_db()
        self.assertGreater(self.project.results_stamp, stamp_after_first)

        second = self._get_results()
        self.assertEqual(second.status_code, status.HTTP_200_OK)

        cached_row = models.ProjectResultCache.objects.get(
            project=self.project,
            results_stamp=self.project.results_stamp,
        )
        self.assertEqual(cached_row.results_stamp, self.project.results_stamp)
        self.assertNotEqual(cached_row.results_stamp, stamp_after_first)

    def test_cached_false_bypasses_the_stored_row_and_still_returns_200(self):
        self._get_results()

        response = self._get_results(query_string="cached=false")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_activities_param_order_hits_the_same_row(self):
        create_activity_response = self.create_activity(self.project, self.user)
        self.assertEqual(create_activity_response.status_code, status.HTTP_200_OK)
        second_activity = models.Activity.objects.get(id=create_activity_response.data["id"])

        pks = sorted([self.activity.id, second_activity.id])

        forward = self._get_results(query_string=f"activities={pks[0]},{pks[1]}")
        reverse_order = self._get_results(query_string=f"activities={pks[1]},{pks[0]}")

        self.assertEqual(forward.status_code, status.HTTP_200_OK)
        self.assertEqual(reverse_order.status_code, status.HTTP_200_OK)
        self.assertEqual(
            models.ProjectResultCache.objects.filter(project=self.project).count(),
            1,
        )

    def test_user_without_view_project_permission_gets_error_and_no_cache_touched(self):
        rows_before = models.ProjectResultCache.objects.filter(project=self.project).count()

        view = ProjectViewSet.as_view({"get": "results"})
        request = self.request_factory.get(
            reverse("project-results", args=[self.project.id]), format="json",
        )
        force_authenticate(request, user=self.user2)
        response = view(request, pk=self.project.id)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            models.ProjectResultCache.objects.filter(project=self.project).count(),
            rows_before,
        )
