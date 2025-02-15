import simpy
from typing import Optional
from django.db import transaction
from ..models.ship import Ship
from ..models.station import Station

class SimulationEngine:
    """Core simulation engine using SimPy"""
    
    def __init__(self):
        self.env = simpy.Environment()
        self.active_agents = []

    def add_agent(self, agent):
        """Register an agent with the simulation"""
        self.active_agents.append(agent)
        self.env.process(agent.run())

    def run(self, duration: Optional[int] = None):
        """Run simulation for specified duration"""
        self.env.run(until=duration)