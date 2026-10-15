"""Guard for what the PDF engine may fetch while rendering a report.

WeasyPrint is not importable on every dev machine, so this pins the allow
decision itself and not the fetcher class wrapped around it.

Run with:
    python manage.py test api.tests.reports.test_pdf
"""
from __future__ import annotations

from django.test import SimpleTestCase

from api.reports.pdf import ALLOWED_URLS, is_fetchable


class IsFetchableTestCase(SimpleTestCase):
    def test_embedded_data_and_the_pinned_stylesheet_are_allowed(self):
        self.assertTrue(is_fetchable("data:image/svg+xml;base64,AAAA"))
        for url in ALLOWED_URLS:
            self.assertTrue(is_fetchable(url))

    def test_everything_else_is_refused(self):
        for url in (
            "file:///etc/passwd",
            "file:///app/djangoexact/.env.production",
            "http://169.254.169.254/computeMetadata/v1/",
            "http://metadata.google.internal/",
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css?x=1",
            "https://cdn.jsdelivr.net/npm/other-package/index.css",
            "https://example.org/pixel.png",
            "ftp://example.org/x",
            "",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_fetchable(url))

    def test_allowlist_is_https_only(self):
        for url in ALLOWED_URLS:
            self.assertTrue(url.startswith("https://"))
