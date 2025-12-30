from django.apps import AppConfig


class UniverseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mysite.universe'  # This should be the full path
    
    def ready(self):
        """Import signal receivers when the app is ready."""
        import mysite.universe.receivers  # noqa: F401
        # Warm up TTS and start the audio worker (best-effort) — gated to avoid
        # slowing management commands like makemigrations/collectstatic.
        import os
        import sys
        import logging
        from mysite.universe.services.log_buffer import get_log_handler

        # Attach in-memory log handler for live diagnostics (always).
        handler = get_log_handler()
        root = logging.getLogger()
        if handler not in root.handlers:
            root.addHandler(handler)
        root.setLevel(logging.INFO)

        # Skip heavy warmup during management commands.
        skip_cmds = {"makemigrations", "migrate", "collectstatic", "test", "shell"}
        if len(sys.argv) >= 2 and sys.argv[1] in skip_cmds:
            return

        # Ensure worker always; warmup is opt-in.
        try:
            from mysite.universe.views import events as events_views
            events_views._ensure_worker()
        except Exception:
            pass

        if os.getenv("AUDIO_WARMUP", "0") == "1":
            try:
                from mysite.universe.services.tts_service import warm_tts_service
                warm_tts_service()
            except Exception:
                pass