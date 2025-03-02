"""
RouteService using a two-pass planning approach based on the World Building Rules.

The approach is:
1. Build an ordered-scale path from a list of Locations.
2. Determine the required transfers between scales to yield a hybrid path that interleaves scale values with transfer types.
3. Generate detailed maneuvers from the transfer plan.
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
        controller: The controlling Station for this maneuver, if any.
    """
    maneuver: ManeuverType
    target: Location
    description: str = ""
    controller: Optional[Station] = None

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
    """Route planning service implementing a two-pass approach."""
    
    # Mapping from Scale names (or values) to a numeric order.
    # These numbers must follow the assumed ordering in our universe:
    # Station (lowest), then Moon, Planet, Star, Starsystem, Galaxy.
    _scale_order = {
        Scale.STATION: 1,
        Scale.MOON: 2,
        Scale.PLANET: 3,
        Scale.STAR: 4,
        "STARSYSTEM": 5,  # assuming these are the string values
        "GALAXY": 6,
    }
    
    def plan_route(self, origin: Location, destination: Location) -> List[NavigationEvent]:
        """
        Plans a route from origin to destination using a two-pass approach.
        
        The steps are:
            1. Build an ordered_scale_path from the low-level path.
            2. Determine a transfer plan from that scale path.
            3. Synthesize the maneuver events from the transfer plan.
            
        Returns:
            List[NavigationEvent]: The resulting list of maneuvers.
        """
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)
        if not path or len(path) < 2:
            return []
        
        # SPECIAL CASE: Two-node direct neighbor: use DIRECT_ASCENT but do not bypass departure/arrival.
        if len(path) == 2 and path[1] in universe.get_neighbors(path[0]):
            scale_path = self._build_scale_path(path)
            transfer_plan = [scale_path[0], ManeuverType.DIRECT_ASCENT, scale_path[1]]
            maneuvers = self._determine_maneuvers(transfer_plan, path)
            return maneuvers
        
        # Pass 1:
        scale_path = self._build_scale_path(path)
        overall_max = max(scale_path)
        
        # Pass 2: If overall maximum exceeds StarSystem, use hyperdrive logic.
        if overall_max > OrderedScale(Scale.STARSYSTEM):
            # Simplify the transfer plan for hyperdrive travel.
            transfer_plan = [
                scale_path[0],
                ManeuverType.INSERTION,
                scale_path[-1],
                ManeuverType.HYPERSPACE,
                scale_path[-1]
            ]
        else:
            transfer_plan = self._determine_transfer_plan(scale_path)
        
        # Pass 3:
        maneuvers = self._determine_maneuvers(transfer_plan, path)
        return maneuvers
    
    
    def _build_scale_path(self, path: List[Location]) -> List[int]:
        """
        Convert a list of Locations into an ordered-scale path (list of integers)
        representing each Location's scale.
        
        For example, a path from Earth Station to Phobos Station might produce:
            [1, 3, 4, 3, 2, 1]
        """
        scale_path = []
        for loc in path:
            concrete = loc.get_concrete_instance()
            scale_val = self._scale_order_value(concrete.scale)
            scale_path.append(scale_val)
        return scale_path
    
    
    def _scale_order_value(self, scale: str) -> int:
        """
        Convert a scale value (from the model) into an integer order value.
        
        If the scale is not recognized, return a high number.
        """
        return self._scale_order.get(scale, 99)
    
    
    def _determine_transfer_plan(self, scale_path: List[int]) -> List[Union[int, ManeuverType]]:
        """
        Given an ordered scale path (for example: [1, 3, 4, 3, 2, 1]),
        produce a hybrid object that interleaves scale values with transfer types.
        
        The rules are:
        - The first transfer (from the starting scale to the next) is an INSERTION.
        - For subsequent transfers, use SUBLIGHT (or HYPERSPACE if appropriate) to
            collapse upward–downward sequences.
        - The final scale is appended without a trailing transfer type.
        
        For the example:
            [1, 3, 4, 3, 2, 1]  ==>  [1, INSERTION, 3, SUBLIGHT, 3, SUBLIGHT, 2, 1]
        
        Note: More complex logic (e.g. switching to HYPERSPACE) can be added based on
        the maximum scale encountered.
        """
        if len(scale_path) < 2:
            return scale_path
        
        transfer_plan = [scale_path[0]]
        
        # For the first transition use INSERTION always.
        transfer_plan.append(ManeuverType.INSERTION)
        transfer_plan.append(scale_path[1])
        
        # Process intermediate transitions.
        # For simplicity, every subsequent edge will be marked as SUBLIGHT.
        for i in range(1, len(scale_path) - 1):
            # In a more advanced implementation, examine a window (prev, current, next)
            # to decide if a HYPERSPACE jump is warranted.
            # For now, we simply use SUBLIGHT for all transitions after the first edge.
            transfer_plan.append(ManeuverType.SUBLIGHT)
            transfer_plan.append(scale_path[i+1])
        
        return transfer_plan
    
    
    def _determine_maneuvers(self, transfer_plan: List[Union[int, ManeuverType]], location_path: List[Location]) -> List[NavigationEvent]:
        """
        Convert a transfer plan into a sequence of NavigationEvent maneuvers.
        
        The approach is:
         - The departure maneuvers depend on the starting scale:
             * If starting at a Station (scale 1), include UNDOCK.
         - For each transfer type in the transfer plan, insert maneuvers.
             * For an INSERTION segment, include INSERTION followed by CIRCULARIZE.
             * For a SUBLIGHT segment, include a preceding PLANE_CHANGE (if needed) and the SUBLIGHT burn,
               followed by CIRCULARIZE.
         - The final arrival maneuver depends on the final scale:
             * If the final destination is at Station scale, then DOCK; otherwise, DEORBIT and LAND.
        
        For example, the plan:
          [1, INSERTION, 3, SUBLIGHT, 3, SUBLIGHT, 2, 1]
        might yield:
          [UNDOCK, INSERTION, CIRCULARIZE, PLANE_CHANGE, SUBLIGHT, CIRCULARIZE, PLANE_CHANGE, SUBLIGHT, PLANE_CHANGE, DOCK]
        
        These maneuvers are generated in a universal way and do not depend on the names of the objects.
        """
        maneuvers: List[NavigationEvent] = []
        
        # Helper that creates a NavigationEvent given a maneuver type and a simple text target value.
        # (In a full system, the 'target' would be a Location; here we weave in descriptions.)
        def nav(m_type: ManeuverType, desc: str, target_location: Location, controller: Optional[Station] = None) -> NavigationEvent:
            return NavigationEvent(
                maneuver=m_type,
                target=target_location,
                description=desc,
                controller=controller
            )
        
        # Departure:
        start_scale = transfer_plan[0]
        start_location = location_path[0]
        # Always add departure maneuver based on start location:
        if start_scale == OrderedScale(Scale.STATION):
            maneuvers.append(nav(ManeuverType.UNDOCK, "Undock from station", start_location))
        else:
            maneuvers.append(nav(ManeuverType.LAUNCH, "Launch from body", start_location))
        
        # Process each transfer segment.
        # Transfer plan format: [start, TRANSFER_TYPE, scale, ... , final scale]
        current_location_idx = 0
        idx = 1
        while idx < len(transfer_plan) - 1:
            t_type = transfer_plan[idx]
            next_scale = transfer_plan[idx+1]
            
            # Advance to the next location in our path
            if current_location_idx < len(location_path) - 1:
                current_location_idx += 1
            target_location = location_path[current_location_idx]

            # Special case: Skip final SUBLIGHT to a station
            if (t_type == ManeuverType.SUBLIGHT and 
                next_scale == OrderedScale(Scale.STATION) and
                idx >= len(transfer_plan) - 3):
                idx += 2
                continue
                
            if t_type == ManeuverType.INSERTION:
                maneuvers.append(nav(ManeuverType.INSERTION, "Perform insertion burn", target_location))
                maneuvers.append(nav(ManeuverType.CIRCULARIZE, "Circularize orbit", target_location))
                idx += 2
            elif t_type == ManeuverType.DIRECT_ASCENT:
                maneuvers.append(nav(ManeuverType.DIRECT_ASCENT, "Direct ascent maneuver", target_location))
                idx += 2
            elif t_type == ManeuverType.SUBLIGHT:
                if next_scale != OrderedScale(Scale.STATION) and next_scale >= OrderedScale(Scale.PLANET):
                    departure_location = location_path[current_location_idx - 1] if current_location_idx > 0 else location_path[0]
                    ctrl = self.effective_controller(departure_location)
                    maneuvers.append(nav(ManeuverType.PLANE_CHANGE, "Perform plane change", target_location, controller=ctrl))
                departure_location = location_path[current_location_idx - 1] if current_location_idx > 0 else location_path[0]
                ctrl = self.effective_controller(departure_location)
                maneuvers.append(nav(ManeuverType.SUBLIGHT, "Execute sublight transfer burn", target_location, controller=ctrl))
                maneuvers.append(nav(ManeuverType.CIRCULARIZE, "Circularize after sublight transfer", target_location))
                idx += 2
            elif t_type == ManeuverType.HYPERSPACE:
                departure_location = location_path[current_location_idx - 1] if current_location_idx > 0 else location_path[0]
                ctrl = self.effective_controller(departure_location)
                maneuvers.append(nav(ManeuverType.SUBLIGHT, "Execute sublight burn to depart local orbit", target_location, controller=ctrl))
                destination_location = location_path[-1]
                maneuvers.append(nav(ManeuverType.HYPERSPACE, "Perform hyperspace jump", destination_location))
                maneuvers.append(nav(ManeuverType.SUBLIGHT, "Execute sublight burn into destination orbit", destination_location))
                maneuvers.append(nav(ManeuverType.CIRCULARIZE, "Circularize after hyperdrive arrival", destination_location))
                current_location_idx = len(location_path) - 1
                idx += 2
            else:
                idx += 1
        
        # Arrival:
        final_scale = transfer_plan[-1]
        final_location = location_path[-1]
        if final_scale == OrderedScale(Scale.STATION):
            maneuvers.append(nav(ManeuverType.PLANE_CHANGE, "Align orbit for docking", final_location))
            maneuvers.append(nav(ManeuverType.DOCK, "Dock at station", final_location))
        else:
            maneuvers.append(nav(ManeuverType.DEORBIT, "Begin deorbit burn", final_location))
            maneuvers.append(nav(ManeuverType.LANDING, "Perform landing maneuver", final_location))
        
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
