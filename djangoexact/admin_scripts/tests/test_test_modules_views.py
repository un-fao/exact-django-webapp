"""View tests for the Test All Modules admin script."""
from unittest.mock import patch

from django.test import Client, TransactionTestCase, override_settings

from admin_scripts.models import ComputationJob, ModuleTestRun
from api.models import CustomUser

MIDDLEWARE_WITHOUT_DB_CLEANUP = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]


@override_settings(MIDDLEWARE=MIDDLEWARE_WITHOUT_DB_CLEANUP)
class TestModulesViewsTest(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        self.client = Client()
        self.staff = CustomUser.objects.create_user(
            email="staff@example.com", password="x", is_staff=True,
            firebase_uid="staff_v",
        )
        self.other_staff = CustomUser.objects.create_user(
            email="other@example.com", password="x", is_staff=True,
            firebase_uid="other_v",
        )
        self.regular = CustomUser.objects.create_user(
            email="reg@example.com", password="x", is_staff=False,
            firebase_uid="reg_v",
        )

    # ---------- access control ----------

    def test_landing_redirects_unauthenticated(self):
        response = self.client.get("/api/admin-scripts/test-modules/")
        self.assertEqual(response.status_code, 302)

    def test_landing_forbidden_for_non_staff(self):
        self.client.login(email="reg@example.com", password="x")
        response = self.client.get("/api/admin-scripts/test-modules/")
        self.assertEqual(response.status_code, 403)

    def test_landing_renders_for_staff(self):
        self.client.login(email="staff@example.com", password="x")
        response = self.client.get("/api/admin-scripts/test-modules/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test All Modules")

    # ---------- POST creates a run ----------

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_post_creates_run_and_jobs(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [
                {"module_type": "Grassland", "field_name": "is_fire_used",
                 "from_value": "True", "to_value": "False"},
                {"module_type": "Grassland", "field_name": "fire_impact",
                 "from_value": "1", "to_value": "0"},
            ],
            [
                {"module_type": "Grassland", "field_name": "fire_periodicity",
                 "reason": "only 1 distinct value(s) available"},
            ],
        )
        self.client.login(email="staff@example.com", password="x")
        response = self.client.post("/api/admin-scripts/test-modules/")
        self.assertEqual(response.status_code, 302)

        run = ModuleTestRun.objects.get(requested_by=self.staff)
        self.assertEqual(run.jobs.count(), 2)
        for job in run.jobs.all():
            self.assertEqual(job.max_rows, 100)
        self.assertEqual(len(run.skipped), 1)
        self.assertEqual(run.skipped[0]["field_name"], "fire_periodicity")
        self.assertTrue(response.url.endswith(f"/test-modules/{run.id}/"))

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_post_with_all_skipped_creates_empty_run(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [],
            [{"module_type": "Grassland", "field_name": "f", "reason": "no values available"}],
        )
        self.client.login(email="staff@example.com", password="x")
        response = self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)
        self.assertEqual(run.jobs.count(), 0)
        self.assertEqual(len(run.skipped), 1)
        mock_dispatch.assert_not_called()
        self.assertEqual(response.status_code, 302)

    # ---------- detail page ----------

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_detail_renders_for_owner(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [{"module_type": "Grassland", "field_name": "is_fire_used",
              "from_value": "True", "to_value": "False"}],
            [],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        response = self.client.get(f"/api/admin-scripts/test-modules/{run.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Grassland")
        self.assertContains(response, "is_fire_used")

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_detail_404_for_other_user(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [{"module_type": "Grassland", "field_name": "is_fire_used",
              "from_value": "True", "to_value": "False"}],
            [],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        self.client.logout()
        self.client.login(email="other@example.com", password="x")
        response = self.client.get(f"/api/admin-scripts/test-modules/{run.id}/")
        self.assertEqual(response.status_code, 404)

    # ---------- status partial polling lifecycle ----------

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_status_partial_polls_while_pending(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [{"module_type": "Grassland", "field_name": "is_fire_used",
              "from_value": "True", "to_value": "False"}],
            [],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        response = self.client.get(
            f"/api/admin-scripts/test-modules/{run.id}/status/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-trigger="every 3s"')
        run.refresh_from_db()
        self.assertIsNone(run.completed_at)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_status_partial_stops_polling_when_all_terminal(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [{"module_type": "Grassland", "field_name": "is_fire_used",
              "from_value": "True", "to_value": "False"}],
            [],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        # Force all jobs into a terminal state.
        run.jobs.all().update(status=ComputationJob.Status.COMPLETED)

        response = self.client.get(
            f"/api/admin-scripts/test-modules/{run.id}/status/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "hx-trigger")
        run.refresh_from_db()
        self.assertIsNotNone(run.completed_at)

    @patch("admin_scripts.job_dispatcher.dispatch_job")
    @patch("admin_scripts.views.plan_module_tests")
    def test_status_partial_treats_empty_run_as_complete(self, mock_plan, mock_dispatch):
        mock_plan.return_value = (
            [],
            [{"module_type": "Grassland", "field_name": "f", "reason": "no values available"}],
        )
        self.client.login(email="staff@example.com", password="x")
        self.client.post("/api/admin-scripts/test-modules/")
        run = ModuleTestRun.objects.get(requested_by=self.staff)

        response = self.client.get(
            f"/api/admin-scripts/test-modules/{run.id}/status/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "hx-trigger")
        run.refresh_from_db()
        self.assertIsNotNone(run.completed_at)
