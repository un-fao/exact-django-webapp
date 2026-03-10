import json
import time
from collections import deque
from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.http import HttpResponse, JsonResponse


@override_settings(
    BUG_REPORT_ENDPOINT="https://example.com/api/bug-report",
    BUG_REPORT_THROTTLE_SECONDS=300,
    BUG_REPORT_MAX_REPORTS=50,
    BUG_REPORT_BUFFER_SIZE=20,
)
class BugReportMiddlewareTests(SimpleTestCase):
    def setUp(self):
        from bug_report.middleware import BugReportMiddleware

        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=HttpResponse("OK", status=200))
        self.middleware = BugReportMiddleware(self.get_response)

    def test_passes_through_2xx_responses(self):
        """2xx responses pass through without triggering a report."""
        request = self.factory.get("/api/test/")
        with patch.object(self.middleware.reporter, "report_async") as mock_report:
            self.middleware(request)
            mock_report.assert_not_called()

    def test_passes_through_4xx_responses(self):
        """4xx responses pass through without triggering a report."""
        self.get_response.return_value = HttpResponse("Not Found", status=404)
        request = self.factory.get("/api/test/")
        with patch.object(self.middleware.reporter, "report_async") as mock_report:
            self.middleware(request)
            mock_report.assert_not_called()

    def test_triggers_report_on_5xx_response(self):
        """5xx responses trigger an error report."""
        self.get_response.return_value = HttpResponse("Server Error", status=500)
        request = self.factory.get("/api/test/")
        request.user = MagicMock(id=1, email="test@fao.org", is_authenticated=True)
        with patch.object(self.middleware.reporter, "should_send", return_value=True):
            with patch.object(self.middleware.reporter, "report_async") as mock_report:
                self.middleware(request)
                mock_report.assert_called_once()
                payload = mock_report.call_args[0][0]
                self.assertEqual(payload["error"]["status_code"], 500)
                self.assertEqual(payload["request"]["method"], "GET")
                self.assertEqual(payload["request"]["path"], "/api/test/")

    def test_request_buffer_records_requests(self):
        """Ring buffer records requests up to configured size."""
        for i in range(25):
            request = self.factory.get(f"/api/test/{i}/")
            self.middleware(request)
        self.assertEqual(len(self.middleware._request_buffer), 20)

    def test_request_buffer_entry_format(self):
        """Buffer entries contain expected fields."""
        request = self.factory.post(
            "/api/test/",
            data='{"key": "value"}',
            content_type="application/json",
        )
        self.middleware(request)
        entry = self.middleware._request_buffer[0]
        self.assertIn("timestamp", entry)
        self.assertEqual(entry["method"], "POST")
        self.assertEqual(entry["path"], "/api/test/")
        self.assertIn("duration_ms", entry)

    def test_body_truncated_to_2kb(self):
        """Request body is truncated to 2KB in buffer entries."""
        large_body = "x" * 5000
        request = self.factory.post(
            "/api/test/", data=large_body, content_type="text/plain"
        )
        self.middleware(request)
        entry = self.middleware._request_buffer[0]
        self.assertLessEqual(len(entry.get("body_snippet", "")), 2048)

    def test_sensitive_fields_redacted(self):
        """Password and token fields are redacted in body snippet."""
        body = json.dumps({"password": "secret123", "token": "abc", "name": "test"})
        request = self.factory.post(
            "/api/test/", data=body, content_type="application/json"
        )
        self.middleware(request)
        entry = self.middleware._request_buffer[0]
        self.assertNotIn("secret123", entry.get("body_snippet", ""))
        self.assertNotIn("abc", entry.get("body_snippet", ""))

    def test_process_exception_captures_traceback(self):
        """Unhandled exceptions are captured with traceback.

        When an exception is raised in get_response, the middleware catches it,
        stores exception info on the request, then builds a 500 response and
        triggers the report before re-raising. We verify the payload contains
        the exception type and traceback.
        """
        def raise_error(request):
            raise ValueError("test exception")

        from bug_report.middleware import BugReportMiddleware

        middleware = BugReportMiddleware(raise_error)

        request = self.factory.get("/api/test/")
        request.user = MagicMock(id=1, email="test@fao.org", is_authenticated=True)

        with patch.object(middleware.reporter, "should_send", return_value=True):
            with patch.object(middleware.reporter, "report_async") as mock_report:
                with self.assertRaises(ValueError):
                    middleware(request)

                mock_report.assert_called_once()
                payload = mock_report.call_args[0][0]
                self.assertEqual(payload["error"]["type"], "ValueError")
                self.assertIn("test exception", payload["error"]["traceback"])

    @override_settings(BUG_REPORT_ENDPOINT="")
    def test_middleware_inert_when_disabled(self):
        """Middleware does nothing when endpoint is not configured."""
        from bug_report.middleware import BugReportMiddleware

        get_response = MagicMock(return_value=HttpResponse("Error", status=500))
        mw = BugReportMiddleware(get_response)
        request = self.factory.get("/api/test/")
        with patch.object(mw.reporter, "report_async") as mock_report:
            mw(request)
            mock_report.assert_not_called()

    def test_report_includes_recent_requests(self):
        """Error report includes recent request buffer.

        The failing request itself is also recorded in the buffer before the
        report is sent, so the total is prior requests + the failing one.
        """
        for i in range(3):
            request = self.factory.get(f"/api/ok/{i}/")
            self.middleware(request)

        self.get_response.return_value = HttpResponse("Error", status=500)
        request = self.factory.get("/api/fail/")
        request.user = MagicMock(id=1, email="test@fao.org", is_authenticated=True)
        with patch.object(self.middleware.reporter, "should_send", return_value=True):
            with patch.object(self.middleware.reporter, "report_async") as mock_report:
                self.middleware(request)
                payload = mock_report.call_args[0][0]
                # 3 prior + 1 failing request = 4 entries
                self.assertEqual(len(payload["recent_requests"]), 4)

    def test_user_context_for_authenticated_user(self):
        """Report includes user info for authenticated users."""
        self.get_response.return_value = HttpResponse("Error", status=500)
        request = self.factory.get("/api/test/")
        request.user = MagicMock(id=42, email="user@fao.org", is_authenticated=True)
        request.user.profile.organization = "FAO HQ"
        with patch.object(self.middleware.reporter, "should_send", return_value=True):
            with patch.object(self.middleware.reporter, "report_async") as mock_report:
                self.middleware(request)
                payload = mock_report.call_args[0][0]
                self.assertEqual(payload["user"]["id"], 42)
                self.assertEqual(payload["user"]["email"], "user@fao.org")

    def test_user_context_for_anonymous_user(self):
        """Report handles anonymous users gracefully."""
        self.get_response.return_value = HttpResponse("Error", status=500)
        request = self.factory.get("/api/test/")
        request.user = MagicMock(is_authenticated=False)
        with patch.object(self.middleware.reporter, "should_send", return_value=True):
            with patch.object(self.middleware.reporter, "report_async") as mock_report:
                self.middleware(request)
                payload = mock_report.call_args[0][0]
                self.assertIsNone(payload["user"]["id"])
