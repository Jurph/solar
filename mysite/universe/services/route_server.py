"""
High-level routing services to plan journeys and determine maneuvers for ships.

This module builds on the low-level navigation capabilities provided by the
UniverseGraph class. It applies domain‐specific rules (using ship status, scales, and
local controllers) to decide which maneuvers to apply (e.g. TRANSFER vs HYPERSPACE) and
to synthesize navigation events from the low-level graph path.
"""

from typing import List, Optional
from ..models.base import Location
from ..models.scale import Scale, OrderedScale
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
        
        This method:
        1. Uses UniverseGraph to obtain a path between origin and destination
        2. Analyzes the path to determine the maximum scale encountered
        3. Generates appropriate NavigationEvents based on the path structure
        
        The event sequence follows strict rules:
        
        DEPARTURE (first few nodes of path):
        - From Station: UNDOCK -> INSERTION -> CIRCULARIZE
        - From Planet/Moon (to neighbor): DIRECT_ASCENT
        - From Planet/Moon (not neighbor): LAUNCH -> INSERTION -> CIRCULARIZE
        
        TRANSIT (analyzed by maximum scale in path):
        - Within local planet's influence (max_scale <= PLANET):
            * SUBLIGHT transfer only
        - Within star system (max_scale <= STAR):
            * PLANE_CHANGE -> SUBLIGHT to destination planet
            * Skip intermediate star-scale nodes
        - Within star cluster (max_scale <= STARSYSTEM):
            * PLANE_CHANGE -> SUBLIGHT to destination planet
            * Skip intermediate system-scale nodes
        - Between star systems (max_scale > STARSYSTEM):
            * SUBLIGHT transfer away from origin planet
            * HYPERDRIVE to destination system
            * SUBLIGHT transfer to destination planet
            * Skip all intermediate galaxy/cluster nodes
        
        ARRIVAL (final few nodes of path):
        - To Planet: DEORBIT -> LAND
        - To Station (around planet): DOCK
        - To Moon: SUBLIGHT -> DEORBIT -> LAND
        - To Station (around moon): SUBLIGHT -> CIRCULARIZE -> PLANE_CHANGE -> DOCK

        Args:
            origin: Starting Location
            destination: Ending Location
            
        Returns:
            List[NavigationEvent]: Sequence of navigation events for the journey
            
        Raises:
            ValueError: If no valid path exists between origin and destination
        """
        # Get the complete path from the navigation graph
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        
        # Determine the maximum scale encountered in the path
        max_scale = self._determine_max_scale(path)
        
        events: List[NavigationEvent] = []
        
        # Generate DEPARTURE sequence based on origin type and first hop
        if len(path) > 1:
            events.extend(self._generate_departure_sequence(path))
        
        # Generate TRANSIT sequence based on max_scale
        if len(path) > 2:
            events.extend(self._generate_transit_sequence(path[1:-1], max_scale))
        
        # Generate ARRIVAL sequence based on destination type
        if len(path) > 1:
            events.extend(self._generate_arrival_sequence(path[-2:]))
        
        return events

    def _determine_max_scale(self, path: List[Location]) -> Scale:
        """Helper to determine the maximum scale encountered in a path."""
        return max(location.scale for location in path)

    def _generate_departure_sequence(self, path: List[Location]) -> List[NavigationEvent]:
        """
        Generate departure sequence based on WBR rules:
        
        Rule: "If your path starts with a Station, UNDOCK then do an INSERTION burn 
        and then CIRCULARIZE to orbit."
        
        Rule: "If your path starts with a Moon or Planet, and the destination is a neighbor, 
        you can do a DIRECT ASCENT"
        
        Rule: "If your path starts with a Moon or Planet and your destination is not a neighbor, 
        you'll need to LAUNCH, do an INSERTION burn, and then CIRCULARIZE to achieve orbit."
        """
        events: List[NavigationEvent] = []
        start = path[0]
        next_stop = path[1] if len(path) > 1 else None
        universe = UniverseGraph.get_instance()

        if start.scale == Scale.STATION:
            if next_stop and next_stop in universe.get_neighbors(start) and len(path) == 2:
                # Direct neighbor case
                events.extend([
                    NavigationEvent(
                        maneuver=ManeuverType.UNDOCK,
                        target=start,
                        description=f"Undock from station {start.name}"
                    ),
                    NavigationEvent(
                        maneuver=ManeuverType.DIRECT_ASCENT,
                        target=next_stop,
                        description=f"Direct ascent from {start.name} to {next_stop.name}"
                    )
                ])
            else:
                # Standard station departure
                events.extend([
                    NavigationEvent(
                        maneuver=ManeuverType.UNDOCK,
                        target=start,
                        description=f"Undock from station {start.name}"
                    ),
                    NavigationEvent(
                        maneuver=ManeuverType.INSERTION,
                        target=start,
                        description=f"Initial transfer burn from station {start.name}"
                    ),
                    NavigationEvent(
                        maneuver=ManeuverType.CIRCULARIZE,
                        target=start,
                        description=f"Circularize after undocking at {start.name}"
                    )
                ])
                
        elif start.scale in {Scale.PLANET, Scale.MOON}:
            if next_stop and next_stop in universe.get_neighbors(start) and len(path) == 2:
                # Rule: "DIRECT ASCENT is disruptive and dangerous!"
                events.append(
                    NavigationEvent(
                        maneuver=ManeuverType.DIRECT_ASCENT,
                        target=next_stop,
                        description=f"Direct ascent from {start.name} to {next_stop.name} - Caution: Disruptive maneuver!"
                    )
                )
            else:
                # Standard launch sequence
                events.extend([
                    NavigationEvent(
                        maneuver=ManeuverType.LAUNCH,
                        target=start,
                        description=f"Launch from {start.name}"
                    ),
                    NavigationEvent(
                        maneuver=ManeuverType.INSERTION,
                        target=start,
                        description=f"Insertion burn to exit {start.name}'s gravity well"
                    ),
                    NavigationEvent(
                        maneuver=ManeuverType.CIRCULARIZE,
                        target=start,
                        description=f"Circularize orbit after launch from {start.name}"
                    )
                ])
        return events

    def _generate_transit_sequence(self, path: List[Location], max_scale: Scale) -> List[NavigationEvent]:
        """
        Generate transit maneuvers following World Building Rules document.
        """
        events: List[NavigationEvent] = []
        i = 0
        
        while i < len(path) - 1:
            start = path[i]
            end = path[i + 1]
            
            # Rule: "Transfers within the local area around a Planet (from Luna to Earth, 
            # for example, or Mars to Phobos) are SUBLIGHT and don't require a PLANE CHANGE"
            if max_scale <= Scale.PLANET:
                events.append(
                    NavigationEvent(
                        maneuver=ManeuverType.SUBLIGHT,
                        target=end,
                        description=f"Sublight transfer from {start.name} to {end.name}"
                    )
                )
                # Rule: "Entering a Planet's sphere of influence after a sublight TRANSFER 
                # you'll need to CIRCULARIZE"
                if end.scale in [Scale.PLANET, Scale.MOON]:
                    events.append(
                        NavigationEvent(
                            maneuver=ManeuverType.CIRCULARIZE,
                            target=end,
                            description=f"Establish orbit around {end.name}"
                        )
                    )
                    
            # Rule: "If the local Star is the single largest-scale object on the path, 
            # then you will need a PLANE CHANGE, and then a SUBLIGHT transfer within the star system: 
            # not to the local Star, but to the destination planet!"
            elif max_scale <= Scale.STAR:
                if start.scale <= Scale.PLANET:  # Only do plane change from planet-scale objects
                    events.append(
                        NavigationEvent(
                            maneuver=ManeuverType.PLANE_CHANGE,
                            target=end,
                            description="Align for interplanetary transfer"
                        )
                    )
                events.append(
                    NavigationEvent(
                        maneuver=ManeuverType.SUBLIGHT,
                        target=path[-1],  # Direct to destination planet
                        description=f"Sublight transfer to {path[-1].name}"
                    )
                )
                # Skip intermediate star-scale nodes
                while i < len(path) - 1 and path[i + 1].scale == Scale.STAR:
                    i += 1
                    
            # Rule: "If the local StarSystem is the single largest-scale object on the path,
            # then you will still need a PLANE CHANGE and a SUBLIGHT transfer within the star system"
            elif max_scale <= Scale.STARSYSTEM:
                if start.scale <= Scale.PLANET:
                    events.append(
                        NavigationEvent(
                            maneuver=ManeuverType.PLANE_CHANGE,
                            target=end,
                            description="Align for system transfer"
                        )
                    )
                events.append(
                    NavigationEvent(
                        maneuver=ManeuverType.SUBLIGHT,
                        target=path[-1],  # Direct to destination planet
                        description=f"Sublight transfer to {path[-1].name}"
                    )
                )
                # Skip intermediate system-scale nodes
                while i < len(path) - 1 and path[i + 1].scale == Scale.STARSYSTEM:
                    i += 1
                    
            # Rule: "If the largest scale in the path is higher than StarSystem, then you need 
            # a HYPERDRIVE transfer... You'll do a SUBLIGHT transfer away from the Planet scale, 
            # a HYPERSPACE transfer to the destination system, and a SUBLIGHT transfer to the Planet"
            else:
                events.append(
                    NavigationEvent(
                        maneuver=ManeuverType.SUBLIGHT,
                        target=start,
                        description=f"Sublight transfer away from {start.name}"
                    )
                )
                
                # Find the destination planet/moon
                dest_idx = len(path) - 1
                while dest_idx > i and path[dest_idx].scale > Scale.PLANET:
                    dest_idx -= 1
                    
                events.append(
                    NavigationEvent(
                        maneuver=ManeuverType.HYPERSPACE,
                        target=path[dest_idx],
                        description=f"Hyperspace jump to {path[dest_idx].name} system"
                    )
                )
                events.append(
                    NavigationEvent(
                        maneuver=ManeuverType.SUBLIGHT,
                        target=path[dest_idx],
                        description=f"Sublight transfer to {path[dest_idx].name}"
                    )
                )
                
                # Skip all intermediate galaxy/cluster nodes
                i = dest_idx - 1
                
            i += 1
        return events

    def _generate_arrival_sequence(self, path: List[Location]) -> List[NavigationEvent]:
        """
        Generate arrival sequence based on WBR rules:
        
        Rule: "If the Planet is your destination you can then DEORBIT and LAND"
        Rule: "If the Planet is not your final destination you should CIRCULARIZE around 
        the Planet to get into a stable orbit for subsequent maneuvers"
        Rule: "If a station around the Moon is your destination, you will need to 
        CIRCULARIZE around the Moon, do a PLANE CHANGE, and then DOCK"
        """
        events: List[NavigationEvent] = []
        final_stop = path[-1]
        parent = path[-2] if len(path) > 1 else None

        if final_stop.scale == Scale.STATION:
            if parent and parent.scale == Scale.MOON:
                # Station around moon requires extra steps
                events.extend([
                    NavigationEvent(
                        maneuver=ManeuverType.CIRCULARIZE,
                        target=parent,
                        description=f"Establish stable orbit around {parent.name}"
                    ),
                    NavigationEvent(
                        maneuver=ManeuverType.PLANE_CHANGE,
                        target=final_stop,
                        description=f"Align for approach to {final_stop.name}"
                    ),
                    NavigationEvent(
                        maneuver=ManeuverType.DOCK,
                        target=final_stop,
                        description=f"Dock at station {final_stop.name}"
                    )
                ])
            else:
                # Direct station docking
                events.append(
                    NavigationEvent(
                        maneuver=ManeuverType.DOCK,
                        target=final_stop,
                        description=f"Dock at station {final_stop.name}"
                    )
                )
        elif final_stop.scale in {Scale.PLANET, Scale.MOON}:
            events.extend([
                NavigationEvent(
                    maneuver=ManeuverType.DEORBIT,
                    target=final_stop,
                    description=f"Begin descent to {final_stop.name}"
                ),
                NavigationEvent(
                    maneuver=ManeuverType.LANDING,
                    target=final_stop,
                    description=f"Land on {final_stop.name}"
                )
            ])

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
        return universe.get_local_graph(current, OrderedScale(max_scale))
