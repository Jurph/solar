from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from mysite.universe.views.audio import audio_lab, audio_lab_render, audio_preset
from mysite.universe.views.events import (
    clear_events,
    event_audio,
    event_feed,
    event_scroller,
    event_scroller_wrapper,
)
from mysite.universe.views.logs import logs_view
from mysite.universe.views.missions import run_demo, spawn_mission
from mysite.universe.views.simulation import (
    get_simulation_status,
    health_check,
    set_time_scale,
    skip_to_next_event,
    worker_health_check,
)
from mysite.universe.views.universe import object_details, universe_view

clear_all_events = clear_events

urlpatterns = (
    [
        # The administrator page for adding elements
        path("admin/", admin.site.urls),
        # The "Universe Browser"
        path("universe/", universe_view, name="universe"),
        # API endpoint for object details (baseball card)
        path(
            "api/universe/<str:object_type>/<int:object_id>/",
            object_details,
            name="object_details",
        ),
        # The event scroller wrapper with control panel (main page):
        path("events/", event_scroller_wrapper, name="event_scroller_wrapper"),
        # The event scroller page (iframe content):
        path("events/scroller/", event_scroller, name="event_scroller"),
        # The JSON API endpoint for polling events:
        path("api/events/", event_feed, name="event_feed"),
        # Dev-only endpoint to run the dialogue demo (guarded by ALLOW_STATE_CHANGING_DEV_ENDPOINTS):
        path("api/run-demo/", run_demo, name="run_demo"),
        # Dev-only endpoint to spawn a complete mission (guarded by ALLOW_STATE_CHANGING_DEV_ENDPOINTS):
        path("api/spawn-mission/", spawn_mission, name="spawn_mission"),
        # Dev-only endpoint to clear display events (guarded by ALLOW_STATE_CHANGING_DEV_ENDPOINTS):
        path("api/clear-events/", clear_events, name="clear_events"),
        # API endpoint to clear all events from DB (fresh start):
        path("api/clear-all-events/", clear_all_events, name="clear_all_events"),
        # Dev-only endpoint to set simulation time scale (guarded by ALLOW_STATE_CHANGING_DEV_ENDPOINTS):
        path("api/simulation/time-scale/", set_time_scale, name="set_time_scale"),
        # API endpoint to get simulation status:
        path("api/simulation/status/", get_simulation_status, name="simulation_status"),
        # Dev-only endpoint to skip to next event (guarded by ALLOW_STATE_CHANGING_DEV_ENDPOINTS):
        path(
            "api/simulation/skip-to-next/",
            skip_to_next_event,
            name="skip_to_next_event",
        ),
        # API endpoint for service health checks:
        path("api/simulation/health/", health_check, name="health_check"),
        # Dedicated audio worker health check; returns 503 when audio generation is stalled:
        path("api/worker/health/", worker_health_check, name="worker_health_check"),
        # API endpoint to fetch generated event audio (synchronous on-demand)
        path("api/event_audio/<int:event_id>/", event_audio, name="event_audio"),
        # Diagnostics: tail recent logs and adjust log level
        path("api/logs/", logs_view, name="logs_view"),
        # API endpoint for audio clip presets (WAV):
        path("api/audio/preset/<str:preset>/", audio_preset, name="audio_preset"),
        # Dev tool: Audio lab (standalone UI + render endpoint; render is dev-only guarded)
        path("audio-lab/", audio_lab, name="audio_lab"),
        path("api/audio/lab/render/", audio_lab_render, name="audio_lab_render"),
    ]
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
)
