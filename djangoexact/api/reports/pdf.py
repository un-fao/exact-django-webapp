"""The one place report HTML becomes PDF bytes.

WeasyPrint fetches every URL the document names, file:// included, so a report
that carries analyst-supplied markup must not be rendered with the default
fetcher. The sanitizer in api.reports.narrative is the first layer; this
allowlist is the second, and it holds even if markup reaches the page some
other way.
"""
from __future__ import annotations

# The FAO templates link Bootstrap from the CDN. Everything else the templates
# embed (logo, charts) is a data: URI built server-side.
ALLOWED_URLS = frozenset({
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
})


def is_fetchable(url: str) -> bool:
    return url.startswith("data:") or url in ALLOWED_URLS


def render_pdf(html: str) -> bytes:
    # Imported here because WeasyPrint needs native libraries that are not
    # present on every dev machine; importing at module level would break the
    # test suite there.
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    class AllowlistFetcher(URLFetcher):
        def fetch(self, url, headers=None):
            if not is_fetchable(url):
                # WeasyPrint logs this and renders the document without the resource.
                raise ValueError("URL is not on the report allowlist")
            return super().fetch(url, headers)

    return HTML(string=html, url_fetcher=AllowlistFetcher()).write_pdf()
