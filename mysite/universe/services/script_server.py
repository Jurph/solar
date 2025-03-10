from mysite.universe.services.dictionary import DictionaryService
import random

# Import our navigation models
from mysite.universe.models.navigation import NavigationEvent, ManeuverType
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.ship import Ship
from mysite.universe.models.actor import Pilot, Controller
from mysite.universe.services.llm_service import LLMService

dictionary_service = DictionaryService()
llm_service = LLMService()

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

    def __init__(self, pilot_call_sign: str = "DUKAKIS TANGO", default_cargo: str = "sulfuric acid"):
        self.pilot_call_sign = pilot_call_sign
        self.default_cargo = default_cargo

    def parse_navigation_event(self, nav_event: NavigationEvent, ship: Ship) -> DialogueEvent:
        """
        Parse a NavigationEvent to produce an initial DialogueEvent representing the pilot's request.
        
        For a SUBLIGHT maneuver, the pilot's dialogue might be:
        "[Controller], this is [pilot_call_sign], inbound from [origin] carrying [default_cargo]. 
        I need a vector for an insertion burn for [destination] orbit."
        
        The metadata will include the control name, so that later a reply can be generated.
        
        Args:
            nav_event: The NavigationEvent to parse.
            ship: The ship associated with the event. Its pilot is used as the dialogue actor.
        
        Returns:
            A DialogueEvent representing the pilot's broadcast.
        """
        pilot = ship.pilot
        controller_name = getattr(nav_event.controller, "name", None) or f"{nav_event.destination.name} Control"
        metadata = {"control_name": controller_name}
        expect_reply = True
        expected_reply_actor = nav_event.controller
        actor = pilot
        
        if nav_event.maneuver == ManeuverType.LAUNCH:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, requesting clearance for takeoff from {nav_event.origin.name}."
            )
            metadata = {"control_name": controller_name}
            duration = 90.0
        elif nav_event.maneuver == ManeuverType.DIRECT_ASCENT:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, requesting a direct ascent burn for {nav_event.destination.name}."
            )
            duration = 90.0
        elif nav_event.maneuver == ManeuverType.CIRCULARIZE:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, requesting permission to circularize around {nav_event.current.name}."
            )
            duration = 45.0
        elif nav_event.maneuver == ManeuverType.PLANE_CHANGE:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, we're ready for our plane change maneuver."
            )
            duration = 10.0
        elif nav_event.maneuver == ManeuverType.DEORBIT:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, we're ready to break orbit and head in to {nav_event.destination.name}. Can you give us a vector?"
            )
            duration = 45.0
        elif nav_event.maneuver == ManeuverType.LANDING:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, on final for our landing at {nav_event.destination.name}. Please advise."
            )
            duration = 75.0
        elif nav_event.maneuver == ManeuverType.INSERTION:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, we're ready for our insertion burn. Can you give us a vector for {nav_event.current.name}?"
            )
            duration = 45.0
        elif nav_event.maneuver == ManeuverType.DOCK:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, requesting docking clearance for {nav_event.destination.name}."
            )
            duration = 10.0
        elif nav_event.maneuver == ManeuverType.UNDOCK:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, ready for departure. Request permission to undock from {nav_event.origin.name}."
            )
            duration = 10.0
        elif nav_event.maneuver == ManeuverType.SUBLIGHT:
            if controller_name == nav_event.next.name:
                text = (
                    f"{controller_name}, this is {self.pilot_call_sign}, we're inbound from {nav_event.origin.name}, request a vector for {nav_event.destination.name}."
                )
                duration = 20.0
            elif controller_name == nav_event.current.name:
                text = (
                    f"{controller_name}, this is {self.pilot_call_sign}, heading for {nav_event.destination.name} and ready for our outbound sublight burn."
                )
                duration = 20.0
            else:
                text = (
                    f"{controller_name}, this is {self.pilot_call_sign}, requesting sublight burn on our way to {nav_event.destination.name}."
                )
                duration = 20.0
        elif nav_event.maneuver == ManeuverType.HYPERSPACE:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}. Gravity well shows clear; requesting hyperspace jump to {nav_event.next.name}."
            )
            duration = 10.0
        else:
            raise NotImplementedError("Navigation parsing for this maneuver type is not implemented.")

            # Bundle control_name in metadata for later reply generation.
        return DialogueEvent(
            timestamp=nav_event.duration,  # Using the nav event's duration as the trigger time.
            actor=pilot,
            text=text,
            expect_reply=True,
            expected_reply_actor=expected_reply_actor,
            duration=duration,
            event_type="dialogue",
            metadata=metadata
        )
            
    
    def parse_dialogue_event(self, dialogue: DialogueEvent) -> DialogueEvent:
        """
        Generate a standard reply DialogueEvent from Control in response to a pilot's dialogue event.
        
        The reply is standardized as:
        "[Pilot], this is [Control]. (Approximately yes you can do that). (OPTIONAL: instructions to change course). (OPTIONAL: goodbye) 
        
        It extracts the control name from the metadata in the pilot's dialogue event.
        
        Args:
            pilot_dialogue: The original DialogueEvent that expects a reply.
        
        Returns:
            A DialogueEvent representing the reply from Control.
        """
        # If a pilot is expecting a reply from Control, the reply event is fairly simple! 
        if dialogue.actor.type == "Pilot":
            # Retrieve control name from the pilot dialogue's metadata.
            control_name = dialogue.metadata.get("control_name") if dialogue.metadata else "CONTROL"
            # Get more context from the dialogue event
            maneuver = dialogue.metadata.get("maneuver") if dialogue.metadata else "your maneuver"
            destination = dialogue.metadata.get("destination") if dialogue.metadata else "wherever you're bound"
            
            
            # Create a Control actor; in a full implementation, you may look it up instead.
            control_actor = Controller.create(name=control_name)
            reply_text = (
                f"{dialogue.actor.name}, this is {control_name}."
            )
            
            # Randomly decide if a course correction is needed (1 in 6 chance)
            # Roll a die (1-6)
            roll = random.randint(1, 6)
            
            # Initialize direction metadata
            direction = {}
            
            # On a roll of 1, generate a course correction
            if roll == 1:
                # Pick a random direction
                directions = ["up", "down", "left", "right"]
                chosen_direction = random.choice(directions)
                
                # Pick a random degree value divisible by 5, between 5 and 90
                degree_value = random.randint(1, 18) * 5
                
                # Format the degree value as text (e.g., "twenty five")
                # Could use a degrees dictionary in a full implementation
                degree_text = str(degree_value)
                
                # Construct the correction instruction
                if chosen_direction in ["left", "right"]:
                    correction = f"Come {chosen_direction} {degree_text} degrees, approved for maneuver."
                else:
                    correction = f"Confirmed, nose {chosen_direction} by {degree_text} degrees and make your burn."
                
                # Add the correction to the reply
                reply_text += f" {correction}"
                
                # Store direction information in metadata for potential follow-up responses
                direction = {
                    "direction": chosen_direction,
                    "degrees": degree_value
                }
            else:
                # Standard confirmation without course correction
                reply_text += f" Confirmed for {maneuver} to {destination}."
                
                # TODO : Add goodbye message 1 in 3 times
            
                # TODO : Pass the text to the LLM, plus the Actor, to get the "in character" text
            llm_text = llm_service.get_actor_text(reply_text, control_actor)
            
            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,  # Reply occurs 3 seconds after the pilot event.
                actor=control_actor,
                text=llm_text,
                expect_reply=True,
                duration=3.0,
                event_type="dialogue",
                metadata=direction, degrees=degree_value, maneuver=ManeuverType, 
            )
        elif dialogue.actor.type == "Control":
            # Retrieve pilot name from the pilot dialogue's metadata.
            ship_name = dialogue.metadata.get("ship_name") if dialogue.metadata else "Unidentified vessel"
            # Get the pilot actor from the ship they're talking to
            pilot_actor = dialogue.metadata.get("ship").pilot if dialogue.metadata and dialogue.metadata.get("ship") else Pilot.create(name=ship_name)
            # Construct the reply text
            reply_text = (
                f"{dialogue.actor.name}, this is {ship_name}."
            )
            
            # If the pilot has been instructed to change course, add that to the reply
            if dialogue.metadata.get("direction"):
                reply_text += f" Adjust {dialogue.metadata.get('direction')} by {dialogue.metadata.get('degrees')} degrees, confirmed, thank you."  
            else:
                reply_text += f" Beginning my {dialogue.metadata.get('maneuver').lower()} now."  
            
            llm_text = llm_service.get_actor_text(reply_text, pilot_actor)
        
            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,  # Reply occurs 3 seconds after the pilot event.
                actor=pilot_actor,
                text=llm_text,
                expect_reply=False,
                duration=2.0,
                event_type="dialogue"
            )   
        else:
            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,  # Reply occurs 3 seconds after the pilot event.
                actor=dialogue.actor,
                text="Did you say something?",
                expect_reply=False,
                duration=2.0,
                event_type="dialogue"
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
