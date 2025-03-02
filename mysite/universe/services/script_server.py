from dataclasses import dataclass
from typing import List
from ..models.navigation import NavigationEvent, ManeuverType
from ..models.ship import Ship

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
            control_name = event.target.name
            shipname_uc = self.allcaps(ship.name)
            control_name_uc = self.allcaps(control_name)

            if event.maneuver == ManeuverType.LAUNCH:
                lines.extend([
                    f'{shipname_uc}: "{control_name}, this is {ship.name} carrying {ship.cargo} bound for {destination}. Requesting departure clearance."',
                    f'{control_name_uc}: "{ship.name}, departure approved. Stand by for launch vector."',
                    f'{shipname_uc}: "{control_name}, {ship.name} vector received, commencing launch sequence. Thank you."'
                ])
            elif event.maneuver == ManeuverType.CIRCULARIZE:
                lines.extend([
                    f'{shipname_uc}: "{control_name}, {ship.name}. Initiating circularization burn."',
                    f'{control_name_uc}: "{ship.name}, confirmed. Maintain orbital parameters."',
                    f'{shipname_uc}: "{control_name}, {ship.name}. Thank you."'
                ])
            elif event.maneuver == ManeuverType.PLANE_CHANGE:
                lines.extend([
                    f'{shipname_uc}: "{control_name}, {ship.name} requesting clearance for plane change maneuver."',
                    f'{control_name_uc}: "{ship.name}, you are cleared for plane change. Mind your delta-v. Stay on reaction engines please."',
                    f'{shipname_uc}: "Thank you, {control_name}."'
                ])
            elif event.maneuver == ManeuverType.TRANSFER:
                if event.target.get_type_name() == "Planet":
                    lines.extend([
                        f'{shipname_uc}: "{control_name}, this is {ship.name} carrying {ship.cargo} bound for {destination}. Requesting transfer burn clearance."',
                        f'{control_name_uc}: "{ship.name}, transfer pending. Stand by for customs scan."',
                        f'{control_name_uc}: "Alright {ship.name}, your transfer is approved. Clear for sublight burn."'
                    ])
                else:
                    lines.extend([
                        f'{shipname_uc}: "{control_name}, {ship.name} requesting transfer burn clearance to {control_name}."',
                        f'{control_name_uc}: "{ship.name}, transfer approved. Sending burn parameters."'
                    ])
            elif event.maneuver == ManeuverType.DOCK:
                lines.extend([
                    f'{shipname_uc}: "{control_name}, this is {ship.name} requesting docking clearance."',
                    f'{control_name_uc}: "{ship.name}, you are cleared to dock. Proceed to assigned berth."'
                ])
            elif event.maneuver == ManeuverType.LANDING:
                lines.extend([
                    f'{shipname_uc}: "{control_name}, {ship.name} on final approach to {event.target.name}."',
                    f'{control_name_uc}: "{ship.name}, you are cleared to land. Surface conditions nominal."'
                ])
            elif event.maneuver == ManeuverType.HYPERSPACE:
                lines.extend([
                    f'{shipname_uc}: "{control_name}, this is {ship.name}. Requesting hyperspace corridor clearance."',
                    f'{control_name_uc}: "{ship.name}, corridor is clear. You are go for jump."',
                    f'{shipname_uc}: "Acknowledged. Spooling up hyperspace drive."'
                ])
            elif event.maneuver == ManeuverType.UNDOCK:
                lines.extend([
                    f'{shipname_uc}: "{control_name}, {ship.name} requesting undocking clearance."',
                    f'{control_name_uc}: "{ship.name}, you are cleared to undock. Safe travels."'
                ])
        return "\n".join(lines)

    def script_handler(self, ship: Ship, navigation_events: List[NavigationEvent]) -> str:
        """Generate and output the radio script for the given navigation events."""
        final_destination = navigation_events[-1].target.name if navigation_events else "unknown"
        script = self.generate_script(ship, navigation_events, final_destination)
        print("Generated Script:")
        print(script)
        return script

