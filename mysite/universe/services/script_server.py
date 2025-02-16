from dataclasses import dataclass
from typing import List
from ..models import Ship, Location, Station
from ..models.navigation import NavigationStep, ManeuverType
import random 

@dataclass
class DialogLine:
    speaker: str
    message: str

class ScriptService:
    """Service for generating radio communication scripts"""
    
    def generate_journey_script(self, ship: Ship, steps: List[NavigationStep]) -> List[DialogLine]:
        """Generate complete radio communications for a journey"""
        script = []
        
        for step in steps:
            script.extend(self._generate_step_dialog(ship, step))
            
        return script
    
    def _generate_step_dialog(self, ship: Ship, step: NavigationStep) -> List[DialogLine]:
        """Generate dialog for a single navigation step"""
        dialog = []
        control_name = step.contact_station.name
        
        if step.maneuver == ManeuverType.CIRCULARIZE:
            dialog.extend([
                DialogLine(
                    ship.name,
                    f"{control_name}, {ship.name} requesting clearance to circularize orbit"
                ),
                DialogLine(
                    control_name,
                    f"{ship.name}, clearance granted. Proceed with orbit stabilization."
                ),
                DialogLine(
                    ship.name,
                    "Roger, executing circularization burn."
                )
            ])
            
        elif step.maneuver == ManeuverType.DOCK:
            dialog.extend([
                DialogLine(
                    ship.name,
                    f"{control_name}, {ship.name} requesting docking clearance"
                ),
                DialogLine(
                    control_name,
                    f"{ship.name}, you are cleared for docking at berth {self._generate_berth_number(ship, step.contact_station)}"
                ),
                DialogLine(
                    ship.name,
                    "Confirmed, proceeding to assigned berth."
                )
            ])
            
        elif step.maneuver == ManeuverType.HYPERSPACE:
            dialog.extend([
                DialogLine(
                    ship.name,
                    f"{control_name}, {ship.name} requesting hyperspace clearance to {step.target.name} system"
                ),
                DialogLine(
                    control_name,
                    f"{ship.name}, hyperspace corridor is clear. You are go for jump."
                ),
                DialogLine(
                    ship.name,
                    "Roger that, spooling up hyperspace drive."
                ),
                DialogLine(
                    control_name,
                    f"{step.target.name} Control has been notified of your arrival window."
                ),
                DialogLine(
                    ship.name,
                    "Understood. Initiating jump in 3... 2... 1..."
                )
            ])
            
        elif step.maneuver == ManeuverType.LANDING:
            dialog.extend([
                DialogLine(
                    ship.name,
                    f"{control_name}, {ship.name} on final approach"
                ),
                DialogLine(
                    control_name,
                    f"{ship.name}, you are cleared to land. Surface conditions nominal."
                ),
                DialogLine(
                    ship.name,
                    "Copy that, beginning landing sequence."
                )
            ])
            
        elif step.maneuver == ManeuverType.LAUNCH:
            dialog.extend([
                DialogLine(
                    ship.name,
                    f"{control_name}, this is {ship.name}, requesting takeoff clearance"
                ),
                DialogLine(
                    control_name,
                    f"{ship.name}, this is {control_name}, takeoff approved. "
                    "Sending orbital parameters on channel four."
                ),
                DialogLine(
                    ship.name,
                    "Control, received on channel four, commencing takeoff."
                )
            ])
            
        elif step.maneuver == ManeuverType.PLANE_CHANGE:
            dialog.extend([
                DialogLine(
                    ship.name,
                    f"{control_name}, {ship.name} requesting clearance for inclination change to the ecliptic."
                ),
                DialogLine(
                    control_name,
                    f"{ship.name}, cleared for plane change maneuver. Mind your delta-v."
                ),
                DialogLine(
                    ship.name,
                    "Understood, commencing plane change burn."
                )
            ])
            
        elif step.maneuver == ManeuverType.TRANSFER:
            dialog.extend([
                DialogLine(
                    ship.name,
                    f"{control_name}, {ship.name} requesting transfer burn to {step.target.name}"
                ),
                DialogLine(
                    control_name,
                    f"{ship.name}, transfer to {step.target.name} approved. "
                    "Stand by for burn parameters."
                ),
                DialogLine(
                    ship.name,
                    "Parameters received, executing transfer burn."
                )
            ])
            
        elif step.maneuver == ManeuverType.UNDOCK:
            dialog.extend([
                DialogLine(
                    ship.name,
                    f"{control_name}, {ship.name} requesting departure clearance"
                ),
                DialogLine(
                    control_name,
                    f"{ship.name}, you are cleared to depart. Safe travels."
                ),
                DialogLine(
                    ship.name,
                    "Thanks control, releasing docking clamps now."
                )
            ])
        
        return dialog

        
    def _generate_berth_number(self, ship: Ship, station: Station) -> str:
        """Generate a plausible berth number based on available berths at the station
        
        Args:
            ship: The ship requesting docking
            station: The station being docked at
            
        Returns:
            A berth designation string like 'Alpha-12' appropriate for the ship size
        """
        # Get berths matching ship size
        available_berths = [b for b in station.berths if b.size == ship.size and not b.occupied]
        
        if not available_berths:
            raise ValueError(f"No available berths for {ship.size} ship at {station.name}")
            
        berth = random.choice(available_berths)
        return berth.designation