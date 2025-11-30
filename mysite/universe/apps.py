from django.apps import AppConfig


class UniverseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mysite.universe'  # This should be the full path
    
    def ready(self):
        """Import signal receivers when the app is ready."""
        import mysite.universe.receivers  # noqa: F401