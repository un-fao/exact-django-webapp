"""Both report actions must document a { content } body. Without an explicit
request_body, drf-yasg falls back to the viewset's ProjectSerializer."""
from django.test import SimpleTestCase


class ReportSwaggerBodyTestCase(SimpleTestCase):
    def test_both_report_actions_document_the_content_body(self):
        paths = self.client.get("/api/swagger.json").json()["paths"]
        for url in ("/projects/{id}/report/", "/projects/{id}/report/async/"):
            with self.subTest(url=url):
                body = next(p for p in paths[url]["post"]["parameters"] if p["in"] == "body")
                self.assertEqual(list(body["schema"]["properties"]), ["content"])
