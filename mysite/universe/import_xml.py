import xml.etree.ElementTree as ET
from django.db import transaction
from typing import Dict, Any
from decimal import Decimal
from mysite.universe.models import (
    Galaxy, StarSystem,
    Star, Planet, Moon, Station
)

class UniverseImporter:
    """Imports the universe from an XML file into the database."""

    def __init__(self, xml_path: str) -> None:
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        self.object_cache: Dict[str, Any] = {}
    
    def count_objects(self) -> Dict[str, int]:
        """
        Count objects in the XML without importing them.
        Returns a dictionary of counts for each type.
        """
        counts = {
            "galaxies": len(self.root.findall(".//galaxy")),
            "systems": len(self.root.findall(".//system")),
            "stars": len(self.root.findall(".//star")),
            "planets": len(self.root.findall(".//planet")),
            "moons": len(self.root.findall(".//moon")),
            "stations": len(self.root.findall(".//station")),
        }
        return counts
    
    def import_stations(self, element: ET.Element, parent) -> None:
        """Import all station elements that are children of the given element."""
        for station_elem in element.findall("./station"):
            name = station_elem.findtext("name")
            station, created = Station.objects.get_or_create(
                name=name,
                orbits=parent,
                defaults={
                    "scale": "SS",
                    "large_berths": int(station_elem.findtext("large_berths") or 0),
                    "medium_berths": int(station_elem.findtext("medium_berths") or 0),
                    "small_berths": int(station_elem.findtext("small_berths") or 0),
                }
            )
            # Update fields if they exist in XML (in case station was already created)
            if not created:
                if station_elem.findtext("large_berths"):
                    station.large_berths = int(station_elem.findtext("large_berths") or 0)
                if station_elem.findtext("medium_berths"):
                    station.medium_berths = int(station_elem.findtext("medium_berths") or 0)
                if station_elem.findtext("small_berths"):
                    station.small_berths = int(station_elem.findtext("small_berths") or 0)
                station.save()
            
            self.object_cache[station.name] = station

            # Create a Controller actor for control stations (only if newly created)
            # Note: Controllers are deployed separately via ActorService.deploy_controllers()
            # so we don't need to handle them here for idempotency
    
    @transaction.atomic
    def import_universe(self) -> None:
        """Import the entire universe; all changes are wrapped in an atomic transaction."""
        with transaction.atomic():
            for galaxy_elem in self.root.findall("./galaxy"):
                self.import_galaxy(galaxy_elem)
            
            # After importing the universe structure, deploy controllers
            from mysite.universe.services.actor_server import ActorService
            controllers = ActorService.deploy_controllers()
            
            # Log the deployment results
            print("\nController Deployment Results:")
            print(f"- {len(controllers['control_stations'])} dedicated control/dispatch stations")
            print(f"- {len(controllers['regular_stations'])} regular station controllers")
            print(f"- {len(controllers['planets'])} planetary controllers")
            print(f"- {len(controllers['moons'])} moon controllers")
            print(f"Total: {sum(len(v) for v in controllers.values())} controllers deployed")
    
    def import_galaxy(self, element: ET.Element) -> Galaxy:
        """Import a galaxy and all its children."""
        name = element.findtext("name")
        galaxy, created = Galaxy.objects.get_or_create(
            name=name,
            defaults={
                "galaxy_type": element.findtext("type"),
                "galaxy_size": element.findtext("size"),
                "scale": "GX",
            }
        )
        # Update fields if they exist in XML (in case galaxy was already created)
        if not created:
            if element.findtext("type"):
                galaxy.galaxy_type = element.findtext("type")
            if element.findtext("size"):
                galaxy.galaxy_size = element.findtext("size")
            galaxy.save()
        
        self.object_cache[galaxy.name] = galaxy
        
        for system_elem in element.findall("./system"):
            self.import_system(system_elem, galaxy)
        
        return galaxy
    
    def import_system(self, element: ET.Element, galaxy: Galaxy) -> StarSystem:
        """Import a star system and its children."""
        name = element.findtext("name")
        system, created = StarSystem.objects.get_or_create(
            name=name,
            orbits=galaxy,
            defaults={
                "scale": "SY",
            }
        )
        self.object_cache[system.name] = system
        
        for star_elem in element.findall("./star"):
            self.import_star(star_elem, system)
            
        return system
    
    def import_star(self, element: ET.Element, system: StarSystem) -> Star:
        """Import a star and its children."""
        name = element.findtext("name")
        star, created = Star.objects.get_or_create(
            name=name,
            orbits=system,
            defaults={
                "star_type": element.findtext("type"),
                "star_magnitude": Decimal(element.findtext("magnitude") or "0"),
                "scale": "SR",
            }
        )
        # Update fields if they exist in XML (in case star was already created)
        if not created:
            if element.findtext("type"):
                star.star_type = element.findtext("type")
            if element.findtext("magnitude"):
                star.star_magnitude = Decimal(element.findtext("magnitude") or "0")
            star.save()
        
        self.object_cache[star.name] = star
        
        for moon_elem in element.findall("./moon"):
            self.import_moon(moon_elem, star)
        for planet_elem in element.findall("./planet"):
            self.import_planet(planet_elem, star)
        self.import_stations(element, star)
        
        return star
    
    def import_planet(self, element: ET.Element, star: Star) -> Planet:
        """Import a planet and its children."""
        name = element.findtext("name")
        planet, created = Planet.objects.get_or_create(
            name=name,
            orbits=star,
            defaults={
                "planet_type": element.findtext("type"),
                "scale": "PL",
            }
        )
        # Update fields if they exist in XML (in case planet was already created)
        if not created:
            if element.findtext("type"):
                planet.planet_type = element.findtext("type")
            planet.save()
        
        self.object_cache[planet.name] = planet
        
        for moon_elem in element.findall("./moon"):
            self.import_moon(moon_elem, planet)
        self.import_stations(element, planet)
            
        return planet
    
    def import_moon(self, element: ET.Element, parent) -> Moon:
        """Import a moon and its stations."""
        name = element.findtext("name")
        variety = element.findtext("variety")
        moon, created = Moon.objects.get_or_create(
            name=name,
            orbits=parent,
            defaults={
                "scale": "MN",
                "variety": variety,
            }
        )
        # Update fields if they exist in XML (in case moon was already created)
        if not created:
            if variety:
                moon.variety = variety
            moon.save()
        
        self.object_cache[moon.name] = moon
        
        self.import_stations(element, moon)
            
        return moon