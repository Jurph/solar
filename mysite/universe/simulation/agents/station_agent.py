from ..simulation.engine import SimulationEngine
from ..simulation.agents.ship_agent import ShipAgent
from ..models.ship import Ship
from ..models.station import Station
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
        
    def find_agent_for_ship(self, ship: Ship) -> Optional[ShipAgent]:
        """Retrieve the agent for a given ship"""
        agent = self._agent_registry.get(ship.id)
        if not agent:
            raise ValueError(f"No agent found for ship {ship.name}")
        return agent
        
    def dispatch_ship(self, ship: Ship, destination: Station):
        """Order ship to begin journey"""
        agent = self.find_agent_for_ship(ship)
        self.engine.env.process(agent.begin_journey(destination))