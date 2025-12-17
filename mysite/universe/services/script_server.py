from mysite.universe.services.dictionary import DictionaryService
from typing import List, Dict, Any, Tuple

# Import our navigation models
from mysite.universe.models.navigation import NavigationEvent
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.ship import Ship
from mysite.universe.models.actor import Controller
from mysite.universe.services.route_server import RouteService
from mysite.universe.schemas.dialogue_schema import DialogueMessage, Role
from mysite.universe.services.dialogue_server import DialogueService

route_service = RouteService()
dictionary_service = DictionaryService()

class ScriptService:
    """
    Service for converting high-level NavigationEvents into DialogueEvents,
    and for processing DialogueEvents to generate appropriate replies.
    
    It provides:
    • parse_navigation_event(navigation_event, ship)
    Converts a NavigationEvent (e.g. a SUBLIGHT maneuver) into a complete dialogue chain
    (List[DialogueEvent]) using the DialogueService. Chains are generated upfront rather
    than one event at a time.
    """

    _instance = None
    
    @classmethod
    def get_instance(cls, llm=None):
        """Get or create the ScriptService instance with optional LLM configuration."""
        if cls._instance is None:
            if llm is None:
                # Use unified LLMService for structured JSON dialogue generation
                from mysite.universe.services.llm_service import LLMService
                llm = LLMService(quiet_mode=True)
            cls._instance = cls(llm)
        return cls._instance

    def __init__(self, llm):
        self.llm = llm
        self.pilot_call_sign = None
        # Initialize DialogueService for chain generation
        self.dialogue_service = DialogueService(llm)

    def parse_navigation_event(self, nav_event: NavigationEvent, ship: Ship) -> List[DialogueEvent]:
        """
        Convert a NavigationEvent into a complete dialogue chain.
        
        Uses DialogueService to generate a complete dialogue sequence (request,
        response, acknowledgment, etc.) upfront rather than one event at a time.
        
        Args:
            nav_event: NavigationEvent to convert
            ship: Ship performing the maneuver
            
        Returns:
            List of DialogueEvent instances forming a complete dialogue chain
            
        Raises:
            ValueError: If ship has no pilot or controller cannot be determined
        """
        if not ship or not hasattr(ship, 'pilot') or not ship.pilot:
            raise ValueError("Ship must have a pilot to generate dialogue")
        
        pilot = ship.pilot
        controller = self._get_controller(nav_event)
        
        # Build navigation context
        nav_context = self._build_nav_context(nav_event, ship)
        
        # Generate complete dialogue chain
        messages = self.dialogue_service.generate_chain_from_nav_event(
            nav_event=nav_event,
            pilot=pilot,
            controller=controller,
            nav_context=nav_context,
            temperature=getattr(self.llm, 'temperature', None)
        )
        
        # Convert messages to events with sequential timestamps
        events = self._convert_messages_to_events(
            messages_with_timing=messages,
            nav_event=nav_event,
            ship=ship
        )
        
        return events
    
    def generate_comms_check_chain(
        self,
        pilot,
        satellite,
        ship: Ship,
        base_timestamp: float = 0.0,
    ) -> List[DialogueEvent]:
        """
        Generate a dialogue chain for a comms check between pilot and satellite.
        
        Uses the particle system to generate:
        1. CommsCheckRequest (pilot → satellite)
        2. SatelliteResponse (satellite → pilot, pre-programmed message)
        
        Args:
            pilot: Pilot actor
            satellite: Satellite actor
            ship: Ship the pilot is operating
            base_timestamp: Base timestamp for the chain (default: 0.0)
            
        Returns:
            List of DialogueEvent instances for the comms check chain
        """
        from mysite.universe.schemas.dialogue_schema import Role
        
        # Build nav context for comms check
        nav_context = {
            "ship_name": ship.name.upper() if ship else "UNKNOWN",
            "pilot_name": pilot.name if pilot else None,
            "recipient": satellite.name.upper(),
        }
        
        # Create initial comms check request particle
        initial_particle = self.dialogue_service.particle_factory.create_particle(
            particle_type="comms_check",
            actor=pilot,
            recipient=satellite.name.upper(),
            nav_context=nav_context,
        )
        
        # Generate chain iteratively (will generate request → satellite response)
        messages = self.dialogue_service.generate_chain_iteratively(
            initial_particle=initial_particle,
            pilot=pilot,
            controller=None,  # Not needed for comms checks
            nav_context=nav_context,
            temperature=getattr(self.llm, 'temperature', None),
            satellite=satellite,
        )
        
        # Convert messages to events
        events: List[DialogueEvent] = []
        for i, (msg, relative_time_offset) in enumerate(messages):
            # Determine actor based on role
            if msg.role == Role.PILOT:
                actor = pilot
                expected_reply_actor = satellite
            elif msg.role == Role.SATELLITE:
                actor = satellite
                expected_reply_actor = pilot
            else:
                # Fallback
                actor = pilot
                expected_reply_actor = satellite
            
            # Build metadata
            metadata = {
                "type": "comms_check" if i == 0 else "satellite_response",
                "ship_name": ship.name.upper() if ship else "UNKNOWN",
                "pilot_name": pilot.name if pilot else None,
                "satellite_name": satellite.name,
                "dialogue_message": msg.model_dump(),
            }
            
            # Create DialogueEvent
            event = DialogueEvent(
                timestamp=base_timestamp + relative_time_offset,
                actor=actor,
                text=msg.message,
                expect_reply=(i == 0),  # Only first event expects reply
                duration=2.0,
                event_type="dialogue",
                metadata=metadata,
                expected_reply_actor=expected_reply_actor if i == 0 else None,
            )
            events.append(event)
        
        return events
    
    def _build_nav_context(self, nav_event: NavigationEvent, ship: Ship) -> Dict[str, Any]:
        """
        Build navigation context dictionary from NavigationEvent and Ship.
        
        Extracts all relevant context needed for dialogue generation:
        - Maneuver type, locations, controller info
        - Ship and pilot information
        - Mission details (origin, destination)
        
        Args:
            nav_event: NavigationEvent to extract context from
            ship: Ship performing the maneuver
            
        Returns:
            Dictionary with navigation context for dialogue generation
        """
        def get_location_name(location) -> str:
            if location and hasattr(location, 'name') and location.name:
                return location.name
            raise ValueError(f"Location object missing name attribute: {location}")
        
        pilot = ship.pilot if ship and hasattr(ship, 'pilot') and ship.pilot else None
        ship_call_sign = ship.name.upper() if ship else "UNKNOWN"
        
        # Get controller name
        controller_name = None
        if hasattr(nav_event, 'controller') and nav_event.controller:
            from mysite.universe.models.actor import Controller
            if isinstance(nav_event.controller, Controller):
                controller_name = nav_event.controller.name
            elif hasattr(nav_event.controller, 'name'):
                controller_name = nav_event.controller.name
        
        if not controller_name and hasattr(nav_event, 'destination') and nav_event.destination:
            controller_name = f"{nav_event.destination.name} Control"
        
        nav_context = {
            "maneuver_type": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else str(nav_event.maneuver),
            "maneuver": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else str(nav_event.maneuver),
            "current_location": get_location_name(nav_event.current),
            "destination": get_location_name(nav_event.destination),
            "origin": get_location_name(nav_event.origin) if hasattr(nav_event, 'origin') and nav_event.origin else None,
            "ship_name": ship_call_sign,
            "pilot_name": pilot.name if pilot else None,
            "control_name": controller_name,
            "recipient": controller_name,
        }
        
        # Remove None values
        return {k: v for k, v in nav_context.items() if v is not None}
    
    def _get_controller(self, nav_event: NavigationEvent) -> Controller:
        """
        Extract or create controller from NavigationEvent.
        
        Uses the controller assigned by RouteService._enhance_with_controllers() if present,
        otherwise determines controller based on maneuver type and location context.
        
        Rules:
        - Arrival maneuvers (DEORBIT, LANDING, DOCK, INSERTION): use destination's effective controller
        - Departure maneuvers (LAUNCH, UNDOCK): use origin's effective controller
        - Transfer maneuvers (SUBLIGHT, TRANSFER, PLANE_CHANGE, CIRCULARIZE): use current location's effective controller
        - Other maneuvers: use current location's effective controller as fallback
        
        Args:
            nav_event: NavigationEvent to extract controller from
            
        Returns:
            Controller actor instance
            
        Raises:
            ValueError: If controller cannot be determined
        """
        from mysite.universe.models.actor import Controller
        from mysite.universe.models.navigation import ManeuverType
        
        # First, check if controller is already assigned by RouteService
        if hasattr(nav_event, 'controller') and nav_event.controller:
            if isinstance(nav_event.controller, Controller):
                return nav_event.controller
            elif hasattr(nav_event.controller, 'name'):
                # It's a Location (station), get or create the Controller actor
                controller = Controller.objects.filter(name=nav_event.controller.name).first()
                if not controller:
                    controller = Controller.create(name=nav_event.controller.name, location=nav_event.controller)
                return controller
        
        # Determine controller based on maneuver type
        route_service = RouteService()
        target_location = None
        
        # Arrival maneuvers: use destination
        if nav_event.maneuver in (ManeuverType.DEORBIT, ManeuverType.LANDING, ManeuverType.DOCK, ManeuverType.INSERTION):
            if hasattr(nav_event, 'destination') and nav_event.destination:
                target_location = nav_event.destination
        # Departure maneuvers: use origin
        elif nav_event.maneuver in (ManeuverType.LAUNCH, ManeuverType.UNDOCK):
            if hasattr(nav_event, 'origin') and nav_event.origin:
                target_location = nav_event.origin
        # Transfer maneuvers: use current location
        elif nav_event.maneuver in (ManeuverType.SUBLIGHT, ManeuverType.TRANSFER, ManeuverType.PLANE_CHANGE, ManeuverType.CIRCULARIZE):
            if hasattr(nav_event, 'current') and nav_event.current:
                target_location = nav_event.current
        # Fallback: use current location if available, otherwise destination
        else:
            if hasattr(nav_event, 'current') and nav_event.current:
                target_location = nav_event.current
            elif hasattr(nav_event, 'destination') and nav_event.destination:
                target_location = nav_event.destination
        
        if not target_location:
            raise ValueError(
                f"Cannot determine controller for navigation event. "
                f"Maneuver: {nav_event.maneuver}, "
                f"Origin: {getattr(nav_event, 'origin', None)}, "
                f"Current: {getattr(nav_event, 'current', None)}, "
                f"Destination: {getattr(nav_event, 'destination', None)}"
            )
        
        # Get the effective controller for the target location
        effective_controller = route_service.effective_controller(target_location)
        
        # If effective_controller is a Controller, return it
        if isinstance(effective_controller, Controller):
            return effective_controller
        
        # If effective_controller is a Location (station), get or create the Controller actor
        if hasattr(effective_controller, 'name'):
            controller = Controller.objects.filter(name=effective_controller.name).first()
            if not controller:
                controller = Controller.create(name=effective_controller.name, location=effective_controller)
            return controller
        
        # Fallback: create a controller with the location's name
        controller_name = f"{target_location.name} Control"
        controller = Controller.objects.filter(name=controller_name).first()
        if not controller:
            controller = Controller.create(name=controller_name, location=target_location)
        return controller
    
    def _convert_messages_to_events(
        self,
        messages_with_timing: List[Tuple[DialogueMessage, float]],
        nav_event: NavigationEvent,
        ship: Ship,
    ) -> List[DialogueEvent]:
        """
        Convert (DialogueMessage, time_offset) tuples to DialogueEvent list with relative timestamps.
        
        Sets up proper timing, actors, and metadata for each event in the chain.
        Timestamps are relative to chain start (0.0) and will be mapped to absolute timestamps
        by parse_navigation_events().
        
        Args:
            messages_with_timing: List of (DialogueMessage, cumulative_time_offset) tuples.
                Times are relative to chain start (0.0).
            nav_event: Original NavigationEvent for context
            ship: Ship performing the maneuver
            
        Returns:
            List of DialogueEvent instances with relative timestamps (will be mapped to absolute by caller)
        """
        events: List[DialogueEvent] = []
        
        pilot = ship.pilot if ship and hasattr(ship, 'pilot') and ship.pilot else None
        controller = self._get_controller(nav_event)
        
        def get_location_name(location) -> str:
            if location and hasattr(location, 'name') and location.name:
                return location.name
            return "Unknown"
        
        # Default duration (TODO: get actual particle duration)
        default_duration = 2.0
        
        for i, (msg, relative_time_offset) in enumerate(messages_with_timing):
            # Determine actor based on role
            if msg.role == Role.PILOT:
                actor = pilot
                expected_reply_actor = controller
            elif msg.role == Role.CONTROLLER:
                actor = controller
                expected_reply_actor = pilot
            else:
                # Fallback
                actor = pilot
                expected_reply_actor = controller
            
            if not actor:
                raise ValueError(f"Cannot determine actor for message {i}: {msg.role}")
            
            # Build metadata
            metadata = {
                "control_name": controller.name,
                "ship_name": ship.name.upper() if ship else "UNKNOWN",
                "pilot_name": pilot.name if pilot else None,
                "maneuver": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else str(nav_event.maneuver),
                "context": {
                    "mission": {
                        "origin": get_location_name(nav_event.origin) if hasattr(nav_event, 'origin') else None,
                        "destination": get_location_name(nav_event.destination),
                        "controller": controller.name,
                    },
                    "current_situation": {
                        "ship": ship.name.upper() if ship else "UNKNOWN",
                        "location": get_location_name(nav_event.current),
                        "next_waypoint": get_location_name(nav_event.next) if hasattr(nav_event, 'next') else None,
                        "maneuver": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else str(nav_event.maneuver),
                    }
                },
                "dialogue_message": msg.model_dump(),
            }
            
            # Remove None values from metadata
            metadata = {k: v for k, v in metadata.items() if v is not None}
            if "context" in metadata:
                metadata["context"] = {
                    k: v for k, v in metadata["context"].items()
                    if v is not None and (not isinstance(v, dict) or any(v.values()))
                }
            
            # Determine if this event expects a reply
            # Last event in chain doesn't expect reply, others do
            expect_reply = (i < len(messages_with_timing) - 1)
            
            # Use relative time offset directly (will be mapped to absolute timestamp by parse_navigation_events)
            event = DialogueEvent(
                timestamp=relative_time_offset,
                actor=actor,
                text=msg.message,  # Natural language message text
                expect_reply=expect_reply,
                expected_reply_actor=expected_reply_actor if expect_reply else None,
                duration=default_duration,  # TODO: Get actual particle duration
                event_type="dialogue",
                metadata=metadata
            )
            
            events.append(event)
        
        return events
    
    def parse_navigation_events(self, nav_events: List[NavigationEvent], ship: Ship) -> List[DialogueEvent]:
        """
        Convert a list of navigation events into dialogue events with sequential timestamps.
        
        Each navigation event generates a complete dialogue chain. Timestamps are set
        sequentially, preserving relative timing within each chain and accumulating
        across chains.
        
        Args:
            nav_events: List of NavigationEvent instances
            ship: Ship performing the maneuvers
            
        Returns:
            List of DialogueEvent instances with sequential absolute timestamps
        """
        from dataclasses import replace
        script_events: List[DialogueEvent] = []
        chain_start_timestamp = 0.0
        
        for nav_event in nav_events:
            # Generate complete dialogue chain for this navigation event
            # Events in chain have relative timestamps (relative to chain start at 0.0)
            dialogue_chain = self.parse_navigation_event(nav_event, ship)
            
            # Map relative timestamps to absolute timestamps, preserving chain's internal timing
            for event in dialogue_chain:
                # event.timestamp is relative offset within chain, map to absolute
                absolute_timestamp = chain_start_timestamp + event.timestamp
                updated_event = replace(event, timestamp=absolute_timestamp)
                script_events.append(updated_event)
            
            # Advance chain start timestamp: use the last event's timestamp + duration
            # This preserves the spacing between chains
            if dialogue_chain:
                last_event = dialogue_chain[-1]
                chain_start_timestamp = chain_start_timestamp + last_event.timestamp + last_event.duration
            else:
                # If chain is empty, advance by a default duration to prevent overlap
                chain_start_timestamp += 2.0
        
        return script_events

