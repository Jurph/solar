from mysite.universe.services.dictionary import DictionaryService
import random
from typing import Optional, List

# Import our navigation models
from mysite.universe.models.navigation import NavigationEvent, ManeuverType
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.ship import Ship
from mysite.universe.models.actor import Pilot, Controller, Actor
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.llm_service import LLMService

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

        # Build metadata: note that we now include ship_name and pilot_name here uniformly.
        metadata = {
            "control_name": controller_name,
            "ship_name": ship.name,
            "pilot_name": pilot.name,
            "maneuver": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else nav_event.maneuver,
        }

        def get_location_name(location) -> str:
            return location.name if location and hasattr(location, 'name') else "unknown location"

        def get_next_name(nav_event) -> str:
            if hasattr(nav_event, 'next') and nav_event.next:
                return get_location_name(nav_event.next)
            return get_location_name(nav_event.destination)

        # Use ship_call_sign everywhere instead of any stored state.
        if nav_event.maneuver == ManeuverType.LAUNCH:
            text = (
                f"{controller_name}, this is {ship_call_sign}, requesting clearance for takeoff from {get_location_name(nav_event.origin)}."
            )
        elif nav_event.maneuver == ManeuverType.DIRECT_ASCENT:
            text = (
                f"{controller_name}, this is {ship_call_sign}, requesting a direct ascent burn for {get_location_name(nav_event.destination)}."
            )
        elif nav_event.maneuver == ManeuverType.CIRCULARIZE:
            text = (
                f"{controller_name}, this is {ship_call_sign}, requesting permission to circularize around {get_location_name(nav_event.current)}."
            )
        elif nav_event.maneuver == ManeuverType.PLANE_CHANGE:
            text = (
                f"{controller_name}, this is {ship_call_sign}, we're ready for our plane change maneuver."
            )
        elif nav_event.maneuver == ManeuverType.DEORBIT:
            text = (
                f"{controller_name}, this is {ship_call_sign}, we're ready to break orbit and head in to {get_location_name(nav_event.destination)}. Can you give us a vector?"
            )
        elif nav_event.maneuver == ManeuverType.LANDING:
            text = (
                f"{controller_name}, this is {ship_call_sign}, on final for our landing at {get_location_name(nav_event.destination)}. Please advise."
            )
        elif nav_event.maneuver == ManeuverType.INSERTION:
            text = (
                f"{controller_name}, this is {ship_call_sign}, we're ready for our insertion burn. Can you give us a vector for {get_location_name(nav_event.current)}?"
            )
        elif nav_event.maneuver == ManeuverType.DOCK:
            text = (
                f"{controller_name}, this is {ship_call_sign}, requesting docking clearance for {get_location_name(nav_event.destination)}."
            )
        elif nav_event.maneuver == ManeuverType.UNDOCK:
            text = (
                f"{controller_name}, this is {ship_call_sign}, ready for departure. Request permission to undock from {get_location_name(nav_event.origin)}."
            )
        elif nav_event.maneuver == ManeuverType.SUBLIGHT:
            if controller_name == get_next_name(nav_event):
                text = (
                    f"{controller_name}, this is {ship_call_sign}, we're inbound from {get_location_name(nav_event.origin)}, request a vector for {get_location_name(nav_event.destination)}."
                )
            elif controller_name == get_location_name(nav_event.current):
                text = (
                    f"{controller_name}, this is {ship_call_sign}, heading for {get_location_name(nav_event.destination)} and ready for our outbound sublight burn."
                )
            else:
                text = (
                    f"{controller_name}, this is {ship_call_sign}, requesting sublight burn on our way to {get_location_name(nav_event.destination)}."
                )
        elif nav_event.maneuver == ManeuverType.HYPERSPACE:
            text = (
                f"{controller_name}, this is {ship_call_sign}. Gravity well shows clear; requesting hyperspace jump to {get_next_name(nav_event)}."
            )
        else:
            raise NotImplementedError("Navigation parsing for this maneuver type is not implemented.")

        return DialogueEvent(
            timestamp=nav_event.duration,
            actor=pilot,
            text=text,
            expect_reply=True,
            expected_reply_actor=expected_reply_actor,
            duration=RouteService().get_event_duration(nav_event),
            event_type="dialogue",
            metadata=metadata
        )
            
    
    def parse_dialogue_event(self, dialogue: DialogueEvent) -> Optional[DialogueEvent]:
        if not dialogue.expect_reply:
            return None

        if getattr(dialogue.actor, 'role', None) == Actor.Role.PILOT:
            # Pilot -> Controller: Controller should reply, expecting acknowledgment
            control_name = dialogue.metadata.get("control_name", "CONTROL").upper()
            ship_name = dialogue.metadata.get("ship_name", "UNKNOWN SHIP").upper()

            control_actor = dialogue.expected_reply_actor
            if not control_actor:
                control_actor = Controller.objects.filter(name=control_name).first()
                if not control_actor:
                    control_actor = Controller.create(name=control_name)

            reply_text = f"{ship_name}, this is {control_name}."

            llm_text = self.llm.get_actor_text(
                line=reply_text,
                actor=control_actor,
                context=[dialogue.text]
            )

            metadata = dialogue.metadata.copy() if dialogue.metadata else {}
            metadata.update({
                'llm_system_prompt': control_actor.get_identity_prompt(),
                'llm_user_prompt': f"Last message: {dialogue.text}\nYour line should be something like: '{reply_text}'",
                'ship_name': ship_name,
                'control_name': control_name,
            })

            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,
                actor=control_actor,
                text=llm_text,
                expect_reply=True,  # Controller expects pilot to acknowledge
                duration=3.0,
                event_type="dialogue",
                metadata=metadata
            )

        elif getattr(dialogue.actor, 'role', None) == Actor.Role.CONTROLLER:
            # Controller -> Pilot: Pilot acknowledges, ending the exchange
            ship_name = dialogue.metadata.get("ship_name", "UNKNOWN SHIP").upper()
            
            from mysite.universe.models.ship import Ship
            ship = Ship.objects.filter(name=ship_name).first()
            if ship and ship.pilot:
                pilot_actor = ship.pilot
            else:
                pilot_actor = Pilot.create(name=ship_name)

            reply_text = f"{dialogue.actor.name}, this is {ship_name}."

            llm_text = self.llm.get_actor_text(
                line=reply_text,
                actor=pilot_actor,
                context=[dialogue.text]
            )

            metadata = dialogue.metadata.copy() if dialogue.metadata else {}
            metadata.update({
                'llm_system_prompt': pilot_actor.get_identity_prompt(),
                'llm_user_prompt': f"Last message: {dialogue.text}\nYour line should be something like: '{reply_text}'"
            })

            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,
                actor=pilot_actor,
                text=llm_text,
                expect_reply=False,  # Pilot acknowledgment ends the exchange
                duration=3.0,
                event_type="dialogue",
                metadata=metadata
            )

        else:
            # Fall back to a generic reply
            return DialogueEvent(
                timestamp=dialogue.timestamp + 5.0,
                actor=dialogue.actor,
                text="Did you say something?",
                expect_reply=False,
                duration=2.0,
                event_type="dialogue",
                metadata=dialogue.metadata
            )

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
        return f"""Examples using your identity as {control_name}:
Pilot: "{control_name}, this is {ship_name}, requesting clearance for launch."
{control_name}: "{ship_name}, {control_name}. Cleared for takeoff, heading 090."

Pilot: "{control_name}, this is {ship_name}, ready for insertion burn."
{control_name}: "{ship_name}, {control_name}. Confirmed for insertion burn whenever you're ready."

Remember: You are {control_name}. Always identify yourself when speaking. Never pretend to be the {ship_name}. 
All of your dialogue with {ship_name} should be in the format '{control_name}: "{ship_name}, {control_name}, <approval or instructions here>"'"""

    def build_pilot_examples(self, ship_name: str, control_name: str) -> str:
        ship_name = ship_name.upper()
        control_name = control_name.upper() 
        return f"""Examples using your identity as {ship_name}:

{control_name}: "{ship_name}, {control_name}. Adjust course 45 degrees right."
{ship_name}: "{control_name}, this is {ship_name}. Coming right 45 degrees, confirmed."

{control_name}: "{ship_name}, {control_name}. You're cleared for landing."
{ship_name}: "{control_name}, this is {ship_name}. Beginning landing approach."

Remember: You are {ship_name}. Always identify yourself when speaking. Never pretend to be {control_name}.
All of your dialogue with {control_name} should be in the format '{ship_name}: "{control_name}, {ship_name}, <request or polite concurrence here>"'"""
