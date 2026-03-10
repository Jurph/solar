"""
Tests for UniverseConfig.ready() in apps.py.

Covers:
- skip_cmds early return (migrate, test, audio_worker)
- _watchdog_started flag prevents double-spawn within a process
- AUDIO_WARMUP=1 path: warm_tts_service called
- AUDIO_WARMUP=1 path: exception swallowed
- Watchdog thread is started for runserver (child process only)
- Autoreloader parent process does NOT start watchdog (#32)
- --noreload bypasses the autoreloader guard
"""

import os
import sys
from unittest.mock import MagicMock, patch

from django.test import TestCase


def _get_cfg():
    from django.apps import apps

    return apps.get_app_config("universe")


class TestUniverseConfigReady(TestCase):
    """UniverseConfig.ready() branches."""

    def _call_ready(self, argv, warmup="0", tts_side_effect=None, run_main="true"):
        """Call ready() with controlled argv and env, mocking heavy deps.

        Args:
            argv: sys.argv to simulate
            warmup: AUDIO_WARMUP env value ("0" or "1")
            tts_side_effect: Optional exception for warm_tts_service
            run_main: RUN_MAIN env value; "true" simulates autoreloader child
                      process, "" simulates parent or non-autoreloader
        """
        cfg = _get_cfg()
        mock_handler = MagicMock()
        mock_root = MagicMock()
        mock_root.handlers = []

        mock_tts = MagicMock()
        if tts_side_effect is not None:
            mock_tts.warm_tts_service.side_effect = tts_side_effect

        import mysite.universe.apps as apps_module

        env = {"AUDIO_WARMUP": warmup}
        if run_main:
            env["RUN_MAIN"] = run_main

        with patch.dict(os.environ, env, clear=False):
            # Clear RUN_MAIN if we're simulating a parent process
            if not run_main and "RUN_MAIN" in os.environ:
                del os.environ["RUN_MAIN"]
            with patch("sys.argv", argv):
                with patch(
                    "mysite.universe.services.log_buffer.get_log_handler",
                    return_value=mock_handler,
                ):
                    with patch("logging.getLogger", return_value=mock_root):
                        with patch.dict(
                            sys.modules,
                            {"mysite.universe.services.tts_service": mock_tts},
                        ):
                            with patch("threading.Thread") as mock_thread:
                                # Reset per-process guard so each test runs cleanly
                                apps_module._watchdog_started = False
                                cfg.ready()
        return mock_tts, mock_thread

    def test_ready_skips_warmup_for_migrate_command(self):
        """When sys.argv[1] is 'migrate', ready() returns before TTS warmup."""
        mock_tts, _ = self._call_ready(["manage.py", "migrate"], warmup="1")
        mock_tts.warm_tts_service.assert_not_called()

    def test_ready_skips_warmup_for_test_command(self):
        """When sys.argv[1] is 'test', ready() returns before TTS warmup."""
        mock_tts, _ = self._call_ready(["manage.py", "test"], warmup="1")
        mock_tts.warm_tts_service.assert_not_called()

    def test_ready_skips_watchdog_for_audio_worker_command(self):
        """When sys.argv[1] is 'audio_worker', ready() returns before spawning a worker."""
        _, mock_thread = self._call_ready(["manage.py", "audio_worker"], warmup="0")
        mock_thread.assert_not_called()

    def test_ready_calls_warm_tts_when_audio_warmup_set(self):
        """When AUDIO_WARMUP=1 and not a skip command, warm_tts_service() is called."""
        mock_tts, _ = self._call_ready(["manage.py", "runserver"], warmup="1")
        mock_tts.warm_tts_service.assert_called_once()

    def test_ready_swallows_warmup_exception(self):
        """An exception from warm_tts_service() is caught; ready() does not raise."""
        self._call_ready(
            ["manage.py", "runserver"],
            warmup="1",
            tts_side_effect=RuntimeError("no GPU"),
        )  # must not raise

    def test_ready_does_not_call_warmup_when_env_not_set(self):
        """When AUDIO_WARMUP is not '1', TTS warmup is skipped even for runserver."""
        mock_tts, _ = self._call_ready(["manage.py", "runserver"], warmup="0")
        mock_tts.warm_tts_service.assert_not_called()

    def test_ready_starts_watchdog_thread_for_runserver(self):
        """When running runserver, watchdog thread is started."""
        _, mock_thread = self._call_ready(["manage.py", "runserver"], warmup="0")
        mock_thread.assert_called_once()
        call_kwargs = mock_thread.call_args.kwargs
        self.assertEqual(call_kwargs.get("daemon"), True)
        self.assertEqual(call_kwargs.get("name"), "audio-worker-watchdog")

    def test_ready_watchdog_not_started_twice(self):
        """Calling ready() twice does not start a second watchdog thread."""
        import mysite.universe.apps as apps_module

        cfg = _get_cfg()
        mock_handler = MagicMock()
        mock_root = MagicMock()
        mock_root.handlers = []

        with patch.dict(os.environ, {"AUDIO_WARMUP": "0", "RUN_MAIN": "true"}):
            with patch("sys.argv", ["manage.py", "runserver"]):
                with patch(
                    "mysite.universe.services.log_buffer.get_log_handler",
                    return_value=mock_handler,
                ):
                    with patch("logging.getLogger", return_value=mock_root):
                        with patch("threading.Thread") as mock_thread:
                            apps_module._watchdog_started = False
                            cfg.ready()
                            cfg.ready()  # second call — should be a no-op
        # Thread should only have been constructed once
        self.assertEqual(mock_thread.call_count, 1)

    def test_ready_autoreloader_parent_skips_watchdog(self):
        """The autoreloader parent process (RUN_MAIN unset) does NOT start a watchdog.

        Fixes #32: two audio_workers would both load ~9 GB TTS model, exceeding
        the 12 GB VRAM on an RTX 3060.
        """
        _, mock_thread = self._call_ready(
            ["manage.py", "runserver"], warmup="0", run_main=""
        )
        mock_thread.assert_not_called()

    def test_ready_noreload_starts_watchdog_without_run_main(self):
        """With --noreload, there's no parent/child split; watchdog starts even without RUN_MAIN."""
        _, mock_thread = self._call_ready(
            ["manage.py", "runserver", "--noreload"], warmup="0", run_main=""
        )
        mock_thread.assert_called_once()
