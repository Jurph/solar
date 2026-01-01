"""
Views package for the universe app.

This package is organized by domain:
- universe.py: Universe browser and celestial object details
- events.py: Event feed, display, and management
- simulation.py: Simulation time control and status
- missions.py: Mission spawning and orchestration
- audio.py: Future audio/TTS rendering (placeholder)
- serializers.py: Type-specific object serializers for API responses
"""

# Universe browser and object details
from mysite.universe.views.universe import (
    universe_view,
    object_details,
)

# Event feed, display, and management
from mysite.universe.views.events import (
    event_feed,
    event_scroller,
    event_scroller_wrapper,
    clear_events,
    event_audio,
)

# Simulation time control
from mysite.universe.views.simulation import (
    set_time_scale,
    skip_to_next_event,
    get_simulation_status,
    health_check,
)

# Mission spawning
from mysite.universe.views.missions import (
    spawn_mission,
    run_demo,
)

# Audio
from mysite.universe.views.audio import (
    audio_preset,
    audio_lab,
    audio_lab_render,
)
from mysite.universe.views.logs import logs_view

# Backwards compatibility alias for consolidated clear function
# (clear_all_events was identical to clear_events)
clear_all_events = clear_events

__all__ = [
    # Universe
    'universe_view',
    'object_details',
    # Events
    'event_feed',
    'event_scroller',
    'event_scroller_wrapper',
    'clear_events',
    'event_audio',
    'clear_all_events',  # Alias for backwards compatibility
    # Simulation
    'set_time_scale',
    'skip_to_next_event',
    'get_simulation_status',
    'health_check',
    # Missions
    'spawn_mission',
    'run_demo',
    # Audio
    'audio_preset',
    'audio_lab',
    'audio_lab_render',
    'logs_view',
]
