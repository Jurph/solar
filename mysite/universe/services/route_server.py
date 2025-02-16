from typing import List, Optional
from ..models.navigation import UniverseGraph, NavigationStep, ManeuverType, effective_contact_station, plan_navigation_steps
from ..models.base import Location
import random

class RouteService:
    """Service for planning routes using the universe graph"""
    
    def plan_route(self, origin: Location, destination: Location) -> List[NavigationStep]:
        """Generate navigation steps between two points using the domain logic."""
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)

        # Domain helper that computes steps based on effective contact stations.
        steps = plan_navigation_steps(path)

        # Fallback: if any step does not have a contact station, fall back to the previous known station.
        current_station: Optional[Station] = effective_contact_station(origin)
        for step in steps:
            if step.contact_station is None:
                if current_station is None:
                    raise ValueError(
                        f"Error: No effective station found for {step.target.name}."
                    )
                step.contact_station = current_station
            else:
                current_station = step.contact_station

        return steps

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

    def random_journey(self, ship) -> List[NavigationStep]:
        """
        Plans a random journey for the given ship.
        For each leg of the journey, ensure that the effective contact station
        is carried forward until a new station is available.
        """
        origin = ship.current_location
        destination = self.pick_random_destination(excluding=origin)
        print(f"Random journey: {origin.name} -> {destination.name}")

        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        steps = plan_navigation_steps(path)

        # Propagate the effective station down the journey.
        current_station = effective_contact_station(origin)
        for step in steps:
            if step.contact_station is None:
                if current_station is None:
                    raise ValueError(
                        f"No effective station found for leg towards {step.target.name}"
                    )
                # Fall back to the previous station if this leg lacks one.
                step.contact_station = current_station
            else:
                current_station = step.contact_station

        return steps