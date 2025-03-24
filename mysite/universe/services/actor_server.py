"""
Service for managing actors (Pilots, Controllers, etc.) in the universe.
"""

import random
from typing import List, Dict, Optional
from django.db import transaction
from mysite.universe.models.actor import Controller
from mysite.universe.models.base import Location
from mysite.universe.models.navigation import UniverseGraph

class ActorService:
    """Service for managing actors in the universe."""
    
    # Standard suffixes for non-control station controllers
    TRAFFIC_SUFFIXES = ["Transit", "Handler", "Local", "Authority"]
    
    @staticmethod
    def _generate_controller_name(location: Location) -> str:
        """
        Generate an appropriate controller name for a location.
        
        Args:
            location: The Location object to generate a controller name for
            
        Returns:
            A string representing the controller name
        """
        # If it's already a control or dispatch station, use its name
        if any(keyword in location.name for keyword in ["Control", "Dispatch"]):
            return location.name
            
        # For planets, use "Planetary Control"
        if hasattr(location, 'planet') and location.planet is not None:
            return f"{location.name} Planetary Control"
            
        # For moons, use "Control"
        if hasattr(location, 'moon') and location.moon is not None:
            return f"{location.name} Control"
            
        # For other stations, use a random traffic suffix
        suffix = random.choice(ActorService.TRAFFIC_SUFFIXES)
        return f"{location.name} {suffix}"
    
    @staticmethod
    def deploy_controllers(universe_graph: Optional[UniverseGraph] = None) -> Dict[str, List[Controller]]:
        """
        Deploy Controller actors to all major locations in the universe.
        
        This method:
        1. Creates Controllers for all Stations (with appropriate naming based on type)
        2. Creates Controllers for all Planets
        3. Creates Controllers for all Moons
        
        Args:
            universe_graph: Optional UniverseGraph instance. If None, gets the current instance.
            
        Returns:
            Dict with keys 'control_stations', 'regular_stations', 'planets', 'moons' 
            mapping to lists of created Controllers
        """
        if universe_graph is None:
            universe_graph = UniverseGraph.get_instance()
            
        results = {
            'control_stations': [],  # Stations with Control/Dispatch in name
            'regular_stations': [],  # Other stations
            'planets': [],
            'moons': []
        }
        
        with transaction.atomic():
            # Handle all stations first
            stations = Location.objects.filter(
                station__isnull=False
            ).select_related('station')
            
            for station in stations:
                controller_name = ActorService._generate_controller_name(station)
                controller = Controller.objects.filter(name=controller_name).first()
                
                if not controller:
                    controller = Controller.create(
                        name=controller_name,
                        location=station
                    )
                
                # Categorize based on whether it's a control station
                if any(keyword in station.name for keyword in ["Control", "Dispatch"]):
                    results['control_stations'].append(controller)
                else:
                    results['regular_stations'].append(controller)
            
            # Handle planets
            planets = Location.objects.filter(
                planet__isnull=False
            ).select_related('planet')
            
            for planet in planets:
                controller_name = ActorService._generate_controller_name(planet)
                controller = Controller.objects.filter(name=controller_name).first()
                if not controller:
                    controller = Controller.create(
                        name=controller_name,
                        location=planet
                    )
                results['planets'].append(controller)
            
            # Handle moons
            moons = Location.objects.filter(
                moon__isnull=False
            ).select_related('moon')
            
            for moon in moons:
                controller_name = ActorService._generate_controller_name(moon)
                controller = Controller.objects.filter(name=controller_name).first()
                if not controller:
                    controller = Controller.create(
                        name=controller_name,
                        location=moon
                    )
                results['moons'].append(controller)
        
        return results 