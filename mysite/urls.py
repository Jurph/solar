from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .universe import views

urlpatterns = [
    # The administrator page for adding elements 
    path('admin/', admin.site.urls),
    # The "Universe Browser"
    path('universe/', views.universe_view, name='universe'),
    # API endpoint for object details (baseball card)
    path('api/universe/<str:object_type>/<int:object_id>/', views.object_details, name='object_details'),
    # The event scroller wrapper with control panel (main page):
    path("events/", views.event_scroller_wrapper, name="event_scroller_wrapper"),
    # The event scroller page (iframe content):
    path("events/scroller/", views.event_scroller, name="event_scroller"),
    # The JSON API endpoint for polling events:
    path("api/events/", views.event_feed, name="event_feed"),
    # API endpoint to run the dialogue demo (deprecated - use spawn_mission):
    path("api/run-demo/", views.run_demo, name="run_demo"),
    # API endpoint to spawn a complete mission (ship + cargo + journey):
    path("api/spawn-mission/", views.spawn_mission, name="spawn_mission"),
    # API endpoint to clear display events:
    path("api/clear-events/", views.clear_events, name="clear_events"),
    # API endpoint to clear all events from DB (fresh start):
    path("api/clear-all-events/", views.clear_all_events, name="clear_all_events"),
    # API endpoint to set simulation time scale:
    path("api/simulation/time-scale/", views.set_time_scale, name="set_time_scale"),
    # API endpoint to get simulation status:
    path("api/simulation/status/", views.get_simulation_status, name="simulation_status"),
    # API endpoint to skip to next event:
    path("api/simulation/skip-to-next/", views.skip_to_next_event, name="skip_to_next_event"),
    # API endpoint to fetch generated event audio (synchronous on-demand)
    path("api/event_audio/<int:event_id>/", views.event_audio, name="event_audio"),
    # Diagnostics: tail recent logs and adjust log level
    path("api/logs/", views.logs_view, name="logs_view"),
    # API endpoint for audio clip presets (WAV):
    path("api/audio/preset/<str:preset>/", views.audio_preset, name="audio_preset"),
    # Dev tool: Audio lab (standalone UI + render endpoint)
    path("audio-lab/", views.audio_lab, name="audio_lab"),
    path("api/audio/lab/render/", views.audio_lab_render, name="audio_lab_render"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

