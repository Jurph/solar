"""
Views package for the universe app.
"""
from mysite.universe.views.events import (
    clear_events,
    clear_all_events,
    event_feed,
    event_scroller,
    event_scroller_wrapper,
    get_simulation_status,
    run_demo,
    set_time_scale,
    spawn_mission,
    universe_view,
    object_details,
)

__all__ = [
    'clear_events',
    'clear_all_events',
    'event_feed',
    'event_scroller',
    'event_scroller_wrapper',
    'get_simulation_status',
    'run_demo',
    'set_time_scale',
    'spawn_mission',
    'universe_view',
    'object_details',
]

