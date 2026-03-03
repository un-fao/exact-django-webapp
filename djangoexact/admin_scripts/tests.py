from django.test import TestCase, Client, override_settings
from api.models import CustomUser

# The DatabaseConnectionMiddleware calls connections.close_all() after every
# request, which breaks TestCase's transaction-based isolation. We exclude it
# during tests so the test-runner's database connection stays open.
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
class AdminScriptsAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = CustomUser.objects.create_user(
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
            firebase_uid="staff_uid",
        )
        self.regular_user = CustomUser.objects.create_user(
            email="user@example.com",
            password="testpass123",
            is_staff=False,
            firebase_uid="user_uid",
        )

    def test_dashboard_redirects_unauthenticated(self):
        response = self.client.get("/api/admin-scripts/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_dashboard_forbidden_for_non_staff(self):
        self.client.login(email="user@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/")
        self.assertEqual(response.status_code, 403)

    def test_dashboard_accessible_for_staff(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Example Script")

    def test_example_script_get(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.get("/api/admin-scripts/example-script/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Example Script")

    def test_example_script_post_with_input(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/example-script/", {"name": "World"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hello, World!")

    def test_example_script_post_empty_input(self):
        self.client.login(email="staff@example.com", password="testpass123")
        response = self.client.post("/api/admin-scripts/example-script/", {"name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please provide a name")
