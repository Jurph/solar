"""
Internal helpers for `mysite.universe.services.route_server.RouteService`.

This package exists to keep `route_server.py` (the public service façade) small and readable,
while preserving its public API.

Design intent:
- Keep the public `RouteService` class and method signatures stable.
- Move implementation details into focused modules:
  - plan.py: path/scale/transfer/maneuver synthesis (core route planning)
  - controllers.py: controller assignment (service-layer adapter over world-model logic)
  - durations.py: physics-based maneuver durations (part of route planning correctness)
  - missions.py: mission-oriented helpers (currently cargo-only; will expand later)
  - formatting.py: pretty-printing for debug/diagnostics
"""


