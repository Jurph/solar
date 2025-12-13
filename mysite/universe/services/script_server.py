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
        Convert (DialogueMessage, time_offset) tuples to DialogueEvent list with timestamps.
        
        Sets up proper timing, actors, and metadata for each event in the chain.
        Times are relative to chain start (0.0), then mapped to absolute timestamps
        starting at nav_event.duration.
        
        Args:
            messages_with_timing: List of (DialogueMessage, cumulative_time_offset) tuples.
                Times are relative to chain start (0.0).
            nav_event: Original NavigationEvent for context
            ship: Ship performing the maneuver
            
        Returns:
            List of DialogueEvent instances with absolute timestamps
        """
        events: List[DialogueEvent] = []
        # Base timestamp: navigation event duration (when nav event completes)
        base_timestamp = nav_event.duration if hasattr(nav_event, 'duration') else 0.0
        
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
            
            # Calculate absolute timestamp: base (nav event completion) + relative offset
            absolute_timestamp = base_timestamp + relative_time_offset
            
            event = DialogueEvent(
                timestamp=absolute_timestamp,
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
        Convert a list of navigation events into dialogue events with updated sequential timestamps.
        
        Each navigation event generates a complete dialogue chain. Timestamps are set
        sequentially, accumulating duration from previous events.
        
        Args:
            nav_events: List of NavigationEvent instances
            ship: Ship performing the maneuvers
            
        Returns:
            List of DialogueEvent instances with sequential timestamps
        """
        from dataclasses import replace
        script_events: List[DialogueEvent] = []
        current_timestamp = 0.0
        
        for nav_event in nav_events:
            # Generate complete dialogue chain for this navigation event
            dialogue_chain = self.parse_navigation_event(nav_event, ship)
            
            # Update timestamps to be sequential
            for event in dialogue_chain:
                updated_event = replace(event, timestamp=current_timestamp)
                script_events.append(updated_event)
                current_timestamp += updated_event.duration
        
        return script_events

    def build_situation_prompt(self, nav_event: NavigationEvent, ship: Ship) -> str:
        return f"""Current Situation:
- Ship {ship.name.upper()} is on a journey from {nav_event.origin} to {nav_event.destination}
- Currently at {nav_event.current}, next stop is {nav_event.next}
- Performing a {nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver} maneuver
- Under the direction of {nav_event.controller} 
"""

    def get_dialogue_context(self, dialogue: DialogueEvent) -> dict:
        """Assembles dialogue context from existing metadata and exchanges."""
        context = {
            "navigation": dialogue.metadata.get("context", {}),
            "recent_exchanges": dialogue.metadata.get("recent_exchanges", [])[-3:],  # Last 3 exchanges
            "current_maneuver": dialogue.metadata.get("maneuver"),
        }
        return context

    def format_context_for_llm(self, context: dict, dialogue: DialogueEvent) -> List[str]:
        """Formats context into a list of strings for the LLM."""
        messages = []
        
        # Add situation prompt if we have navigation context
        if nav_context := context["navigation"]:
            mission = nav_context.get("mission", {})
            situation = nav_context.get("current_situation", {})
            
            situation_text = f"""Current Situation:
- Ship {situation.get('ship', 'UNIDENTIFIED VESSEL').upper()} is on a journey from {mission.get('origin')} to {mission.get('destination')}
- Currently at {situation.get('location')}, next stop is {situation.get('next_waypoint')}
- Performing a {situation.get('maneuver')} maneuver
- Under the direction of {mission.get('controller')}
"""
            messages.append(situation_text)
        
        # Add recent exchanges in chronological order
        for exchange in context["recent_exchanges"]:
            messages.append(f"{exchange['speaker']}: {exchange['message']}")
        
        # Add the current message last
        messages.append(dialogue.text)
        
        return messages

    def build_controller_examples(self, ship_name: str, control_name: str) -> str:
        ship_name = ship_name.upper()
        control_name = control_name.upper()
        return f"""Examples of responding to a Pilot, using your identity as {control_name}:
Pilot: "{control_name}, this is {ship_name}, requesting clearance for launch."
{control_name}: "{ship_name}, {control_name}. Cleared for takeoff, heading 090."

Pilot: "{control_name}, this is {ship_name}, ready for insertion burn."
{control_name}: "{ship_name}, {control_name}. Confirmed for insertion burn whenever you're ready."

Remember: You are {control_name}. Always identify yourself when speaking. Never pretend to be the {ship_name}. 
All of your dialogue with {ship_name} should be in the format '{control_name}: "{ship_name}, {control_name}, <approval or instructions here>"'"""

    def build_pilot_examples(self, ship_name: str, control_name: str) -> str:
        ship_name = ship_name.upper()
        control_name = control_name.upper() 
        return f"""Examples of responding to a Controller, using your identity as {ship_name}:

{control_name}: "{ship_name}, {control_name}. Adjust course 45 degrees right."
{ship_name}: "{control_name}, this is {ship_name}. Coming right 45 degrees, confirmed."

{control_name}: "{ship_name}, {control_name}. You're cleared for landing."
{ship_name}: "{control_name}, this is {ship_name}. Beginning landing approach."

Remember: You are {ship_name}. Always identify yourself when speaking. Never pretend to be {control_name}.
All of your dialogue with {control_name} should be in the format '{ship_name}: "{control_name}, {ship_name}, <request or polite concurrence here>"'"""

