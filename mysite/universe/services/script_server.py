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
    
    def generate_script(self, ship: Ship, navigation_events: List[NavigationEvent], destination: str) -> str:
        """
        Convert NavigationEvents into a radio script following our etiquette rules:
        - Always address the recipient first: "Control, this is <ship_name>..."
        - On departure: announce ship name, cargo, destination
        - On planetary arrival: announce ship name, cargo, destination
        """
        lines = []
        for event in navigation_events:
            control_name = event.target.name
            
            if event.maneuver == ManeuverType.LAUNCH:
                lines.extend([
                    f'SHIP: "{control_name}, this is {ship.name} carrying {ship.cargo} bound for {destination}. '
                    f'Requesting departure clearance."',
                    f'CONTROL: "{ship.name}, departure approved. Stand by for launch vector."',
                    f'SHIP: "Control, {ship.name}, vector received, commencing launch sequence. Thank you."'
                ])
                
            elif event.maneuver == ManeuverType.CIRCULARIZE:
                lines.extend([
                    f'SHIP: "{control_name}, {ship.name}. Initiating circularization burn."',
                    f'CONTROL: "{ship.name}, confirmed. Maintain orbital parameters."',
                    f'SHIP: "{control_name}, {ship.name}. Thank you."'
                ])
                
            elif event.maneuver == ManeuverType.PLANE_CHANGE:
                lines.extend([
                    f'SHIP: "{control_name}, {ship.name} requesting clearance for plane change maneuver."',
                    f'CONTROL: "{ship.name}, you are cleared for plane change. Mind your delta-v. Stay on reaction engines please."',
                    'SHIP: "Thank you, Control."'
                ])
                
            elif event.maneuver == ManeuverType.TRANSFER:
                # Special case: if transferring to a Planet, announce cargo and destination
                if event.target.get_type_name() == "Planet":
                    lines.extend([
                        f'SHIP: "{control_name}, this is {ship.name} carrying {ship.cargo} bound for {destination}. '
                        f'Requesting transfer burn clearance."',
                        f'CONTROL: "{ship.name}, transfer pending. Stand by for customs scan."',
                        f'CONTROL: "Alright {ship.name}, your transfer is approved. Clear for sublight burn."'
                    ])
                else:
                    lines.extend([
                        f'SHIP: "{control_name}, {ship.name} requesting transfer burn clearance to {event.target.name}."',
                        f'CONTROL: "{ship.name}, transfer approved. Sending burn parameters."'
                    ])
                
            elif event.maneuver == ManeuverType.DOCK:
                lines.extend([
                    f'SHIP: "{control_name}, this is {ship.name} requesting docking clearance."',
                    f'CONTROL: "{ship.name}, you are cleared to dock. Proceed to assigned berth."'
                ])
                
            elif event.maneuver == ManeuverType.LANDING:
                lines.extend([
                    f'SHIP: "{control_name}, {ship.name} on final approach to {event.target.name}."',
                    f'CONTROL: "{ship.name}, you are cleared to land. Surface conditions nominal."'
                ])
                
            elif event.maneuver == ManeuverType.HYPERSPACE:
                lines.extend([
                    f'SHIP: "{control_name}, this is {ship.name}. Requesting hyperspace corridor clearance."',
                    f'CONTROL: "{ship.name}, corridor is clear. You are go for jump."',
                    'SHIP: "Acknowledged. Spooling up hyperspace drive."'
                ])
                
            elif event.maneuver == ManeuverType.UNDOCK:
                lines.extend([
                    f'SHIP: "{control_name}, {ship.name} requesting undocking clearance."',
                    f'CONTROL: "{ship.name}, you are cleared to undock. Safe travels."'
                ])
            
        return "\n".join(lines)

    def script_handler(self, ship: Ship, navigation_events: List[NavigationEvent]) -> str:
        """Generate and output the radio script for the given navigation events."""
        # Get the final destination from the last event's target
        final_destination = navigation_events[-1].target.name if navigation_events else "unknown"
        
        script = self.generate_script(ship, navigation_events, final_destination)
        print("Generated Script:")
        print(script)
        return script