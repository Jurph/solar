"""
RouteService using a two-pass planning approach based on the World Building Rules.

The approach is:
1. Build an ordered-scale path from a list of Locations.
2. Determine the required transfers between scales to yield a hybrid path that interleaves scale values with transfer types.
3. Generate detailed maneuvers from the transfer plan.
"""

from typing import List, Union, Optional
from ..models.base import Location
from ..models.scale import Scale, OrderedScale
from ..models.navigation import ManeuverType, UniverseGraph, NavigationEvent, is_planetary
from dataclasses import dataclass
import random
from mysite.universe.models.actor import Controller

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
    
    # We use OrderedScale from the Scale model to handle scale ordering
    # This provides a consistent way to compare scales across the application
    
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
        
        # Compute overall_max from the original path scales
        original_scale_path = self._build_scale_path(path)
        overall_max = max(original_scale_path)

        # Compress the path to remove transit nodes (e.g., Stars) not needed for maneuver events
        compressed_path = self._compress_location_path(path)

        # SPECIAL CASE: Direct ascent if the path has exactly two nodes
        if len(path) == 2:
            origin_type = origin.get_concrete_instance().get_type_name()
            dest_type = destination.get_concrete_instance().get_type_name()
            events = []

            # Departure phase
            if origin_type == "Station":
                events.append(NavigationEvent(
                    maneuver=ManeuverType.UNDOCK,
                    origin=origin,
                    current=origin,
                    next=destination,
                    destination=destination,
                    description=f"UNDOCK from {origin.name} to {destination.name}",
                    controller=None
                ))
            elif origin_type == "Moon":
                events.append(NavigationEvent(
                    maneuver=ManeuverType.LAUNCH,
                    origin=origin,
                    current=origin,
                    next=destination,
                    destination=destination,
                    description=f"LAUNCH from {origin.name} to {destination.name}",
                    controller=None
                ))

            # Transfer phase: always one DIRECT_ASCENT event
            events.append(NavigationEvent(
                maneuver=ManeuverType.DIRECT_ASCENT,
                origin=origin,
                current=origin,
                next=destination,
                destination=destination,
                description=f"DIRECT_ASCENT from {origin.name} to {destination.name}",
                controller=None
            ))

            # Arrival phase
            if dest_type == "Moon" and origin_type != "Moon":
                events.append(NavigationEvent(
                    maneuver=ManeuverType.CIRCULARIZE,
                    origin=origin,
                    current=destination,
                    next=destination,
                    destination=destination,
                    description=f"CIRCULARIZE at {destination.name}",
                    controller=None
                ))
            events.append(NavigationEvent(
                maneuver=ManeuverType.DEORBIT,
                origin=origin,
                current=destination,
                next=destination,
                destination=destination,
                description=f"DEORBIT at {destination.name}",
                controller=None
            ))
            events.append(NavigationEvent(
                maneuver=ManeuverType.LANDING,
                origin=origin,
                current=destination,
                next=destination,
                destination=destination,
                description=f"LANDING at {destination.name}",
                controller=None
            ))
            return self._enhance_with_controllers(events)
        
        # Pass 1: Build scale path from the compressed path
        scale_path = self._build_scale_path(compressed_path)
        
        # Pass 2: Determine transfer plan
        if overall_max > OrderedScale(Scale.STARSYSTEM):
            transfer_plan = [
                scale_path[0],
                ManeuverType.INSERTION,
                scale_path[-1],
                ManeuverType.HYPERSPACE,
                scale_path[-1]
            ]
        else:
            transfer_plan = self._determine_transfer_plan(scale_path)
        
        # Pass 3: Generate maneuvers using the compressed path and overall_max from the original path
        maneuvers = self._determine_maneuvers(transfer_plan, compressed_path, overall_max)
        return maneuvers
    
    
    def _build_scale_path(self, path: List[Location]) -> List[int]:
        """
        Convert a list of Locations into an ordered-scale path (list of integers)
        representing each Location's scale.
        
        For example, a path from Earth Station to Phobos Station might produce:
            [OrderedScale.STATION, OrderedScale.PLANET, OrderedScale.STARSYSTEM, 
            OrderedScale.PLANET, OrderedScale.MOON, OrderedScale.STATION]
        """
        scale_path = []
        for loc in path:
            concrete = loc.get_concrete_instance()
            scale_val = OrderedScale(concrete.scale)
            scale_path.append(scale_val)
        return scale_path
    
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
    
    
    def _determine_maneuvers(self, transfer_plan: List[Union[int, ManeuverType]], location_path: List[Location], overall_max: int) -> List[NavigationEvent]:
        """Using a 3-pass approach, create navigation events from the transfer plan.
        
        This function handles:
        1. Direct neighbor routes - these are simple direct-ascent maneuvers.
        2. Hyperspace routes - require specific departure, hyperspace, and arrival procedures.
        3. Non-hyperspace routes - standard multi-leg journeys.
        """
        if not location_path or len(location_path) < 2:
            raise ValueError("Invalid route: Path must contain at least two locations")

        # Compress the path to remove irrelevant transit nodes, keeping only the key locations
        compressed_path = self._compress_location_path(location_path)

        origin = compressed_path[0]
        destination = compressed_path[-1]
        next_location = destination  # For simplicity, default next_location to destination
        origin_type = origin.get_concrete_instance().get_type_name()
        dest_type = destination.get_concrete_instance().get_type_name()

        # Initialize events list
        events = []

        # If the transfer_plan explicitly indicates a direct ascent (i.e. exactly three elements with DIRECT_ASCENT in the middle), handle as a direct neighbor route
        if len(transfer_plan) == 3 and isinstance(transfer_plan[1], ManeuverType) and transfer_plan[1] == ManeuverType.DIRECT_ASCENT:
            def make_direct_event(maneuver: ManeuverType) -> NavigationEvent:
                # For arrival maneuvers, set current to destination
                current_loc = origin
                if maneuver in (ManeuverType.DEORBIT, ManeuverType.LANDING, ManeuverType.DOCK, ManeuverType.CIRCULARIZE):
                    current_loc = destination
                
                return NavigationEvent(
                    maneuver=maneuver,
                    origin=origin,
                    current=current_loc,
                    next=destination,
                    destination=destination,
                    description=f"{maneuver.name} from {origin.name} to {destination.name}",
                    controller=None
                )
            # Clear the existing events list for direct ascent
            events.clear()
            
            if origin_type == "Station":
                events.append(make_direct_event(ManeuverType.UNDOCK))
            elif origin_type == "Moon":
                events.append(make_direct_event(ManeuverType.LAUNCH))
            events.append(make_direct_event(ManeuverType.DIRECT_ASCENT))
            if dest_type == "Station":
                events.append(make_direct_event(ManeuverType.DOCK))
            elif dest_type == "Moon":
                events.extend([
                    make_direct_event(ManeuverType.CIRCULARIZE),
                    make_direct_event(ManeuverType.DEORBIT),
                    make_direct_event(ManeuverType.LANDING)
                ])
            else:
                events.extend([
                    make_direct_event(ManeuverType.DEORBIT),
                    make_direct_event(ManeuverType.LANDING)
                ])
            # Direct ascent events are complete, skip to the controller enhancement
                return self._enhance_with_controllers(events)
                
        # Multi-leg journey branch

        def make_departure_event(maneuver: ManeuverType) -> NavigationEvent:
            """Create a NavigationEvent for the departure phase (current = origin)."""
            return NavigationEvent(
                maneuver=maneuver,
                origin=origin,
                current=origin,
                next=next_location,
                destination=destination,
                description=f"{maneuver.name} from {origin.name} to {destination.name}",
                controller=None
            )
            
        def make_transfer_event(maneuver: ManeuverType) -> NavigationEvent:
            """Create a NavigationEvent for the transfer phase (current = origin)."""
            return NavigationEvent(
                maneuver=maneuver,
                origin=origin,
                current=origin,
                next=next_location,
                destination=destination,
                description=f"{maneuver.name} from {origin.name} to {destination.name}",
                controller=None
            )
            
        def make_transfer_arrival_event(maneuver: ManeuverType) -> NavigationEvent:
            """Create a NavigationEvent for the arrival sub-phase of transfer (current = destination)."""
            return NavigationEvent(
                maneuver=maneuver,
                origin=origin,
                current=destination,
                next=next_location,
                destination=destination,
                description=f"{maneuver.name} from {origin.name} to {destination.name}",
                controller=None
            )

        # 1. DEPARTURE PHASE - Generate departure events based on origin type
        if origin_type == "Station":
            events.append(make_departure_event(ManeuverType.UNDOCK))
            events.append(make_departure_event(ManeuverType.INSERTION))
            events.append(make_departure_event(ManeuverType.CIRCULARIZE))
        elif origin_type in ("Planet", "Moon") or is_planetary(origin):
            events.append(make_departure_event(ManeuverType.LAUNCH))
            events.append(make_departure_event(ManeuverType.INSERTION))
            events.append(make_departure_event(ManeuverType.CIRCULARIZE))

        # 2. TRANSFER PHASE - Handle the transfer logic based on the transfer plan
        if len(transfer_plan) == 3:
            # Simple direct transfer: for a direct hop, add one event.
            if dest_type == "Station":
                events.append(make_transfer_event(ManeuverType.PLANE_CHANGE))
            else:
                events.append(make_transfer_event(ManeuverType.SUBLIGHT))
        else:
            is_origin_planetary = origin_type in ("Planet", "Moon") or is_planetary(origin)
            if is_origin_planetary:
                if not any(isinstance(x, ManeuverType) and x == ManeuverType.HYPERSPACE for x in transfer_plan):
                    # Non-hyperspace transfer
                    if dest_type == "Station":
                        if len(transfer_plan) == 5:
                            # Single-leg transfer: produce 4 events
                            events.append(make_transfer_arrival_event(ManeuverType.PLANE_CHANGE))
                            events.append(make_transfer_event(ManeuverType.SUBLIGHT))
                            events.append(make_transfer_arrival_event(ManeuverType.CIRCULARIZE))
                            events.append(make_transfer_arrival_event(ManeuverType.PLANE_CHANGE))
                        else:
                            # Multi-leg transfer: produce standard 6 events
                            events.append(make_transfer_event(ManeuverType.PLANE_CHANGE))
                            events.append(make_transfer_event(ManeuverType.SUBLIGHT))
                            events.append(make_transfer_event(ManeuverType.CIRCULARIZE))
                            events.append(make_transfer_arrival_event(ManeuverType.SUBLIGHT))
                            events.append(make_transfer_arrival_event(ManeuverType.CIRCULARIZE))
                            events.append(make_transfer_arrival_event(ManeuverType.PLANE_CHANGE))
                    else:
                        # For transfers between celestial bodies (Planet/Moon to Planet/Moon), use arrival style events
                        events.append(make_transfer_arrival_event(ManeuverType.SUBLIGHT))
                        events.append(make_transfer_arrival_event(ManeuverType.CIRCULARIZE))
                else:
                    # Hyperspace transfer branch - use arrival events with current set to destination
                    hyperspace_segments = [ (i, t) for i, t in enumerate(transfer_plan) if isinstance(t, ManeuverType) and t == ManeuverType.HYPERSPACE ]
                    for i, _ in hyperspace_segments:
                        # Departure sub-phase
                        events.append(make_transfer_event(ManeuverType.SUBLIGHT))
                        events.append(make_transfer_event(ManeuverType.HYPERSPACE))
                        # Arrival sub-phase: set current to destination
                        events.append(make_transfer_arrival_event(ManeuverType.SUBLIGHT))
                        events.append(make_transfer_arrival_event(ManeuverType.CIRCULARIZE))
                    if dest_type == "Station":
                        events.append(make_transfer_arrival_event(ManeuverType.PLANE_CHANGE))
            else:
                # Fallback: simple transfer if origin is not planetary
                events.append(make_transfer_event(ManeuverType.SUBLIGHT))
                events.append(make_transfer_event(ManeuverType.CIRCULARIZE))

        # 3. ARRIVAL PHASE - Add arrival maneuvers based on destination type
        if dest_type == "Station":
            events.append(make_transfer_arrival_event(ManeuverType.DOCK))
        elif dest_type in ("Planet", "Moon") or is_planetary(destination):
            events.append(make_transfer_arrival_event(ManeuverType.DEORBIT))
            events.append(make_transfer_arrival_event(ManeuverType.LANDING))
        
        return self._enhance_with_controllers(events)
    
    def _enhance_with_controllers(self, events: List[NavigationEvent]) -> List[NavigationEvent]:
        """
        Helper method to enhance all events with proper controller information.
        
        Rules for controller assignment:
        1. For departure maneuvers (LAUNCH, UNDOCK, INSERTION), use the controller of the origin/departure location
        2. For arrival maneuvers (DOCK, DEORBIT, LANDING), use the controller of the destination
        3. For transfer maneuvers (SUBLIGHT, HYPERSPACE, etc.), use the controller of the current location
        """
        enhanced_events: List[NavigationEvent] = []
        
        for event in events:
            # Determine which location should provide the controller based on maneuver type and context
            if event.maneuver in [ManeuverType.LAUNCH, ManeuverType.UNDOCK, ManeuverType.INSERTION]:
                # Departure maneuvers - controlled by the origin/departure location
                controller_loc = event.origin
            elif event.maneuver in [ManeuverType.DOCK, ManeuverType.DEORBIT, ManeuverType.LANDING]:
                # Arrival maneuvers - controlled by the destination
                controller_loc = event.destination
            else:
                # Transfer maneuvers - controlled by the current location
                controller_loc = event.current
            
            # Find the effective controller for this location
            controller = self.effective_controller(controller_loc)
            
            # Update the event with the proper controller information
            updated_event = NavigationEvent(
                maneuver=event.maneuver,
                origin=event.origin,
                current=event.current,
                next=event.next,
                destination=event.destination,
                description=event.description,
                controller=controller
            )
            enhanced_events.append(updated_event)
        
        return enhanced_events

    def effective_controller(self, location: Location) -> Union[Controller, Location]:
        """
        Determines the controlling entity for a given Location.
        
        Rules:
        1. Select the nearest local Location of type Station whose name contains 'Control' or 'Dispatch'.
        2. If none, select the nearest local Location of type Station.
        3. If still none, select the nearest local Location of type Planet or Moon.
        4. Otherwise, return the location itself.
        
        For any control station found, return its associated Controller actor.
        If no Controller actor exists for a control station, create one.
        """
        universe = UniverseGraph.get_instance()
        concrete_location = location.get_concrete_instance()
        local_nodes = universe.get_local_graph(concrete_location, OrderedScale(Scale.PLANET))
        
        # Helper function to compute path distance
        def distance(node: Location) -> int:
            path = universe.get_path(concrete_location, node)
            return len(path) if path else float('inf')
            
        # Helper to get actual type name (Station, Planet, etc.)
        def get_type_name(node: Location) -> str:
            try:
                return node.get_concrete_instance().__class__.__name__
            except Exception:
                return ""
        
        # 1. Find nearest Station with "Control" or "Dispatch" in name
        control_stations = []
        for node in local_nodes:
            node_type = get_type_name(node)
            if node_type == "Station" and ("Control" in node.name or "Dispatch" in node.name):
                control_stations.append(node)
                
        if control_stations:
            station = min(control_stations, key=distance)
            # Look up or create the Controller actor for this station
            controller = Controller.objects.filter(name=station.name).first()
            if not controller:
                controller = Controller.create(name=station.name, location=station)
            return controller
            
        # 2. Find nearest Station
        stations = []
        for node in local_nodes:
            if get_type_name(node) == "Station":
                stations.append(node)
                
        if stations:
            station = min(stations, key=distance)
            # For non-control stations, return the station itself
            return station
            
        # 3. Find nearest Planet or Moon
        celestials = []
        for node in local_nodes:
            node_type = get_type_name(node)
            if node_type in ["Planet", "Moon"]:
                celestials.append(node)
                
        if celestials:
            return min(celestials, key=distance)
            
        # 4. Return the location itself
        return concrete_location

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
        if not ship.current_location or ship.current_location.scale > Scale.PLANET:
            eligible_origins = [loc for loc in Location.objects.all() if loc.scale <= Scale.PLANET]
            if not eligible_origins:
                raise ValueError("No eligible origin locations (scale <= Planet) found in the universe.")
            origin = random.choice(eligible_origins)
            ship.current_location = origin
            ship.save()
        else:
            origin = ship.current_location

        destination = self.pick_random_destination(excluding=origin, max_scale=Scale.PLANET)
        print(f"Random journey: {origin.name} -> {destination.name}")
        universe = UniverseGraph.get_instance()
        path = universe.get_path(origin, destination)

        # Use plan_route to generate the full route with controller information
        events = self.plan_route(origin, destination)

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
                        controller=self.effective_controller(departure_loc)
                    )
                else:
                    events[i] = NavigationEvent(
                        maneuver=event.maneuver,
                        origin=event.origin,
                        current=event.current,
                        next=event.next,
                        destination=event.destination,
                        description=event.description,
                        controller=self.effective_controller(event.destination)
                    )
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

    def pretty_print_events(self, events: List[NavigationEvent], include_headers: bool = True) -> str:
        """
        Creates a readable table of navigation events with key information.
        
        Args:
            events: List of NavigationEvent objects
            include_headers: Whether to include column headers in the output
            
        Returns:
            Formatted string representation of the events
        """
        if not events:
            return "No navigation events to display"
        
        # Determine column widths based on content
        origins = []
        
        # For the first event, we don't have a previous target, so use the event's target
        # as the origin (this is a simplification; in reality the first event's origin
        # should be determined elsewhere)
        for i, event in enumerate(events):
            if i == 0:
                # For the first event, we assume origin information might be in the description
                # or we just use "STARTING POINT" as a placeholder
                origins.append("STARTING POINT")
            else:
                # For subsequent events, the origin is the previous event's target
                origins.append(events[i-1].destination.name if events[i-1].destination else "Unknown")
        
        # Calculate column widths
        origin_width = max(len("Origin"), max(len(str(o)) for o in origins))
        next_stop_width = max(len("Next Stop"), max(len(str(e.destination.name)) if e.destination else 0 for e in events))
        maneuver_width = max(len("Maneuver Type"), max(len(str(e.maneuver.name)) for e in events))
        controller_width = max(len("Effective Controller"), 
                            max(len(str(e.controller.name)) if e.controller else len("None") for e in events))
        
        # Create formatting template
        row_template = f"{{:{origin_width}}} | {{:{next_stop_width}}} | {{:{maneuver_width}}} | {{:{controller_width}}}"
        
        # Build the table
        result = []
        
        # Add headers if requested
        if include_headers:
            result.append(row_template.format("Origin", "Next Stop", "Maneuver Type", "Effective Controller"))
            result.append("-" * (origin_width + next_stop_width + maneuver_width + controller_width + 9))  # +9 for separators
        
        # Add data rows
        for i, event in enumerate(events):
            origin = origins[i]
            next_stop = event.destination.name if event.destination else "Unknown"
            maneuver_type = event.maneuver.name
            controller = event.controller.name if event.controller else "None"
            
            result.append(row_template.format(origin, next_stop, maneuver_type, controller))
        
        return "\n".join(result)

    def _compress_location_path(self, location_path: List[Location]) -> List[Location]:
        """Compress the location path by retaining only essential nodes: the first and last nodes are always kept,
        and any intermediate node whose concrete type is one of 'Planet', 'Moon', or 'Station'."""
        if not location_path:
            return location_path
        compressed = [location_path[0]]
        for node in location_path[1:-1]:
            node_type = node.get_concrete_instance().get_type_name()
            if node_type in ("Planet", "Moon", "Station"):
                compressed.append(node)
        compressed.append(location_path[-1])
        return compressed

    def get_event_duration(self, event: NavigationEvent) -> float:
        """
        Returns the physics-based duration of a navigation event.
        
        Uses ManeuverPhysicsService to calculate realistic durations based on:
        - Maneuver type (LAUNCH, CIRCULARIZE, SUBLIGHT, etc.)
        - Planetary properties (gravity, radius, atmosphere)
        - Orbital mechanics (distances, velocities)
        
        Args:
            event: NavigationEvent object
            
        Returns:
            Duration in seconds
        """
        from mysite.universe.services.maneuver_physics import get_maneuver_physics_service
        from mysite.universe.models.celestial import Planet, Moon, PhysicalBody
        
        physics = get_maneuver_physics_service()
        maneuver_type = event.maneuver.value if hasattr(event.maneuver, 'value') else str(event.maneuver)
        
        # Get the relevant body for this maneuver
        body = self._get_relevant_body_for_maneuver(event)
        body_params = self._extract_body_params(body) if body else {}
        
        # Build navigation context
        nav_context = self._build_physics_nav_context(event, body)
        
        # Calculate duration using physics service
        duration = physics.get_maneuver_duration(
            maneuver_type=maneuver_type,
            body_params=body_params,
            nav_context=nav_context,
        )
        
        return duration
    
    def _get_relevant_body_for_maneuver(self, event: NavigationEvent) -> Optional["PhysicalBody"]:
        """
        Determine the relevant planet/moon for physics calculations.
        
        Rules:
        - Arrival maneuvers (DEORBIT, LANDING, DOCK, INSERTION): use destination
        - Departure maneuvers (LAUNCH, UNDOCK): use origin/current
        - Transfer maneuvers: use origin for departure calculations
        """
        from mysite.universe.models.celestial import Planet, Moon, PhysicalBody
        from mysite.universe.models.station import Station
        
        maneuver = event.maneuver.value.upper() if hasattr(event.maneuver, 'value') else str(event.maneuver).upper()
        
        # Determine which location to use
        if maneuver in ["DEORBIT", "LANDING", "DOCK", "INSERTION"]:
            target_location = event.next or event.destination
        else:
            target_location = event.current or event.origin
        
        if not target_location:
            return None
        
        concrete = target_location.get_concrete_instance()
        
        # If it's already a planet/moon, return it
        if isinstance(concrete, (Planet, Moon)):
            return concrete
        
        # If it's a station, get what it orbits
        if isinstance(concrete, Station) and concrete.orbits:
            parent = concrete.orbits.get_concrete_instance()
            if isinstance(parent, (Planet, Moon)):
                return parent
        
        return None
    
    def _extract_body_params(self, body) -> dict:
        """Extract physical parameters from a celestial body."""
        if body is None:
            return {}
        
        params = {
            "radius_km": getattr(body, 'radius_km', 6371),
            "mass_kg": getattr(body, 'mass_kg', 5.97e24),
            "gravity_gees": getattr(body, 'surface_gravity_gees', None),
            "atmospheric_height_km": getattr(body, 'atmospheric_height_km', 100),
            "rotation_period_seconds": getattr(body, 'rotation_period_seconds', 86400),
            "has_atmosphere": getattr(body, 'atmospheric_height_km', 0) > 0,
        }
        
        # Calculate gravity from mass and radius if not provided
        if params["gravity_gees"] is None and params["mass_kg"] and params["radius_km"]:
            G = 6.67430e-11
            EARTH_G = 9.80665
            surface_g = (G * params["mass_kg"]) / ((params["radius_km"] * 1000) ** 2)
            params["gravity_gees"] = surface_g / EARTH_G
        
        return params
    
    def _build_physics_nav_context(self, event: NavigationEvent, body) -> dict:
        """Build navigation context for physics calculations."""
        from mysite.universe.models.celestial import Planet
        
        context = {
            "altitude_km": 300,  # Default LEO altitude
            "entry_interface_km": 100,  # Default entry interface
            "orbit_altitude_km": 300,
        }
        
        # For sublight/transfer maneuvers, calculate distance
        maneuver = event.maneuver.value.upper() if hasattr(event.maneuver, 'value') else str(event.maneuver).upper()
        
        if maneuver in ["SUBLIGHT", "TRANSFER"]:
            # Try to get orbital distances for origin and destination
            origin_au = None
            dest_au = None
            
            if event.origin:
                origin_concrete = event.origin.get_concrete_instance()
                if isinstance(origin_concrete, Planet):
                    origin_au = getattr(origin_concrete, 'orbital_distance_au', None)
            
            if event.destination:
                dest_concrete = event.destination.get_concrete_instance()
                if isinstance(dest_concrete, Planet):
                    dest_au = getattr(dest_concrete, 'orbital_distance_au', None)
            
            if origin_au and dest_au:
                context["distance_au"] = abs(dest_au - origin_au)
                context["origin_orbit_au"] = origin_au
                context["dest_orbit_au"] = dest_au
            else:
                # Default to Mars-Earth distance (~0.5 AU average)
                context["distance_au"] = 0.5
        
        # Get target altitude if body provides it
        if body and hasattr(body, 'get_leo_band_altitude_km'):
            try:
                context["altitude_km"] = body.get_leo_band_altitude_km()
            except:
                pass
        
        return context