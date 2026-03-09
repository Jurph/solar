import os
import sys
import logging
import subprocess
import threading
import time

from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _audio_worker_watchdog(manage_py: str) -> None:
    """
    Daemon thread that keeps the audio worker process alive.

    Restarts the worker on crash with exponential back-off when it fails
    fast (TTS unavailable, warmup error, etc.).  A clean exit (code 0) or
    a very fast exit is treated as a transient failure and retried.
    """
    consecutive_fast_exits = 0
    while True:
        started_at = time.monotonic()
        try:
            proc = subprocess.Popen(
                [sys.executable, manage_py, "audio_worker"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Audio worker started (pid %d)", proc.pid)
            proc.wait()
            elapsed = time.monotonic() - started_at
            logger.warning(
                "Audio worker exited (code=%s, uptime=%.0fs)",
                proc.returncode,
                elapsed,
            )
        except Exception as exc:
            logger.error("Audio worker watchdog error: %s", exc)
            elapsed = time.monotonic() - started_at

        if elapsed < 30:
            # Fast exit — TTS init failure, GPU not available, warmup error, etc.
            consecutive_fast_exits += 1
            backoff = min(300, 30 * consecutive_fast_exits)
            logger.warning(
                "Audio worker fast-exited %d time(s); retrying in %ds",
                consecutive_fast_exits,
                backoff,
            )
            time.sleep(backoff)
        else:
            consecutive_fast_exits = 0
            time.sleep(5)  # Brief pause before normal restart


class UniverseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mysite.universe"

    def ready(self) -> None:
        """Import signal receivers and start background services."""
        import mysite.universe.receivers  # noqa: F401

        from mysite.universe.services.log_buffer import get_log_handler

        # Attach in-memory log handler for live diagnostics (always).
        handler = get_log_handler()
        root = logging.getLogger()
        if handler not in root.handlers:
            root.addHandler(handler)
        root.setLevel(logging.INFO)

        # Skip heavy startup work for management commands that don't need it.
        # Also skip for audio_worker itself to avoid recursive spawning.
        skip_cmds = {
            "makemigrations",
            "migrate",
            "collectstatic",
            "test",
            "shell",
            "audio_worker",
        }
        if len(sys.argv) >= 2 and sys.argv[1] in skip_cmds:
            return

        # Django's autoreloader forks two processes; only run in the child
        # (RUN_MAIN=true) to avoid spawning duplicate audio workers.
        if (
            os.environ.get("RUN_MAIN") != "true"
            and os.environ.get("DJANGO_AUTORELOAD") != "0"
        ):
            # Parent watcher process — skip worker spawn, it will happen in child
            return

        # Optional TTS warmup (loads model into GPU on startup)
        if os.getenv("AUDIO_WARMUP", "0") == "1":
            try:
                from mysite.universe.services.tts_service import warm_tts_service

                warm_tts_service()
            except Exception:
                pass

        # Start the audio worker watchdog in a daemon thread so it lives and
        # dies with this Django process.
        manage_py = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "manage.py"
        )
        manage_py = os.path.normpath(manage_py)
        t = threading.Thread(
            target=_audio_worker_watchdog,
            args=(manage_py,),
            daemon=True,
            name="audio-worker-watchdog",
        )
        t.start()
        logger.info("Audio worker watchdog started (manage_py=%s)", manage_py)
