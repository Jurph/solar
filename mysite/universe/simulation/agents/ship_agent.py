from typing import Optional
from django.db import transaction
import random
from ...models.ship import Ship
from ...models.station import Station
from ..events.maintenance import MaintenanceManager
from ...services.cargo_server import CargoService

class ShipAgent:
    def __init__(self, env, ship: Ship):
        self.env = env
        self.ship = ship
        self.maintenance_manager = MaintenanceManager(env)
        self.cargo_service = CargoService()
    
    async def begin_journey(self, destination: Station):
        """Start journey to new destination"""
        # Assign new cargo when starting journey
        self.ship.cargo = self.cargo_service.generate_cargo(
            self.ship, 
            departure=self.ship.current_location
        )
        self.ship.save()
        
        travel_time = self.calculate_travel_time(destination)
        self.ship.save()
        
        yield self.env.timeout(travel_time)
        
        with transaction.atomic():
            self.ship.current_location = destination
            self.ship.save()