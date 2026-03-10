import time
from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase, override_settings


@override_settings(
    BUG_REPORT_ENDPOINT="https://example.com/api/bug-report",
    BUG_REPORT_THROTTLE_SECONDS=300,
    BUG_REPORT_MAX_REPORTS=50,
    BUG_REPORT_BUFFER_SIZE=20,
)
class ErrorReporterTests(SimpleTestCase):
    def setUp(self):
        from bug_report.reporter import ErrorReporter

        self.reporter = ErrorReporter()

    def test_report_sends_payload_to_endpoint(self):
        """Report POSTs JSON payload to configured endpoint."""
        payload = {"error": {"type": "ValueError", "message": "test"}}
        with patch("bug_report.reporter.urlopen") as mock_urlopen:
            mock_urlopen.return_value = MagicMock()
            self.reporter.send_report(payload)
            mock_urlopen.assert_called_once()
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            self.assertEqual(request.full_url, "https://example.com/api/bug-report")
            self.assertEqual(request.get_header("Content-type"), "application/json")

    def test_throttle_blocks_duplicate_within_window(self):
        """Same throttle key within window is blocked."""
        self.reporter.should_send("ValueError:/api/test/")
        self.assertFalse(self.reporter.should_send("ValueError:/api/test/"))

    def test_throttle_allows_different_keys(self):
        """Different throttle keys are independent."""
        self.reporter.should_send("ValueError:/api/test/")
        self.assertTrue(self.reporter.should_send("TypeError:/api/other/"))

    def test_throttle_allows_after_window_expires(self):
        """Same key allowed again after throttle window."""
        self.reporter.should_send("ValueError:/api/test/")
        # Manually expire the entry
        for key in self.reporter._throttle_map:
            self.reporter._throttle_map[key] = time.time() - 301
        self.assertTrue(self.reporter.should_send("ValueError:/api/test/"))

    def test_session_cap_enforced(self):
        """No more reports after session cap reached."""
        self.reporter._report_count = 50
        self.assertFalse(self.reporter.should_send("ValueError:/api/new/"))

    @override_settings(BUG_REPORT_ENDPOINT="")
    def test_disabled_when_no_endpoint(self):
        """Reporter is disabled when endpoint is empty."""
        from bug_report.reporter import ErrorReporter

        reporter = ErrorReporter()
        self.assertFalse(reporter.is_enabled())

    def test_enabled_when_endpoint_configured(self):
        """Reporter is enabled when endpoint is set."""
        self.assertTrue(self.reporter.is_enabled())

    def test_report_async_spawns_daemon_thread(self):
        """report_async spawns a background daemon thread."""
        with patch.object(self.reporter, "send_report") as mock_send:
            payload = {"error": {"type": "ValueError"}}
            self.reporter.report_async(payload)
            import time; time.sleep(0.05)
            mock_send.assert_called_once_with(payload)

    def test_send_report_silently_fails_on_error(self):
        """Network errors are swallowed, not raised."""
        payload = {"error": {"type": "ValueError", "message": "test"}}
        with patch("bug_report.reporter.urlopen", side_effect=Exception("network error")):
            # Should not raise
            self.reporter.send_report(payload)
