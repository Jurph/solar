"""
High-level routing services to plan journeys and determine maneuvers for ships.

This module builds on the low-level navigation capabilities provided by the
UniverseGraph class. It applies domain‐specific rules (using ship status, scales, and
local controllers) to decide which maneuvers to apply (e.g. TRANSFER vs HYPERSPACE) and
to synthesize navigation events from the low-level graph path.
"""

from typing import List, Optional
from ..models.base import Location
from ..models.scale import Scale
from ..models.station import Station
from ..models.navigation import ManeuverType, UniverseGraph
from dataclasses import dataclass
import random

@dataclass(frozen=True)
class NavigationEvent:
    """
    A NavigationEvent represents a single maneuver step in a navigation plan.
    
    Attributes:
        maneuver: The type of maneuver (e.g., TRANSFER, LAUNCH, LANDING).
        target: The destination Location object for this maneuver.
        description: A human-readable description of the maneuver.
    """
    maneuver: ManeuverType
    target: Location
    description: str = ""

class RouteService:
    """Service for planning routes and maneuvers within the universe."""

    def plan_route(self, origin: Location, destination: Location) -> List[NavigationEvent]:
        """
        Generates a series of NavigationEvent objects for a journey from origin to destination.
        This method leverages the UniverseGraph to obtain a path and then applies business rules
        to convert that path into domain-relevant maneuvers.
        """
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        # As an initial approach, build events for each adjacent pair.
        events: List[NavigationEvent] = []
        for i in range(len(path) - 1):
            # For the final leg, mark final=True so that landing/docking events are produced.
            final = (i == len(path) - 2)
            segment_events = self.generate_segment_events(path[i], path[i + 1], final=final)
            events.extend(segment_events)
        # Propagate effective controller information along the journey.
        current_station: Optional[Station] = self.effective_controller(origin)
        for event in events:
            if current_station is None:
                raise ValueError(f"No effective controller found for leg toward {event.target.name}")
            candidate = self.effective_controller(event.target)
            if candidate is not None:
                current_station = candidate
        return events

    def build_navigation_events(self, path: List[Location]) -> List[NavigationEvent]:
        """
        [Legacy helper]
        Transforms a path (a list of Locations) into a series of basic navigation events.
        This method is retained for simpler maneuvers.
        """
        events = []
        if not path:
            return events

        for i in range(len(path) - 1):
            current, nxt = path[i], path[i + 1]
            if current.scale < nxt.scale:
                maneuver = "HYPERSPACE"
                description = f"Hyperspace jump from {current.name} to {nxt.name}"
            else:
                maneuver = "TRANSFER"
                description = f"Standard transfer from {current.name} to {nxt.name}"
            events.append(NavigationEvent(maneuver=maneuver, target=nxt, description=description))

        destination = path[-1]
        if destination.get_type_name() == "Station":
            events.append(NavigationEvent(maneuver="DOCK", target=destination,
                                        description=f"Dock at {destination.name}"))
        else:
            events.append(NavigationEvent(maneuver="LAND", target=destination,
                                        description=f"Land on {destination.name}"))
        return events

    def effective_controller(self, location: Location) -> Optional[Station]:
        """
        Determines the controlling Station for a given Location.

        Uses the UniverseGraph's find_nearest_node to look for the nearest Station (within the
        local graph bounded by location.scale) whose name contains "control" or "dispatch."
        """
        universe = UniverseGraph.get_instance()
        controller = universe.find_nearest_node(
            start=location,
            condition=lambda node: node.get_type_name() == "Station"
            and ("control" in node.name.lower() or "dispatch" in node.name.lower()),
            max_scale=location.scale,
        )
        return controller

    def pick_random_destination(self, excluding: Location, max_scale: Scale = None) -> Location:
        """
        Picks a random destination from all Location objects (excluding the one provided),
        optionally filtering for those with scale <= max_scale.
        """
        all_locations = list(Location.objects.exclude(id=excluding.id))
        eligible = [loc for loc in all_locations if not max_scale or loc.scale <= max_scale]
        if not eligible:
            raise ValueError("No available destination in the universe matching criteria.")
        return random.choice(eligible)

    def random_journey(self, ship) -> List[NavigationEvent]:
        """
        Plans a random journey for a given ship.
        
        This method:
            - Assigns a random origin to the ship if its current_location is None or is above Planet scale.
            - Chooses a random destination (with scale at or below Planet) different from the origin.
            - Builds and returns a sequence of NavigationEvent objects for the journey.
        """
        # If the ship doesn't have a current location or the location is too large, assign a random origin.
        if not ship.current_location or ship.current_location.scale > Scale.PLANET:
            eligible_origins = [loc for loc in Location.objects.all() if loc.scale <= Scale.PLANET]
            if not eligible_origins:
                raise ValueError("No eligible origin locations (scale <= Planet) found in the universe.")
            origin = random.choice(eligible_origins)
            ship.current_location = origin
            # Assuming ship is a Django model:
            ship.save()
        else:
            origin = ship.current_location

        # Pick a random destination with scale <= Planet, excluding the origin.
        destination = self.pick_random_destination(excluding=origin, max_scale=Scale.PLANET)
        print(f"Random journey: {origin.name} -> {destination.name}")
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        # Use our new segment generator for the full path.
        events: List[NavigationEvent] = []
        for i in range(len(path) - 1):
            final = (i == len(path) - 2)
            events.extend(self.generate_segment_events(path[i], path[i + 1], final=final))
        current_station = self.effective_controller(origin)
        for event in events:
            if current_station is None:
                raise ValueError(f"No effective controller found for leg toward {event.target.name}")
            candidate = self.effective_controller(event.target)
            if candidate is not None:
                current_station = candidate
        return events

    def get_local_locations(self, current: Location, max_scale: Scale) -> List[Location]:
        """
        Returns all Location objects reachable from 'current' whose scale is less than or equal
        to 'max_scale'. This helper leverages the UniverseGraph's local_graph method.

        For instance, calling get_local_locations(current, Scale.PLANET) returns all local nodes
        (e.g., nearby Stations, Moons, or Planets) that do not exceed the Planet scale. In a binary
        star system, if reaching a neighbor requires traversing a node with a scale above the specified
        max_scale, that neighbor is omitted.
        """
        universe = UniverseGraph.get_instance()
        return universe.local_graph(current, max_scale)

    def generate_segment_events(
        self, start: Location, end: Location, final: bool = False
    ) -> List[NavigationEvent]:
        """
        Generates a list of NavigationEvent objects that transition from the 'start' location to the 'end'
        location. This helper embodies the following rules:

        1. Departure:
            - If at a Station: UNDOCK, then TRANSFER burn, then CIRCULARIZE.
            - If at a Planet or Moon: LAUNCH, then INSERTION burn, then CIRCULARIZE.
            (TODO: Handle the case where the origin exceeds Planet scale.)
        
        2. Transit:
            - From a Moon: perform a short TRANSFER burn.
            - From a Planet to a Moon: include a PLANE CHANGE maneuver, then a short TRANSFER burn.
            - From a Planet to another Planet: execute a standard TRANSFER burn.
            - (If departing from a Station, the initial transfer is already provided.)
        
        3. Arrival:
            - For intermediate stops (final=False) at a Planet or Moon: perform an INSERTION burn followed by CIRCULARIZATION
                to capture orbit.
            - For final segments (final=True):
             * At a Planet or Moon: execute a DEORBIT burn followed by LANDING.
             * At a Station: perform a DOCK maneuver.
        
        Returns:
            List[NavigationEvent]: A list of events for the segment.
        """
        events: List[NavigationEvent] = []

        # Departure sequence
        if start.scale == Scale.STATION:
            events.extend([
                NavigationEvent(maneuver="UNDOCK", target=start,
                                description=f"Undock from station {start.name}"),
                NavigationEvent(maneuver="TRANSFER", target=start,
                                description=f"Initial transfer burn from station {start.name}"),
                NavigationEvent(maneuver="CIRCULARIZE", target=start,
                                description=f"Circularize after undocking at {start.name}")
            ])
        elif start.scale in {Scale.PLANET, Scale.MOON}:
            events.extend([
                NavigationEvent(maneuver="LAUNCH", target=start,
                                description=f"Launch from {start.name}"),
                NavigationEvent(maneuver="INSERTION", target=start,
                                description=f"Insertion burn to exit {start.name}'s gravity well"),
                NavigationEvent(maneuver="CIRCULARIZE", target=start,
                                description=f"Circularize orbit after launch from {start.name}")
            ])
        else:
            events.append(
                NavigationEvent(maneuver="UNKNOWN_DEPARTURE", target=start,
                                description=f"Departure procedure for scale {start.scale} not defined")
            )

        # Transit maneuvers based on origin and destination types
        if start.scale == Scale.MOON:
            events.append(
                NavigationEvent(maneuver="TRANSFER", target=end,
                                description=f"Short sublight transfer burn from moon {start.name}")
            )
        elif start.scale == Scale.PLANET and end.scale == Scale.MOON:
            events.extend([
                NavigationEvent(maneuver="PLANE_CHANGE", target=end,
                                description=f"Plane change maneuver from planet {start.name} for transfer to moon {end.name}"),
                NavigationEvent(maneuver="TRANSFER", target=end,
                                description=f"Short sublight transfer burn from {start.name} to {end.name}")
            ])
        elif start.scale == Scale.PLANET and end.scale == Scale.PLANET:
            events.append(
                NavigationEvent(maneuver="TRANSFER", target=end,
                                description=f"Sublight transfer burn from planet {start.name} to planet {end.name}")
            )
        elif start.scale == Scale.STATION and end.scale != Scale.STATION:
            # No additional transit event needed if departing from a station.
            pass

        # Arrival sequence: differentiate between intermediate and final segments.
        if final:
            if end.scale in {Scale.PLANET, Scale.MOON}:
                events.extend([
                    NavigationEvent(maneuver="DEORBIT", target=end,
                                    description=f"Deorbit burn to approach {end.name}"),
                    NavigationEvent(maneuver="LANDING", target=end,
                                    description=f"Landing procedure at {end.name}")
                ])
            elif end.scale == Scale.STATION:
                events.append(
                    NavigationEvent(maneuver="DOCK", target=end,
                                    description=f"Docking procedure at station {end.name}")
                )
        else:
            if end.scale in {Scale.PLANET, Scale.MOON}:
                events.extend([
                    NavigationEvent(maneuver="INSERTION", target=end,
                                    description=f"Insertion burn to get captured by {end.name}'s gravity well"),
                    NavigationEvent(maneuver="CIRCULARIZE", target=end,
                                    description=f"Orbit circularization at {end.name}")
                ])
            elif end.scale == Scale.STATION:
                # Intermediate docking (rare, but possible)
                events.append(
                    NavigationEvent(maneuver="DOCK", target=end,
                                    description=f"Docking procedure at station {end.name} [intermediate]")
                )
        return events