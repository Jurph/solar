from mysite.universe.services.dictionary import DictionaryService
from typing import Optional, List
import json

# Import our navigation models
from mysite.universe.models.navigation import NavigationEvent, ManeuverType
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.ship import Ship
from mysite.universe.models.actor import Pilot, Controller, Actor
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.llm_service import LLMService
from mysite.universe.services.llm_service import LLMJSONService

route_service = RouteService()
dictionary_service = DictionaryService()

class ScriptService:
    """
    Service for converting high-level NavigationEvents into DialogueEvents,
    and for processing DialogueEvents to generate appropriate replies.
    
    It provides:
    • parse_navigation_event(navigation_event, ship)
    Converts a NavigationEvent (e.g. a SUBLIGHT maneuver) into an initial DialogueEvent
    from the ship's pilot. The event text is constructed from various mission details.


    • parse_dialogue_event(pilot_dialogue)
    Given a DialogueEvent (from pilot) that expects a reply, this method generates a standard
    reply from Control.
    """

    _instance = None
    
    @classmethod
    def get_instance(cls, llm=None):
        """Get or create the ScriptService instance with optional LLM configuration."""
        if cls._instance is None:
            if llm is None:
                from mysite.universe.services.llm_service import LLMService
                llm = LLMService(quiet_mode=True)
            cls._instance = cls(llm)
        return cls._instance

    def __init__(self, llm):
        self.llm = llm
        self.pilot_call_sign = None

    def parse_navigation_event(self, nav_event: NavigationEvent, ship: Ship) -> DialogueEvent:
        """
        Convert a NavigationEvent (e.g. a SUBLIGHT maneuver) into an initial DialogueEvent
        representing the pilot's broadcast.
        """
        if not ship or not hasattr(ship, 'pilot') or not ship.pilot:
            raise ValueError("Ship must have a pilot to generate dialogue")

        pilot = ship.pilot
        ship_call_sign = ship.name.upper()

        # Determine controller name and expected reply actor
        if hasattr(nav_event, 'controller') and nav_event.controller:
            if hasattr(nav_event.controller, 'role') and nav_event.controller.role == 'CONTROLLER':
                controller_name = nav_event.controller.name
                expected_reply_actor = nav_event.controller
            else:
                controller_name = getattr(nav_event.controller, "name", None)
                if not controller_name and hasattr(nav_event, 'destination') and nav_event.destination:
                    controller_name = f"{nav_event.destination.name} Control"
                else:
                    controller_name = "Control"
                from mysite.universe.models.actor import Controller
                expected_reply_actor = Controller.objects.filter(name=controller_name).first()
                if not expected_reply_actor:
                    expected_reply_actor = Controller.create(name=controller_name, location=nav_event.controller)
        else:
            controller_name = "Control"
            expected_reply_actor = None

        def get_location_name(location) -> str:
            return location.name if location and hasattr(location, 'name') else "unknown location"

        def get_next_name(nav_event) -> str:
            if hasattr(nav_event, 'next') and nav_event.next:
                return get_location_name(nav_event.next)
            return get_location_name(nav_event.destination)

        # Generate the line first based on maneuver type
        if isinstance(self.llm, LLMJSONService):
            # Get the exemplar line from our pre-written dialogue
            exemplar = ""
            if nav_event.maneuver == ManeuverType.LAUNCH:
                exemplar = f"{controller_name}, this is {ship_call_sign}, requesting clearance for takeoff from {get_location_name(nav_event.origin)}."
            elif nav_event.maneuver == ManeuverType.DIRECT_ASCENT:
                exemplar = f"{controller_name}, this is {ship_call_sign}, requesting a direct ascent burn for {get_location_name(nav_event.destination)}."
            elif nav_event.maneuver == ManeuverType.CIRCULARIZE:
                exemplar = f"{controller_name}, this is {ship_call_sign}, requesting permission to circularize around {get_location_name(nav_event.current)}."
            elif nav_event.maneuver == ManeuverType.PLANE_CHANGE:
                exemplar = f"{controller_name}, this is {ship_call_sign}, we're ready for our plane change maneuver."
            elif nav_event.maneuver == ManeuverType.DEORBIT:
                exemplar = f"{controller_name}, this is {ship_call_sign}, we're ready to break orbit and head in to {get_location_name(nav_event.destination)}. Can you give us a vector?"
            elif nav_event.maneuver == ManeuverType.LANDING:
                exemplar = f"{controller_name}, this is {ship_call_sign}, on final for our landing at {get_location_name(nav_event.destination)}. Please advise."
            elif nav_event.maneuver == ManeuverType.INSERTION:
                exemplar = f"{controller_name}, this is {ship_call_sign}, we're ready for our insertion burn. Can you give us a vector for {get_location_name(nav_event.current)}?"
            elif nav_event.maneuver == ManeuverType.DOCK:
                exemplar = f"{controller_name}, this is {ship_call_sign}, requesting docking clearance for {get_location_name(nav_event.destination)}."
            elif nav_event.maneuver == ManeuverType.UNDOCK:
                exemplar = f"{controller_name}, this is {ship_call_sign}, ready for departure. Request permission to undock from {get_location_name(nav_event.origin)}."
            elif nav_event.maneuver == ManeuverType.SUBLIGHT:
                if controller_name == get_next_name(nav_event):
                    exemplar = f"{controller_name}, this is {ship_call_sign}, we're inbound from {get_location_name(nav_event.origin)}, request a vector for {get_location_name(nav_event.destination)}."
                elif controller_name == get_location_name(nav_event.current):
                    exemplar = f"{controller_name}, this is {ship_call_sign}, heading for {get_location_name(nav_event.destination)} and ready for our outbound sublight burn."
                else:
                    exemplar = f"{controller_name}, this is {ship_call_sign}, requesting sublight burn on our way to {get_location_name(nav_event.destination)}."
            elif nav_event.maneuver == ManeuverType.HYPERSPACE:
                exemplar = f"{controller_name}, this is {ship_call_sign}. Gravity well shows clear; requesting hyperspace jump to {get_next_name(nav_event)}."
            else:
                exemplar = f"{controller_name}, this is {ship_call_sign}, requesting clearance for {nav_event.maneuver.value} maneuver."

            # For JSON mode, let the LLM generate the line with exemplar
            context = {
                "maneuver_type": nav_event.maneuver.value,
                "current_location": get_location_name(nav_event.current),
                "destination": get_location_name(nav_event.destination),
                "cargo": ship.cargo,
                "previous_exchanges": []
            }
            
            dialogue_context = {
                "role": pilot.role.value,
                "speaker_callsign": ship_call_sign,
                "recipient_callsign": controller_name,
                "format": "INITIAL_CONTACT",
                "message": exemplar,
                "requires_readback": False
            }

            line = self.llm.get_actor_text(
                line=exemplar,
                actor=pilot,
                context=[],  # No previous context for initial contact
                temperature=0.2,  # Lower temperature for more consistent output
                navigation_context=context
            )
            # Extract message from JSON response
            if isinstance(line, str) and line.strip().startswith('{'):
                try:
                    json_response = json.loads(line)
                    line = json_response.get("message", line)
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON response from LLM: {line}")
        else:
            # Original text-based format with specific lines per maneuver
            if nav_event.maneuver == ManeuverType.LAUNCH:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, requesting clearance for takeoff from {get_location_name(nav_event.origin)}."
                )
            elif nav_event.maneuver == ManeuverType.DIRECT_ASCENT:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, requesting a direct ascent burn for {get_location_name(nav_event.destination)}."
                )
            elif nav_event.maneuver == ManeuverType.CIRCULARIZE:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, requesting permission to circularize around {get_location_name(nav_event.current)}."
                )
            elif nav_event.maneuver == ManeuverType.PLANE_CHANGE:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, we're ready for our plane change maneuver."
                )
            elif nav_event.maneuver == ManeuverType.DEORBIT:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, we're ready to break orbit and head in to {get_location_name(nav_event.destination)}. Can you give us a vector?"
                )
            elif nav_event.maneuver == ManeuverType.LANDING:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, on final for our landing at {get_location_name(nav_event.destination)}. Please advise."
                )
            elif nav_event.maneuver == ManeuverType.INSERTION:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, we're ready for our insertion burn. Can you give us a vector for {get_location_name(nav_event.current)}?"
                )
            elif nav_event.maneuver == ManeuverType.DOCK:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, requesting docking clearance for {get_location_name(nav_event.destination)}."
                )
            elif nav_event.maneuver == ManeuverType.UNDOCK:
                line = (
                    f"{controller_name}, this is {ship_call_sign}, ready for departure. Request permission to undock from {get_location_name(nav_event.origin)}."
                )
            elif nav_event.maneuver == ManeuverType.SUBLIGHT:
                if controller_name == get_next_name(nav_event):
                    line = (
                        f"{controller_name}, this is {ship_call_sign}, we're inbound from {get_location_name(nav_event.origin)}, request a vector for {get_location_name(nav_event.destination)}."
                    )
                elif controller_name == get_location_name(nav_event.current):
                    line = (
                        f"{controller_name}, this is {ship_call_sign}, heading for {get_location_name(nav_event.destination)} and ready for our outbound sublight burn."
                    )
                else:
                    line = (
                        f"{controller_name}, this is {ship_call_sign}, requesting sublight burn on our way to {get_location_name(nav_event.destination)}."
                    )
            elif nav_event.maneuver == ManeuverType.HYPERSPACE:
                line = (
                    f"{controller_name}, this is {ship_call_sign}. Gravity well shows clear; requesting hyperspace jump to {get_next_name(nav_event)}."
                )
            else:
                raise NotImplementedError("Navigation parsing for this maneuver type is not implemented.")

        # Build metadata: preserve existing fields and add rich context for the LLM
        metadata = {
            "control_name": controller_name,
            "ship_name": ship_call_sign,
            "pilot_name": pilot.name,
            "maneuver": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver,
            "llm_system_prompt": pilot.get_identity_prompt(),
            "llm_user_prompt": {
                "role": "PILOT",
                "context": {
                    "maneuver_type": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver,
                    "current_location": get_location_name(nav_event.current),
                    "destination": get_location_name(nav_event.destination),
                    "previous_exchanges": []
                },
                "expected_format": "INITIAL_CONTACT"
            } if isinstance(self.llm, LLMJSONService) else {
                "Current situation": f"{ship_call_sign} is performing a {nav_event.maneuver.value} maneuver "
                f"from {get_location_name(nav_event.origin)} to {get_location_name(nav_event.destination)}. "
                f"Currently at {get_location_name(nav_event.current)}, next stop is {get_next_name(nav_event)}.\n\n"
                f"<YOUR LINE> should be something like: '{line}'\n"
                "Given the situation, say <YOUR LINE> in character, incorporating specific details about your location and maneuver."
            },
            "context": {
                "mission": {
                    "origin": get_location_name(nav_event.origin),
                    "destination": get_location_name(nav_event.destination),
                    "controller": controller_name,
                },
                "current_situation": {
                    "ship": ship_call_sign,
                    "location": get_location_name(nav_event.current),
                    "next_waypoint": get_location_name(nav_event.next),
                    "maneuver": nav_event.maneuver.value,
                }
            }
        }

        # Create the dialogue event
        return DialogueEvent(
            timestamp=nav_event.duration,
            actor=pilot,
            text=line,
            expect_reply=True,
            expected_reply_actor=expected_reply_actor,
            duration=RouteService().get_event_duration(nav_event),
            event_type="dialogue",
            metadata=metadata
        )
            
    
    def parse_dialogue_event(self, event: DialogueEvent) -> Optional[DialogueEvent]:
        """
        Process a dialogue event and generate a response if needed.
        
        Args:
            event: The dialogue event to process
            
        Returns:
            A new dialogue event containing the response, or None if no response needed
        """
        if not event.expect_reply:
            return None
            
        # Get the actor who should respond
        reply_actor_name = event.metadata.get("reply_actor_name")
        if not reply_actor_name:
            return None
            
        reply_actor = None
        try:
            # Try to get the actor by name
            if "Control" in reply_actor_name:
                reply_actor = Controller.objects.get(name=reply_actor_name)
            elif "Satellite" in reply_actor_name:
                reply_actor = Satellite.objects.get(name=reply_actor_name)
            else:
                reply_actor = Pilot.objects.get(name=reply_actor_name)
        except (Controller.DoesNotExist, Pilot.DoesNotExist, Satellite.DoesNotExist):
            print(f"Warning: Could not find actor {reply_actor_name}")
            return None
            
        # Build context from previous messages
        context = []
        if event.metadata.get("previous_messages"):
            context.extend(event.metadata["previous_messages"])
        context.append(f"{event.actor.name}: {event.text}")
        
        # Get navigation context if available
        nav_ctx = {
            "maneuver": event.metadata.get("maneuver"),
            "current_location": event.metadata.get("current_location"),
            "destination": event.metadata.get("destination"),
            "recipient": event.actor.name  # Add the original speaker as recipient
        }
        
        # Generate response using LLM
        try:
            llm_text = self.llm.get_actor_text(
                line=self.build_controller_examples(event.actor.name, reply_actor.name),
                actor=reply_actor,
                context={
                    "role": reply_actor.role,
                    "context": {
                        "maneuver_type": nav_ctx.get("maneuver"),
                        "current_location": nav_ctx.get("current_location"),
                        "destination": nav_ctx.get("destination"),
                        "previous_exchanges": context
                    },
                    "expected_format": event.metadata.get("expected_format", "RESPONSE")
                },
                navigation_context=nav_ctx
            )
            
            # Handle JSON responses
            message_text = llm_text
            if isinstance(llm_text, str) and llm_text.strip().startswith('{'):
                try:
                    json_response = json.loads(llm_text)
                    message_text = json_response.get("message", llm_text)
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON response from LLM: {llm_text}")
                    message_text = llm_text
            
            # Create response event
            response_event = DialogueEvent(
                timestamp=event.timestamp + event.duration + 0.5,
                actor=reply_actor,
                text=message_text,
                expect_reply=False,  # Default to no reply expected
                duration=2.0,
                event_type="dialogue",
                metadata={
                    "previous_messages": context,
                    "llm_system_prompt": event.metadata.get("llm_system_prompt"),
                    "llm_user_prompt": event.metadata.get("llm_user_prompt"),
                    **nav_ctx
                }
            )
            
            return response_event
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return None

    def parse_navigation_events(self, nav_events, ship):
        """Convert a list of navigation events into dialogue events with updated sequential timestamps.

        Each dialogue event's timestamp is set to the accumulated duration from previous events.
        Uses dataclasses.replace() since DialogueEvent is frozen.
        """
        from dataclasses import replace
        script_events = []
        current_timestamp = 0.0
        for nav_event in nav_events:
            dialogue_event = self.parse_navigation_event(nav_event, ship)
            dialogue_event = replace(dialogue_event, timestamp=current_timestamp)
            current_timestamp += dialogue_event.duration
            script_events.append(dialogue_event)
        return script_events

    def build_situation_prompt(self, nav_event: NavigationEvent, ship: Ship) -> str:
        return f"""Current Situation:
- Ship {ship.name.upper()} is on a journey from {nav_event.origin} to {nav_event.destination}
- Currently at {nav_event.current}, next stop is {nav_event.next}
- Performing a {nav_event.maneuver.value} maneuver
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

