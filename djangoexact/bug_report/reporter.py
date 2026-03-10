import json
import logging
import threading
import time
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class ErrorReporter:
    """Sends error reports to an external endpoint with throttling."""

    def __init__(self):
        self._throttle_map = {}  # {throttle_key: last_sent_timestamp}
        self._report_count = 0
        self._lock = threading.Lock()

    def is_enabled(self):
        endpoint = getattr(settings, "BUG_REPORT_ENDPOINT", "")
        return bool(endpoint)

    def should_send(self, throttle_key):
        """Check if a report should be sent, updating throttle state if yes."""
        max_reports = getattr(settings, "BUG_REPORT_MAX_REPORTS", 50)
        throttle_seconds = getattr(settings, "BUG_REPORT_THROTTLE_SECONDS", 300)

        with self._lock:
            if self._report_count >= max_reports:
                return False

            now = time.time()
            last_sent = self._throttle_map.get(throttle_key)
            if last_sent and (now - last_sent) < throttle_seconds:
                return False

            self._throttle_map[throttle_key] = now
            self._report_count += 1

            # Clean stale entries
            stale_keys = [
                k
                for k, v in self._throttle_map.items()
                if (now - v) > throttle_seconds
            ]
            for k in stale_keys:
                if k != throttle_key:
                    del self._throttle_map[k]

            return True

    def send_report(self, payload):
        """POST the payload to the configured endpoint. Silently fails."""
        endpoint = getattr(settings, "BUG_REPORT_ENDPOINT", "")
        if not endpoint:
            return

        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                endpoint,
                data=data,
                headers={"Content-type": "application/json"},
                method="POST",
            )
            urlopen(request, timeout=5)
        except Exception:
            logger.debug("Bug report delivery failed", exc_info=True)

    def report_async(self, payload):
        """Send report in a background daemon thread."""
        thread = threading.Thread(
            target=self.send_report, args=(payload,), daemon=True
        )
        thread.start()
