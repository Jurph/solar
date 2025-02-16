from enum import Enum
from dataclasses import dataclass
from typing import Optional
from mysite.universe.models import Location, Station

class ManeuverType(Enum):
    """Types of spacecraft maneuvers in our universe"""
    """These are alphabetized for easy checking against the Script Server"""
    CIRCULARIZE = "circularize"    # Stabilize orbit, either post-launch or on joining a system
    DOCK = "dock"                  # Dock with station
    HYPERSPACE = "hyperspace"      # Hyperspace jump to new system 
    LANDING = "landing"            # Orbit to surface
    LAUNCH = "launch"              # Surface to orbit
    PLANE_CHANGE = "plane_change"  # Change orbital inclination
    TRANSFER = "transfer"          # Hohmann transfer to new orbit
    UNDOCK = "undock"              # Leave station
    # TODO: consider adding "reentry" for elements with atmospheres 
    
@dataclass
class NavigationStep:
    """A single step in a navigation plan"""
    contact_station: Station       # Station to request permission from
    maneuver: ManeuverType        # Type of maneuver
    target: Location              # Target of the maneuver

    def get_required_clearance(self) -> str:
        """Get the type of clearance needed for this maneuver"""
        if self.maneuver == ManeuverType.LAUNCH:
            return "launch clearance"
        elif self.maneuver == ManeuverType.TRANSFER:
            return "transfer clearance"
        elif self.maneuver == ManeuverType.LANDING:
            return "landing clearance"
        elif self.maneuver == ManeuverType.CIRCULARIZE:
            return "orbital clearance"
        elif self.maneuver == ManeuverType.PLANE_CHANGE:
            return "orbital clearance"
        elif self.maneuver == ManeuverType.DOCK:
            return "docking clearance"
        elif self.maneuver == ManeuverType.UNDOCK:
            return "departure clearance"
        elif self.maneuver == ManeuverType.HYPERSPACE:
            return "clearance for hyperspace jump"
        else:
            raise ValueError(f"Unknown maneuver type: {self.maneuver}")
