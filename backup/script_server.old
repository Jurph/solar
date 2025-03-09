from dataclasses import dataclass
from typing import List
from ..models.navigation import NavigationEvent, ManeuverType
from ..models.ship import Ship
from ..services.dictionary import DictionaryService
from mysite.universe.services.llm_service import LLMService


# LEGACY script server - the newer script_service.py uses the DialogueEvent and NavigationEvent classes.
@dataclass
class DialogLine:
    speaker: str
    message: str

class ScriptService:
    """Service for generating radio communication scripts based on navigation events."""
    
    def allcaps(self, text: str) -> str:
        """Convert the given text to all uppercase."""
        return text.upper()

    def generate_script(
        self, ship: Ship, navigation_events: List[NavigationEvent], destination: str
    ) -> str:
        """
        Convert NavigationEvents into a radio script following our etiquette rules:
        - Always address the recipient first: "<CONTROL_STATION>, this is <SHIP>..."
        - On departure: announce ship name, cargo, and destination.
        - On planetary arrival: announce ship name, cargo, and destination.
        The speaker labels are ALL CAPS.
        """
        lines = []
        for event in navigation_events:
            # Use the effective controller's name if available, otherwise fallback to target's name.
            controller_name = (
                self.allcaps(event.controller.name)
                # if event.controller is not None
                #else self.allcaps(event.target.name)
            )
            shipname_uc = self.allcaps(ship.name)
            target_name_uc = self.allcaps(event.target.name)

            if event.maneuver == ManeuverType.LAUNCH:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, this is {ship.name} carrying {ship.cargo} bound for {destination}. Requesting departure clearance."',
                    f'{controller_name}: "{ship.name}, departure approved. Stand by for launch vector."',
                    f'{shipname_uc}: "{controller_name}, {ship.name} vector received, commencing launch sequence. Thank you."'
                ])
            elif event.maneuver == ManeuverType.INSERTION:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, this is {ship.name}. Initiating insertion burn."',
                    f'{controller_name}: "{ship.name}, insertion burn confirmed. Maintain trajectory."',
                    f'{shipname_uc}: "{controller_name}, {ship.name} insertion complete."'
                ])
            elif event.maneuver == ManeuverType.CIRCULARIZE:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, {ship.name} initiating circularization burn."',
                    f'{controller_name}: "{ship.name}, circularization confirmed. Maintain orbital parameters."',
                    f'{shipname_uc}: "{controller_name}, {ship.name} circularization complete. Thank you."'
                ])
            elif event.maneuver == ManeuverType.PLANE_CHANGE:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, {ship.name} requesting clearance for plane change maneuver."',
                    f'{controller_name}: "{ship.name}, you are cleared for plane change. Monitor your delta-v carefully."',
                    f'{shipname_uc}: "Thank you, {controller_name}."'
                ])
            elif event.maneuver == ManeuverType.SUBLIGHT:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, this is {ship.name} carrying {ship.cargo} bound for {destination}. Requesting transfer burn clearance."',
                    f'{controller_name}: "{ship.name}, transfer burn pending. Stand by for parameters."',
                    f'{controller_name}: "Alright {ship.name}, transfer approved. Clear for sublight burn. {DictionaryService().get_random("GOODBYE")}."'
                ])
            elif event.maneuver == ManeuverType.HYPERSPACE:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, this is {ship.name}. Requesting hyperspace corridor clearance."',
                    f'{controller_name}: "{ship.name}, hyperspace corridor is clear. You are go for jump. {DictionaryService().get_random("GOODBYE")}."',
                    f'{shipname_uc}: "Acknowledged. Spooling up hyperspace drive."'
                ])
            elif event.maneuver == ManeuverType.DIRECT_ASCENT:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, {ship.name} requesting direct ascent to {destination}."',
                    f'{controller_name}: "{ship.name}, checking your corridor, hold tight."',
                    f'{controller_name}: "Alright {ship.name}, you are cleared for direct ascent."',
                    f'{shipname_uc}: "Thank you, {controller_name}. Throttling up on your mark."',
                    f'{controller_name}: "Stay safe, {ship.name}. Mark in 5, 4, 3, 2, ... Mark."'
                ])
            elif event.maneuver == ManeuverType.DEORBIT:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, {ship.name} initiating deorbit burn."',
                    f'{controller_name}: "{ship.name}, deorbit burn acknowledged. See you on the surface."'
                ])
            elif event.maneuver == ManeuverType.DOCK:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, this is {ship.name} requesting docking clearance."',
                    f'{controller_name}: "{ship.name}, you are cleared to dock. Proceed to your assigned berth."'
                ])
            elif event.maneuver == ManeuverType.LANDING:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, {ship.name} on final approach to {target_name_uc}."',
                    f'{controller_name}: "{ship.name}, landing clearance granted. Check in if you need to deviate."',
                    f'{shipname_uc}: "Thank you, {controller_name}."'
                ])
            elif event.maneuver == ManeuverType.UNDOCK:
                lines.extend([
                    f'{shipname_uc}: "{controller_name}, {ship.name} requesting undocking clearance."',
                    f'{controller_name}: "{ship.name}, you are cleared to undock."',
                    f'{shipname_uc}: "Thank you, {controller_name}. We\'ll be asking for maneuvers in a moment."'
                ])
        return "\n".join(lines)

    def script_handler(self, ship: Ship, navigation_events: List[NavigationEvent]) -> str:
        """Generate and output the radio script for the given navigation events."""
        final_destination = navigation_events[-1].target.name if navigation_events else "unknown"
        script = self.generate_script(ship, navigation_events, final_destination)
        print("Generated Script:")
        print(script)
        return script

    def generate_llm_script(self, events: List[NavigationEvent], ship_name: str, cargo: str, use_llm: bool = True) -> str:
        """
        Generate a script for a series of navigation events using an LLM for more natural dialogue.
        
        Args:
            events: The navigation events to generate script for
            ship_name: The name of the ship
            cargo: The cargo the ship is carrying
            use_llm: Whether to use the LLM (falls back to template if False or if LLM fails)
            
        Returns:
            A string containing the script
        """
        # First generate the template-based script as a fallback
        template_script = self.generate_script(events)
        
        if not use_llm:
            return template_script
            
        try:
            # Initialize the LLM service
            llm = LLMService(model_name="qwen2.5:0.5b")
            
            # Create a detailed prompt for the LLM
            system_prompt = """
            You are a space traffic control AI that generates realistic radio communications between spacecraft and control stations.
            Your task is to generate dialogue for a spacecraft journey, following these guidelines:
            
            1. Use proper radio communication etiquette, always stating who you're talking to, followed by who you are
            2. Include call signs, acknowledgments, and technical terminology appropriate for space navigation
            3. Each maneuver should have both the ship's request and the controller's response
            4. Keep communications professional but with slight variations in personality for different controllers
            5. Include occasional radio static markers [*static*] and technical issues in communications
            6. Mention the cargo in at least one exchange
            """
            
            # Build a description of the journey for the LLM
            journey_details = []
            for i, event in enumerate(events):
                origin = events[i-1].target.name if i > 0 else "starting location"
                controller = event.controller.name if event.controller else "Unknown Control"
                journey_details.append(f"{i+1}. {event.maneuver.name} from {origin} to {event.target.name} (Controller: {controller})")
            
            journey_text = "\n".join(journey_details)
            
            user_message = f"""
            Generate realistic radio communications for the journey of spacecraft "{ship_name}" carrying "{cargo}" as cargo.
            
            The navigation events are:
            {journey_text}
            
            For reference, here is a template-based script that you can improve upon:
            
            {template_script}
            
            Please create a more natural, engaging script with realistic dialogue following proper radio protocols.
            """
            
            # Get the LLM-generated script
            llm_script = llm.generate_with_system_prompt(
                user_message=user_message,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1024
            )
            
            return llm_script
            
        except Exception as e:
            # Fall back to template script if LLM fails
            print(f"LLM script generation failed: {e}. Using template script instead.")
            return template_script

