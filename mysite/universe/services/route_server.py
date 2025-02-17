from typing import List, Optional
from ..models.navigation import UniverseGraph, build_navigation_events, effective_controller
from ..models.base import Location
from ..models.event import Event  # If needed elsewhere.
from ..models.station import Station
import random

class RouteService:
    """Service for planning routes using the universe graph"""
    
    def plan_route(self, origin: Location, destination: Location) -> List:
        """
        Generate navigation events between two points using the domain logic.
        This now uses build_navigation_events, which implements the full world-building logic.
        """
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        # Use the richer, world-building-aware function:
        events = build_navigation_events(path)

        # Optionally, if needed, attach or adjust controlling station information here.
        # For each event, you might want to check and propagate effective controllers.
        current_station: Optional[Station] = effective_controller(origin)
        for event in events:
            # In case your NavigationEvent doesn't include a contact station,
            # you could create a NavigationStep object from event info if required
            if current_station is None:
                raise ValueError(f"No effective station found for {event.target.name}.")
            # Optionally update current_station based on the event target:
            candidate = effective_controller(event.target)
            if candidate is not None:
                current_station = candidate

        return events

    def pick_random_destination(self, excluding: Location) -> Location:
        """
        Picks a random destination from all available locations,
        excluding the given origin.
        """
        from mysite.universe.models.base import Location  # or use specific subclass queries
        all_ids = list(Location.objects.exclude(id=excluding.id).values_list("id", flat=True))
        if not all_ids:
            raise ValueError("No available destination in the universe.")
        random_id = random.choice(all_ids)
        return Location.objects.get(id=random_id)

    def random_journey(self, ship) -> List:
        """
        Plans a random journey for the ship using build_navigation_events.
        """
        origin = ship.current_location
        destination = self.pick_random_destination(excluding=origin)
        print(f"Random journey: {origin.name} -> {destination.name}")
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        # Now using the new, richer event builder:
        events = build_navigation_events(path)

        current_station = effective_controller(origin)
        for event in events:
            if current_station is None:
                raise ValueError(f"No effective station found for leg towards {event.target.name}")
            candidate = effective_controller(event.target)
            if candidate is not None:
                current_station = candidate
        return events