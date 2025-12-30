from django.apps import AppConfig


class UniverseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mysite.universe'  # This should be the full path
    
    def ready(self):
        """Import signal receivers when the app is ready."""
        import mysite.universe.receivers  # noqa: F401
        # Warm up TTS and start the audio worker (best-effort).
        try:
            from mysite.universe.views import events as events_views
            from mysite.universe.services.tts_service import warm_tts_service

            events_views._ensure_worker()
            warm_tts_service()
        except Exception:
            # Best-effort only; do not break startup.
            pass