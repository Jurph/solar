"""
High-level routing services to plan journeys and determine maneuvers for ships.

This module builds on the low-level navigation capabilities provided by the
UniverseGraph class. It applies domain‐specific rules (using ship status, scales, and
local controllers) to decide which maneuvers to apply (e.g. TRANSFER vs HYPERSPACE) and
to synthesize navigation events from the low-level graph path.
"""

from typing import List, Optional, Tuple, Dict, Union
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

@dataclass(frozen=True)
class TransferSegment:
    """
    Represents a high-level transfer between two locations.
    
    Attributes:
        start: The starting location
        end: The ending location
        transfer_type: The type of transfer (SUBLIGHT, HYPERSPACE)
        max_scale: The maximum scale encountered during this transfer
    """
    start: Location
    end: Location
    transfer_type: ManeuverType
    max_scale: Scale

class RouteService:
    """Service for planning routes and maneuvers within the universe."""
    
    def plan_route(self, origin: Location, destination: Location) -> List[NavigationEvent]:
        """
        Plans a route from origin to destination using a three‑pass approach:
        
          1. Build an ordered scale path from the low‑level path.
          2. Determine the transfer plan from that scale path.
          3. Synthesize the maneuver events from the transfer plan.
        
        Returns:
            List[NavigationEvent]: The resulting list of maneuvers.
        """
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        if not path or len(path) < 2:
            return []
        
        # SPECIAL CASE: If there are only two nodes and they are direct neighbors,
        # use DIRECT_ASCENT (treated as a transfer type) wrapped in departure/arrival events.
        if len(path) == 2 and path[1] in universe.get_neighbors(path[0]):
            scale_path = self._build_scale_path(path)  # returns [OrderedScale, OrderedScale]
            # Override the normal transfer plan: use DIRECT_ASCENT instead of INSERTION/SUBLIGHT.
            transfer_plan = [scale_path[0], ManeuverType.DIRECT_ASCENT, scale_path[1]]
            maneuvers = self._determine_maneuvers(transfer_plan)
            return maneuvers
        
        # Pass 1: Build an ordered scale path (e.g., [1, 3, 4, 3, 2, 1]).
        scale_path = self._build_scale_path(path)
        
        # Compute overall maximum scale in the route.
        overall_max = max(scale_path)
        
        # Pass 2: Determine transfer plan.
        # Rule: First edge is INSERTION; subsequent edges normally use SUBLIGHT.
        # However, if the overall maximum scale exceeds StarSystem (i.e. >5),
        # then we use HYPERSPACE for all transfers (per Rule 2d).
        transfer_plan = self._determine_transfer_plan(scale_path, overall_max)
        
        # Pass 3: Convert the transfer plan into detailed maneuvers.
        maneuvers = self._determine_maneuvers(transfer_plan)
        return maneuvers
    
    def _build_scale_path(self, path: List[Location]) -> List[OrderedScale]:
        """
        Converts the low-level Location path into a list of OrderedScale values.
        
        Example: [Station, Planet, Star, Planet, Moon, Station] becomes
                 [Scale.STATION.value, Scale.PLANET.value, Scale.STAR.value, Scale.PLANET.value, Scale.MOON.value, Scale.STATION.value].
        """
        scale_path = []
        for loc in path:
            concrete = loc.get_concrete_instance()
            scale_val: OrderedScale = OrderedScale(concrete.scale)
            scale_path.append(scale_val)
        return scale_path
    
    def _determine_transfer_plan(self, scale_path: List[OrderedScale], overall_max: OrderedScale) -> List[Union[OrderedScale, ManeuverType]]:
        """
        Produces a hybrid transfer plan that interleaves OrderedScale values
        with transfer maneuver types.
        
        Rules:
          - The first transfer uses INSERTION.
          - If the overall maximum scale is higher than StarSystem, then
            all transfers become HYPERSPACE transfers.
          - Otherwise, subsequent transfers use SUBLIGHT.
        """
        if len(scale_path) < 2:
            return scale_path
        
        transfer_plan = [scale_path[0]]
        # First edge always uses INSERTION.
        transfer_plan.append(ManeuverType.INSERTION)
        transfer_plan.append(scale_path[1])
        
        for i in range(1, len(scale_path) - 1):
            if overall_max > OrderedScale(Scale.STARSYSTEM):
                t_type = ManeuverType.HYPERSPACE
            else:
                t_type = ManeuverType.SUBLIGHT
            transfer_plan.append(t_type)
            transfer_plan.append(scale_path[i+1])
        
        return transfer_plan
    
    def _determine_maneuvers(self, transfer_plan: List[Union[OrderedScale, ManeuverType]]) -> List[NavigationEvent]:
        """
        Converts the hybrid transfer plan into a sequence of NavigationEvent maneuvers.
        
        Methodology:
          - Departure:
              * If starting at a Station (scale == Scale.STATION), UNDOCK is required.
              * Otherwise, LAUNCH is used.
          - For each transfer segment:
              * INSERTION segments trigger an INSERTION burn and then CIRCULARIZE.
              * SUBLIGHT segments: if transferring between bodies of at least Planet scale,
                add a PLANE_CHANGE before executing SUBLIGHT.
              * HYPERSPACE segments: execute a SUBLIGHT burn away from the departure,
                then perform a HYPERSPACE jump, then perform a SUBLIGHT burn into the destination.
          - Arrival:
              * If final scale is Station, DOCK; otherwise, DEORBIT and LAND.
        
        Note: This synthesis is universal and does not depend on specific names.
        """
        maneuvers = []
        def nav(m_type: ManeuverType, desc: str) -> NavigationEvent:
            return NavigationEvent(
                maneuver=m_type,
                target=None,  # Target resolution logic can be added later.
                description=desc
            )
        
        # Departure:
        start_scale = transfer_plan[0]
        if start_scale == OrderedScale(Scale.STATION):
            maneuvers.append(nav(ManeuverType.UNDOCK, "Undock from station"))
        else:
            maneuvers.append(nav(ManeuverType.LAUNCH, "Launch from body"))
        
        # Process each transfer segment.
        # Transfer plan format: [start, TRANSFER_TYPE, scale, TRANSFER_TYPE, scale, ..., final_scale]
        for idx in range(1, len(transfer_plan) - 1, 2):
            t_type = transfer_plan[idx]
            next_scale = transfer_plan[idx+1]
            if t_type == ManeuverType.INSERTION:
                maneuvers.append(nav(ManeuverType.INSERTION, "Perform insertion burn"))
                maneuvers.append(nav(ManeuverType.CIRCULARIZE, "Circularize orbit"))
            elif t_type == ManeuverType.DIRECT_ASCENT:
                maneuvers.append(nav(ManeuverType.DIRECT_ASCENT, "Direct ascent maneuver"))
            elif t_type == ManeuverType.SUBLIGHT:
                # If transferring into a station, skip the SUBLIGHT/CIRCULARIZE step;
                # the arrival sequence will handle docking.
                if next_scale == OrderedScale(Scale.STATION):
                    continue
                # Rule 2a/2b: For sublight transfers between bodies of at least planetary scale,
                # add a PLANE_CHANGE before executing SUBLIGHT.
                if next_scale >= OrderedScale(Scale.PLANET):
                    maneuvers.append(nav(ManeuverType.PLANE_CHANGE, "Perform plane change"))
                maneuvers.append(nav(ManeuverType.SUBLIGHT, "Execute sublight transfer burn"))
                maneuvers.append(nav(ManeuverType.CIRCULARIZE, "Circularize after sublight transfer"))
            elif t_type == ManeuverType.HYPERSPACE:
                maneuvers.append(nav(ManeuverType.SUBLIGHT, "Execute sublight burn to depart local orbit"))
                maneuvers.append(nav(ManeuverType.HYPERSPACE, "Perform hyperspace jump"))
                maneuvers.append(nav(ManeuverType.SUBLIGHT, "Execute sublight burn into destination orbit"))
        
        # Arrival:
        final_scale = transfer_plan[-1]
        if final_scale == OrderedScale(Scale.STATION):
            # If arriving at a station orbiting a Moon/Planet,
            # perform a PLANE_CHANGE to match orbit before docking.
            maneuvers.append(nav(ManeuverType.PLANE_CHANGE, "Align orbit for docking"))
            maneuvers.append(nav(ManeuverType.DOCK, "Dock at station"))
        else:
            maneuvers.append(nav(ManeuverType.DEORBIT, "Begin deorbit burn"))
            maneuvers.append(nav(ManeuverType.LANDING, "Perform landing maneuver"))
        
        return maneuvers

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
