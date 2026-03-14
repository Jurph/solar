"""
Tests for views/logs.py and services/log_buffer.py.

Covers:
- InMemoryLogHandler: emit() filtering (numba, urllib3, httpx, favicon)
- InMemoryLogHandler: tail() method
- logs_view: basic response shape
- logs_view: ?level= sets root logger level
- logs_view: ?min_level= filters returned records
- logs_view: ?n= limits tail length
"""

import logging

from django.test import Client, TestCase
from django.urls import reverse

from mysite.universe.services.log_buffer import InMemoryLogHandler, get_log_handler


# ---------------------------------------------------------------------------
# InMemoryLogHandler unit tests
# ---------------------------------------------------------------------------


class TestInMemoryLogHandlerFilters(TestCase):
    """Direct unit tests for InMemoryLogHandler.emit() filter rules."""

    def _make_handler(self) -> InMemoryLogHandler:
        h = InMemoryLogHandler(maxlen=50)
        h.setFormatter(logging.Formatter("%(message)s"))
        return h

    def _record(self, name: str, level: int, message: str) -> logging.LogRecord:
        record = logging.LogRecord(
            name=name,
            level=level,
            pathname="test",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        return record

    def test_numba_debug_logs_are_filtered(self):
        """DEBUG records from numba.* are silently dropped."""
        h = self._make_handler()
        h.emit(self._record("numba.byteflow", logging.DEBUG, "spam"))
        self.assertEqual(len(h.tail()), 0)

    def test_urllib3_debug_logs_are_filtered(self):
        """DEBUG records from urllib3.* are silently dropped."""
        h = self._make_handler()
        h.emit(self._record("urllib3.connectionpool", logging.DEBUG, "GET /api"))
        self.assertEqual(len(h.tail()), 0)

    def test_httpx_debug_logs_are_filtered(self):
        """DEBUG records from httpx are silently dropped."""
        h = self._make_handler()
        h.emit(self._record("httpx", logging.DEBUG, "connect"))
        self.assertEqual(len(h.tail()), 0)

    def test_favicon_messages_are_filtered_at_any_level(self):
        """Records whose message contains 'favicon.ico' are silently dropped."""
        h = self._make_handler()
        h.emit(
            self._record(
                "django.request", logging.WARNING, "GET /favicon.ico returned 404"
            )
        )
        self.assertEqual(len(h.tail()), 0)

    def test_numba_info_logs_are_kept(self):
        """INFO records from numba.* pass through (only DEBUG is filtered)."""
        h = self._make_handler()
        h.emit(self._record("numba.core", logging.INFO, "important"))
        self.assertEqual(len(h.tail()), 1)

    def test_normal_debug_logs_are_kept(self):
        """DEBUG records from application loggers are kept."""
        h = self._make_handler()
        h.emit(self._record("mysite.universe", logging.DEBUG, "debug msg"))
        self.assertEqual(len(h.tail()), 1)

    def test_tail_returns_last_n_records(self):
        """tail(n) returns at most the n most recent records."""
        h = self._make_handler()
        for i in range(10):
            h.emit(self._record("app", logging.INFO, f"msg {i}"))
        tail = h.tail(3)
        self.assertEqual(len(tail), 3)
        self.assertEqual(tail[-1]["message"], "msg 9")

    def test_tail_default_returns_all_up_to_100(self):
        """tail() with no argument returns up to 100 records."""
        h = self._make_handler()
        for i in range(5):
            h.emit(self._record("app", logging.INFO, f"entry {i}"))
        tail = h.tail()
        self.assertEqual(len(tail), 5)

    def test_entry_has_expected_keys(self):
        """Each log entry has 'level', 'name', and 'message' keys."""
        h = self._make_handler()
        h.emit(self._record("mysite.test", logging.ERROR, "oops"))
        entry = h.tail(1)[0]
        self.assertIn("level", entry)
        self.assertIn("name", entry)
        self.assertIn("message", entry)
        self.assertEqual(entry["level"], "ERROR")
        self.assertEqual(entry["name"], "mysite.test")


# ---------------------------------------------------------------------------
# logs_view endpoint tests
# ---------------------------------------------------------------------------


class TestLogsView(TestCase):
    """Tests for the GET /api/logs/ endpoint."""

    def setUp(self):
        self.client = Client()
        # Inject some known records into the global handler before each test.
        handler = get_log_handler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.buffer.clear()
        for level, msg in [
            (logging.DEBUG, "debug message"),
            (logging.INFO, "info message"),
            (logging.WARNING, "warning message"),
            (logging.ERROR, "error message"),
        ]:
            record = logging.LogRecord(
                name="mysite.test",
                level=level,
                pathname="test",
                lineno=0,
                msg=msg,
                args=(),
                exc_info=None,
            )
            handler.emit(record)

    def test_basic_get_returns_200_with_logs_key(self):
        url = reverse("logs_view")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("logs", data)
        self.assertIn("filtered", data)

    def test_min_level_info_excludes_debug(self):
        """?min_level=INFO should exclude DEBUG records."""
        url = reverse("logs_view")
        resp = self.client.get(url, {"min_level": "INFO"})
        data = resp.json()
        levels = [entry["level"] for entry in data["logs"]]
        self.assertNotIn("DEBUG", levels)
        # filtered count should be 1 (the DEBUG record)
        self.assertGreaterEqual(data["filtered"], 1)

    def test_min_level_error_only_shows_errors(self):
        """?min_level=ERROR should only include ERROR and CRITICAL."""
        url = reverse("logs_view")
        resp = self.client.get(url, {"min_level": "ERROR"})
        data = resp.json()
        allowed = {"ERROR", "CRITICAL"}
        for entry in data["logs"]:
            self.assertIn(entry["level"], allowed)

    def test_min_level_warn_alias_works(self):
        """?min_level=WARN is treated as WARNING."""
        url = reverse("logs_view")
        resp = self.client.get(url, {"min_level": "WARN"})
        data = resp.json()
        self.assertEqual(resp.status_code, 200)
        for entry in data["logs"]:
            self.assertIn(entry["level"], {"WARNING", "ERROR", "CRITICAL"})

    def test_n_parameter_limits_results(self):
        """?n=2 should limit the tail to 2 records."""
        url = reverse("logs_view")
        resp = self.client.get(url, {"n": "2"})
        data = resp.json()
        # With no min_level filter, we get up to 2 total from tail
        self.assertLessEqual(len(data["logs"]), 2)

    def test_invalid_n_returns_400(self):
        """A non-integer ?n should return a helpful 400 instead of a 500."""
        url = reverse("logs_view")
        resp = self.client.get(url, {"n": "abc"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["status"], "error")

    def test_negative_n_returns_400(self):
        """A negative ?n should be rejected instead of slicing oddly."""
        url = reverse("logs_view")
        resp = self.client.get(url, {"n": "-1"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["status"], "error")

    def test_level_param_does_not_crash(self):
        """?level=DEBUG should set root logger level without crashing."""
        url = reverse("logs_view")
        resp = self.client.get(url, {"level": "DEBUG"})
        self.assertEqual(resp.status_code, 200)

    def test_post_rejected(self):
        """Only GET is allowed; POST should return 405."""
        url = reverse("logs_view")
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 405)

    def test_invalid_level_param_does_not_crash(self):
        """?level=INVALID_NONSENSE triggers the except-pass branch and still returns 200."""
        url = reverse("logs_view")
        resp = self.client.get(url, {"level": "INVALID_NONSENSE"})
        self.assertEqual(resp.status_code, 200)
        # Response should still have the logs key
        self.assertIn("logs", resp.json())
