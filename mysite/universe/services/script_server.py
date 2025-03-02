from dataclasses import dataclass
from typing import List
from ..models.navigation import NavigationEvent, ManeuverType
from ..models.ship import Ship
from ..services.dictionary import DictionaryService

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

