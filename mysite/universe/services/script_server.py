from mysite.universe.services.dictionary import DictionaryService
import random

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

    def __init__(self, llm=None, pilot_call_sign: str = "DUKAKIS TANGO", default_cargo: str = "sulfuric acid"):
        """
        Initialize the ScriptService.
        
        Args:
            llm: Optional LLMService instance. If None, a new one will be created.
            pilot_call_sign: The call sign to use for the pilot.
            default_cargo: The default cargo to use if none is specified.
        """
        self.llm = llm if llm is not None else LLMService(quiet_mode=True)
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
        if not ship or not hasattr(ship, 'pilot') or not ship.pilot:
            raise ValueError("Ship must have a pilot to generate dialogue")

        pilot = ship.pilot
        
        # Get the controller name and actor
        if hasattr(nav_event, 'controller') and nav_event.controller:
            if hasattr(nav_event.controller, 'role') and nav_event.controller.role == 'CONTROLLER':
                # Controller is already a Controller actor
                controller_name = nav_event.controller.name
                expected_reply_actor = nav_event.controller
            else:
                # Controller is a Location, get or create the Controller actor
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
        
        metadata = {"control_name": controller_name}
        
        # Helper function to safely get location name
        def get_location_name(location) -> str:
            if location and hasattr(location, 'name'):
                return location.name
            return "unknown location"
            
        # Helper function to safely get next location name
        def get_next_name(nav_event) -> str:
            if hasattr(nav_event, 'next') and nav_event.next:
                return get_location_name(nav_event.next)
            return get_location_name(nav_event.destination)

        if nav_event.maneuver == ManeuverType.LAUNCH:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, requesting clearance for takeoff from {get_location_name(nav_event.origin)}."
            )
        elif nav_event.maneuver == ManeuverType.DIRECT_ASCENT:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, requesting a direct ascent burn for {get_location_name(nav_event.destination)}."
            )
        elif nav_event.maneuver == ManeuverType.CIRCULARIZE:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, requesting permission to circularize around {get_location_name(nav_event.current)}."
            )
        elif nav_event.maneuver == ManeuverType.PLANE_CHANGE:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, we're ready for our plane change maneuver."
            )
        elif nav_event.maneuver == ManeuverType.DEORBIT:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, we're ready to break orbit and head in to {get_location_name(nav_event.destination)}. Can you give us a vector?"
            )
        elif nav_event.maneuver == ManeuverType.LANDING:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, on final for our landing at {get_location_name(nav_event.destination)}. Please advise."
            )
        elif nav_event.maneuver == ManeuverType.INSERTION:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, we're ready for our insertion burn. Can you give us a vector for {get_location_name(nav_event.current)}?"
            )
        elif nav_event.maneuver == ManeuverType.DOCK:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, requesting docking clearance for {get_location_name(nav_event.destination)}."
            )
        elif nav_event.maneuver == ManeuverType.UNDOCK:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}, ready for departure. Request permission to undock from {get_location_name(nav_event.origin)}."
            )
        elif nav_event.maneuver == ManeuverType.SUBLIGHT:
            if controller_name == get_next_name(nav_event):
                text = (
                    f"{controller_name}, this is {self.pilot_call_sign}, we're inbound from {get_location_name(nav_event.origin)}, request a vector for {get_location_name(nav_event.destination)}."
                )
            elif controller_name == get_location_name(nav_event.current):
                text = (
                    f"{controller_name}, this is {self.pilot_call_sign}, heading for {get_location_name(nav_event.destination)} and ready for our outbound sublight burn."
                )
            else:
                text = (
                    f"{controller_name}, this is {self.pilot_call_sign}, requesting sublight burn on our way to {get_location_name(nav_event.destination)}."
                )
        elif nav_event.maneuver == ManeuverType.HYPERSPACE:
            text = (
                f"{controller_name}, this is {self.pilot_call_sign}. Gravity well shows clear; requesting hyperspace jump to {get_next_name(nav_event)}."
            )
        else:
            raise NotImplementedError("Navigation parsing for this maneuver type is not implemented.")

        # Bundle control_name in metadata for later reply generation.
        return DialogueEvent(
            timestamp=nav_event.duration,  # Using the nav event's duration as the trigger time.
            actor=pilot,
            text=text,
            expect_reply=True,
            expected_reply_actor=expected_reply_actor,
            duration=route_service.get_event_duration(nav_event),
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
        if getattr(dialogue.actor, 'role', None) == Actor.Role.PILOT:
            # Retrieve control name from the pilot dialogue's metadata.
            control_name = dialogue.metadata.get("control_name") if dialogue.metadata else "CONTROL"
            # Get more context from the dialogue event
            maneuver = dialogue.metadata.get("maneuver") if dialogue.metadata else "your maneuver"
            destination = dialogue.metadata.get("destination") if dialogue.metadata else "wherever you're bound"
            
            # Look up the existing controller or create one if it doesn't exist
            control_actor = Controller.objects.filter(name=control_name).first()
            if not control_actor:
                # Try to find the station with this name
                from mysite.universe.models.base import Location
                station = Location.objects.filter(name=control_name).first()
                if station:
                    control_actor = Controller.create(name=control_name, location=station)
                else:
                    control_actor = Controller.create(name=control_name)
            
            # Start with the basic reply format
            ship_name = dialogue.actor.ship.name if hasattr(dialogue.actor, 'ship') and dialogue.actor.ship else "Unknown Ship"
            reply_text = f"{ship_name}, this is {control_name}."
            
            # Randomly decide if a course correction is needed (1 in 6 chance)
            # Roll a die (1-6)
            roll = random.randint(1, 6)
            
            # Initialize direction metadata
            direction = {}
            degree_value = None
            
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
                    "degrees": degree_value,
                    "maneuver": dialogue.metadata.get("maneuver") if dialogue.metadata else None,
                    "ship": ship_name
                }
            else:
                # Standard confirmation without course correction
                reply_text += f" Confirmed for {maneuver} to {destination}."
                
                # Store basic metadata
                direction = {
                    "maneuver": maneuver,  # Pass through the maneuver we got earlier
                    "ship": ship_name,
                    "destination": destination  # Also pass through destination for context
                }
            
            # Pass the text to the LLM to get the "in character" text
            llm_text = self.llm.get_actor_text(
                line=reply_text,
                actor=control_actor,
                context=[dialogue.text]  # Include the pilot's message for context
            )
            
            # If LLM failed, use the original text
            if llm_text.startswith("Error communicating with LLM:"):
                llm_text = reply_text
            
            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,  # Reply occurs 3 seconds after the pilot event.
                actor=control_actor,
                text=llm_text,
                expect_reply=True,
                duration=3.0,
                event_type="dialogue",
                metadata=direction
            )
        elif getattr(dialogue.actor, 'role', None) == Actor.Role.CONTROLLER:
            # Retrieve pilot name from the pilot dialogue's metadata.
            ship_name = dialogue.metadata.get("ship") if dialogue.metadata else "Unidentified vessel"
            
            # Look up the ship and its pilot, or create a new pilot if not found
            from mysite.universe.models.ship import Ship
            ship = Ship.objects.filter(name=ship_name).first()
            if ship and ship.pilot:
                pilot_actor = ship.pilot
            else:
                pilot_actor = Pilot.create(name=ship_name)
                
            # Construct the reply text
            reply_text = (
                f"{dialogue.actor.name}, this is {ship_name}."
            )
            
            # If the pilot has been instructed to change course, add that to the reply
            if dialogue.metadata and dialogue.metadata.get("direction"):
                direction_text = dialogue.metadata.get("direction", "")
                degrees_text = str(dialogue.metadata.get("degrees", "0"))
                reply_text += f" Adjust {direction_text} by {degrees_text} degrees, confirmed, thank you."  
            else:
                # Get maneuver text safely - handle None values properly
                maneuver = dialogue.metadata.get("maneuver") if dialogue.metadata else None
                maneuver_text = maneuver.lower() if isinstance(maneuver, str) else "maneuver"
                reply_text += f" Beginning my {maneuver_text} now."  
            
            llm_text = self.llm.get_actor_text(reply_text, pilot_actor)
            
            # If LLM failed, use the original text
            if llm_text.startswith("Error communicating with LLM:"):
                llm_text = reply_text
            
            return DialogueEvent(
                timestamp=dialogue.timestamp + 3.0,  # Reply occurs 3 seconds after the pilot event.
                actor=pilot_actor,
                text=llm_text,
                expect_reply=False,
                duration=3.0,
                event_type="dialogue",
                metadata=dialogue.metadata
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
