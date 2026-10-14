"""The frontend downloads reports with fetch() from another origin and names the
blob from Content-Disposition, which JS can only read when the header is exposed."""
from django.test import SimpleTestCase, override_settings

ORIGIN = "https://frontend.example"


class CorsExposedHeadersTestCase(SimpleTestCase):
    @override_settings(CORS_ORIGIN_ALLOW_ALL=False, CORS_ALLOWED_ORIGINS=[ORIGIN])
    def test_content_disposition_is_exposed_cross_origin(self):
        response = self.client.get("/api/report-templates/", HTTP_ORIGIN=ORIGIN)
        self.assertEqual(response["Access-Control-Allow-Origin"], ORIGIN)
        self.assertIn("content-disposition", response["Access-Control-Expose-Headers"].lower())
