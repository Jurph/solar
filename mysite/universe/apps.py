import os
import sys
import logging
import subprocess
import threading
import time

from django.apps import AppConfig

logger = logging.getLogger(__name__)

# Module-level flag so the watchdog is only started once per process,
# regardless of how many times Django calls ready() (e.g. during tests).
_watchdog_started = False


def _audio_worker_watchdog(manage_py: str) -> None:
    """
    Daemon thread that keeps the audio worker process alive.

    Worker stdout is suppressed (verbose progress output); stderr is
    forwarded to the Django logger so failures are visible without
    dumping raw tracebacks to the user's terminal.

    Restarts on crash with exponential back-off when it fails fast
    (TTS unavailable, GPU error, warmup failure, etc.).
    """
    consecutive_fast_exits = 0
    while True:
        started_at = time.monotonic()
        proc = None
        try:
            proc = subprocess.Popen(
                [sys.executable, manage_py, "audio_worker"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,  # capture so we can log, not dump raw
                env={**os.environ},  # explicit copy ensures PYTHONPATH is inherited
            )
            logger.info("Audio worker started (pid %d)", proc.pid)

            # Forward worker stderr to Django logger on a background thread
            # so proc.wait() below doesn't deadlock.
            def _drain_stderr(pipe: object) -> None:
                for raw in iter(pipe.readline, b""):
                    line = raw.decode(errors="replace").rstrip()
                    if line:
                        logger.warning("[audio_worker] %s", line)
                pipe.close()

            drain = threading.Thread(
                target=_drain_stderr, args=(proc.stderr,), daemon=True
            )
            drain.start()

            proc.wait()
            drain.join(timeout=5)
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
            time.sleep(5)


class UniverseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mysite.universe"

    def ready(self) -> None:
        """Import signal receivers and start background services."""
        global _watchdog_started

        import mysite.universe.receivers  # noqa: F401

        from mysite.universe.services.log_buffer import get_log_handler

        # Attach in-memory log handler for live diagnostics (always).
        handler = get_log_handler()
        root = logging.getLogger()
        if handler not in root.handlers:
            root.addHandler(handler)
        root.setLevel(logging.INFO)

        # Skip heavy startup work for management commands that don't need it.
        # audio_worker is excluded so it never spawns itself recursively.
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

        # Guard: only start the watchdog once, and only in the right process.
        # Django's autoreloader runs ready() in two processes — the parent
        # (file watcher) and the child (actual server).  Starting a watchdog
        # in both spawns two audio_workers, each loading ~9 GB of TTS model
        # into VRAM, which exceeds the 12 GB on an RTX 3060.
        # RUN_MAIN is set by Django's autoreloader in the child process.
        # When --noreload is used, RUN_MAIN is never set, so we still start.
        is_autoreload_parent = (
            os.environ.get("RUN_MAIN") != "true" and "--noreload" not in sys.argv
        )
        if _watchdog_started or is_autoreload_parent:
            return
        _watchdog_started = True

        # Optional TTS warmup (loads model into GPU on startup)
        if os.getenv("AUDIO_WARMUP", "0") == "1":
            try:
                from mysite.universe.services.tts_service import warm_tts_service

                warm_tts_service()
            except Exception:
                pass

        manage_py = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manage.py")
        )
        t = threading.Thread(
            target=_audio_worker_watchdog,
            args=(manage_py,),
            daemon=True,
            name="audio-worker-watchdog",
        )
        t.start()
        logger.info("Audio worker watchdog started (manage_py=%s)", manage_py)
