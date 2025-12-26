"""
Mission-oriented helpers for route generation.

Right now we only have cargo-style missions exposed in the UI, but as mission scope expands we
expect specialized destination pickers (e.g., populated/mining/science). This module is a first,
minimal step toward a future MissionService without inventing new mission types today.
"""

import random
from typing import List

from mysite.universe.models.base import Location
from mysite.universe.models.navigation import ManeuverType, NavigationEvent, UniverseGraph
from mysite.universe.models.scale import OrderedScale, Scale


def pick_random_destination(
    service,
    *,
    excluding: Location,
    max_scale: Scale = None,
    cargo_mission: bool = False,
) -> Location:
    """
    Picks a random destination from all Location objects (excluding the one provided),
    optionally filtering for those with scale <= max_scale.
    """
    if cargo_mission:
        # Use the Ship model's method to get valid cargo locations
        from mysite.universe.models.ship import Ship

        all_locations = Ship.get_valid_cargo_locations()
        eligible = [loc for loc in all_locations if loc.id != excluding.id]
    else:
        all_locations = list(Location.objects.exclude(id=excluding.id))
        eligible = [loc for loc in all_locations if not max_scale or loc.scale <= max_scale]

    if not eligible:
        raise ValueError("No available destination in the universe matching criteria.")
    return random.choice(eligible)


def random_journey(service, ship, cargo_mission: bool = True) -> List[NavigationEvent]:
    """
    Plans a random journey for a given ship.

    This method:
      - Assigns a random origin to the ship if its current_location is None or invalid.
      - Chooses a random destination different from the origin.
      - Builds and returns a sequence of NavigationEvent objects for the journey.
    """
    from mysite.universe.models.ship import Ship

    if not ship.current_location:
        origin = Ship.get_random_cargo_origin() if cargo_mission else random.choice(
            [loc for loc in Location.objects.all() if loc.scale <= Scale.PLANET]
        )
        ship.current_location = origin
        ship.save()
    else:
        origin = ship.current_location

    destination = pick_random_destination(service, excluding=origin, cargo_mission=cargo_mission)
    universe = UniverseGraph.get_instance()
    path = universe.get_path(origin, destination)

    # Use plan_route to generate the full route with controller information
    events = service.plan_route(origin, destination)

    # Ensure all events have a controller assigned
    for i, event in enumerate(events):
        if event.controller is None:
            if event.maneuver in [ManeuverType.LAUNCH, ManeuverType.UNDOCK, ManeuverType.SUBLIGHT, ManeuverType.HYPERSPACE]:
                current_idx = path.index(event.destination) if event.destination in path else 0
                departure_loc = path[max(0, current_idx - 1)]
                events[i] = NavigationEvent(
                    maneuver=event.maneuver,
                    origin=departure_loc,
                    current=departure_loc,
                    next=event.next,
                    destination=event.destination,
                    description=event.description,
                    controller=service.effective_controller(departure_loc),
                )
            else:
                events[i] = NavigationEvent(
                    maneuver=event.maneuver,
                    origin=event.origin,
                    current=event.current,
                    next=event.next,
                    destination=event.destination,
                    description=event.description,
                    controller=service.effective_controller(event.destination),
                )
    return events


def get_local_locations(service, current: Location, max_scale: Scale) -> List[Location]:
    """
    Returns all Location objects reachable from 'current' whose scale is <= max_scale.

    This helper leverages the UniverseGraph's local_graph method.
    """
    universe = UniverseGraph.get_instance()
    return universe.get_local_graph(current, OrderedScale(max_scale))


