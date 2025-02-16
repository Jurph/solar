from ..simulation.engine import SimulationEngine
from ..simulation.agents.ship_agent import ShipAgent
from ..models.ship import Ship
from ..models.station import Station
from ..models.base import Location
from typing import Optional

class TrafficControlService:
    """Coordinates simulation agents and provides business logic interface"""
    
    def __init__(self):
        self.engine = SimulationEngine()
        self._agent_registry = {}  # ship_id -> agent mapping
        
    def register_ship(self, ship: Ship):
        """Add ship to simulation"""
        agent = ShipAgent(self.engine.env, ship)
        self._agent_registry[ship.id] = agent
        self.engine.add_agent(agent)
        
def populate_universe(self, ships_per_location: int = 3):
    stations = Location.objects.filter(scale='SS')
    for station in stations:
        for _ in range(ships_per_location):
            ship = Ship.create(location=station)
            self.register_ship(ship)