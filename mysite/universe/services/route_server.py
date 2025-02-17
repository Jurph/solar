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
        Uses the universe graph's get_path for a clean abstraction.
        """
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        events = self.build_navigation_events(path)
        
        # Propagate effective controller information
        current_station: Optional[Station] = self.effective_controller(origin)
        for event in events:
            if current_station is None:
                raise ValueError(f"No effective station found for {event.target.name}.")
            candidate = self.effective_controller(event.target)
            if candidate is not None:
                current_station = candidate
        return events

    def build_navigation_events(self, path: List) -> List:
        """
        A placeholder for building navigation events based on the path.
        In actual implementation, this relies on world-building logic.
        """
        # Transform the path into NavigationEvent instances.
        # (This logic is assumed to be implemented elsewhere.)
        return []

    def effective_controller(self, location: Location):
        """
        Determine the controlling station for a given location.
        Existing implementation logic.
        """
        # This function could be enhanced to use our get_nearest_node_of_type if needed.
        # For now, assume it returns a Station instance or None.
        from ..models.station import Station
        stations = Station.objects.filter(orbits=location)
        return stations.first() if stations.exists() else None

    def pick_random_destination(self, excluding: Location) -> Location:
        """
        Picks a random destination from all available locations,
        excluding the given origin.
        """
        # As an alternative to arbitrary random selection, one might consider
        # selecting the nearest destination of a certain type by using:
        #   universe.get_nearest_node_of_type(origin, "Planet")
        # Here we preserve the original behavior.
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