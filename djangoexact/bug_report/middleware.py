import json
import logging
import os
import time
import traceback
from collections import deque
from datetime import datetime, timezone

from django.conf import settings
from django.http import HttpResponse

from .reporter import ErrorReporter

logger = logging.getLogger(__name__)

SENSITIVE_FIELDS = {"password", "token", "secret", "api_key", "apikey", "authorization"}
MAX_BODY_SIZE = 2048


class BugReportMiddleware:
    """Captures 5xx errors and sends reports to an external endpoint."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.reporter = ErrorReporter()
        buffer_size = getattr(settings, "BUG_REPORT_BUFFER_SIZE", 20)
        self._request_buffer = deque(maxlen=buffer_size)

    def __call__(self, request):
        start_time = time.time()

        request._bug_report_exception = None

        try:
            response = self.get_response(request)
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000)
            self._record_request(request, 500, duration_ms)
            self._capture_exception(request, exc)

            # Report the exception immediately since there is no response
            # object — Django's default handler would eventually return a 500,
            # but we won't see it from here.
            if self.reporter.is_enabled():
                self._handle_server_error(request, HttpResponse(status=500))

            raise

        duration_ms = round((time.time() - start_time) * 1000)

        self._record_request(request, getattr(response, "status_code", 0), duration_ms)

        if self.reporter.is_enabled() and response.status_code >= 500:
            self._handle_server_error(request, response)

        return response

    def _capture_exception(self, request, exception):
        """Capture exception details on the request object."""
        request._bug_report_exception = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc(),
        }

    def _handle_server_error(self, request, response):
        """Build and send error report for 5xx responses."""
        exc_info = getattr(request, "_bug_report_exception", None)
        error_type = exc_info["type"] if exc_info else "HTTP"
        throttle_key = f"{error_type}:{request.path}"

        if not self.reporter.should_send(throttle_key):
            return

        payload = {
            "error": self._build_error_info(response, exc_info),
            "request": self._build_request_info(request),
            "user": self._build_user_info(request),
            "app": self._build_app_info(),
            "recent_requests": list(self._request_buffer),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.reporter.report_async(payload)

    def _record_request(self, request, status_code, duration_ms):
        """Add a request entry to the ring buffer."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.path,
            "status": status_code,
            "duration_ms": duration_ms,
        }

        body_snippet = self._get_body_snippet(request)
        if body_snippet:
            entry["body_snippet"] = body_snippet

        self._request_buffer.append(entry)

    def _get_body_snippet(self, request):
        """Extract and sanitize request body."""
        try:
            body = request.body.decode("utf-8", errors="replace")[:MAX_BODY_SIZE]
        except Exception:
            return ""

        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                parsed = self._redact_sensitive(parsed)
                return json.dumps(parsed)[:MAX_BODY_SIZE]
        except (json.JSONDecodeError, TypeError):
            pass

        return body

    def _redact_sensitive(self, data):
        """Redact sensitive fields from a dict."""
        redacted = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_FIELDS:
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_sensitive(value)
            else:
                redacted[key] = value
        return redacted

    def _build_error_info(self, response, exc_info):
        """Build the error section of the report."""
        if exc_info:
            return {
                "type": exc_info["type"],
                "message": exc_info["message"],
                "traceback": exc_info["traceback"],
                "status_code": response.status_code,
            }

        body = ""
        try:
            body = response.content.decode("utf-8", errors="replace")[:MAX_BODY_SIZE]
        except Exception:
            pass

        return {
            "type": "HTTP",
            "message": body,
            "traceback": "",
            "status_code": response.status_code,
        }

    def _build_request_info(self, request):
        """Build the request section of the report."""
        return {
            "method": request.method,
            "path": request.path,
            "body_snippet": self._get_body_snippet(request),
            "query_params": dict(request.GET),
        }

    def _build_user_info(self, request):
        """Build the user section of the report."""
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            org = ""
            try:
                org = user.profile.organization
            except Exception:
                pass
            return {
                "id": user.id,
                "email": getattr(user, "email", ""),
                "organization": org,
            }
        return {"id": None, "email": "", "organization": ""}

    def _build_app_info(self):
        """Build the app context section of the report."""
        return {
            "version": os.environ.get("EXACT_APP_VERSION", "dev"),
            "platform": os.environ.get("EXACT_PLATFORM", "unknown"),
            "compatibility_group": getattr(settings, "COMPATIBILITY_GROUP", None),
        }
