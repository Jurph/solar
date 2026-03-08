"""
Tests for UniverseConfig.ready() in apps.py.

Covers:
- skip_cmds early return (line 28)
- AUDIO_WARMUP=1 path: warm_tts_service called (lines 32-34)
- AUDIO_WARMUP=1 path: exception swallowed (lines 35-36)
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

    def _call_ready(self, argv, warmup="0", tts_side_effect=None):
        """Call ready() with controlled argv and AUDIO_WARMUP env, mocking heavy deps."""
        cfg = _get_cfg()
        mock_handler = MagicMock()
        mock_root = MagicMock()
        mock_root.handlers = []

        mock_tts = MagicMock()
        if tts_side_effect is not None:
            mock_tts.warm_tts_service.side_effect = tts_side_effect

        with patch.dict(os.environ, {"AUDIO_WARMUP": warmup}):
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
                            cfg.ready()
        return mock_tts

    def test_ready_skips_warmup_for_migrate_command(self):
        """When sys.argv[1] is 'migrate', ready() returns before TTS warmup."""
        mock_tts = self._call_ready(["manage.py", "migrate"], warmup="1")
        mock_tts.warm_tts_service.assert_not_called()

    def test_ready_skips_warmup_for_test_command(self):
        """When sys.argv[1] is 'test', ready() returns before TTS warmup."""
        mock_tts = self._call_ready(["manage.py", "test"], warmup="1")
        mock_tts.warm_tts_service.assert_not_called()

    def test_ready_calls_warm_tts_when_audio_warmup_set(self):
        """When AUDIO_WARMUP=1 and not a skip command, warm_tts_service() is called."""
        mock_tts = self._call_ready(["manage.py", "runserver"], warmup="1")
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
        mock_tts = self._call_ready(["manage.py", "runserver"], warmup="0")
        mock_tts.warm_tts_service.assert_not_called()
