import xml.etree.ElementTree as ET
from django.db import transaction
from typing import Optional, Dict, Any
from decimal import Decimal
from mysite.universe.models import (
    Location, Galaxy, StarSystem,
    Star, Planet, Moon, Station
)

class UniverseImporter:
    def __init__(self, xml_path: str):
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        self.object_cache: Dict[str, Any] = {}
    
    def count_objects(self):
        """Count objects in the XML without importing them"""
        counts = {
            'galaxies': len(self.root.findall('.//galaxy')),
            'systems': len(self.root.findall('.//system')),
            'stars': len(self.root.findall('.//star')),
            'planets': len(self.root.findall('.//planet')),
            'moons': len(self.root.findall('.//moon')),
            'stations': len(self.root.findall('.//station')),
        }
        return counts
    
    def import_stations(self, element: ET.Element, parent: Location) -> None:
        """Import all stations that are direct children of any celestial object"""
        for station_elem in element.findall('./station'):
            station = Station(
                name=station_elem.findtext('name'),
                orbits=parent,
                scale='SS',
                large_berths=int(station_elem.findtext('large_berths') or 0),
                medium_berths=int(station_elem.findtext('medium_berths') or 0),
                small_berths=int(station_elem.findtext('small_berths') or 0)
            )
            station.save()
            self.object_cache[station.name] = station
    
    @transaction.atomic
    def import_universe(self) -> None:
        """Import entire universe, wrapped in a transaction"""
        for galaxy_elem in self.root.findall('./galaxy'):
            self.import_galaxy(galaxy_elem)
    
    def import_galaxy(self, element: ET.Element) -> Galaxy:
        """Import a galaxy and all its children"""
        galaxy = Galaxy(
            name=element.findtext('name'),
            galaxy_type=element.findtext('type'),
            galaxy_size=element.findtext('size'),
            scale='GX'
        )
        galaxy.save()
        self.object_cache[galaxy.name] = galaxy
        
        for system_elem in element.findall('./system'):
            self.import_system(system_elem, galaxy)
        
        return galaxy
    
    def import_system(self, element: ET.Element, galaxy: Galaxy) -> StarSystem:
        """Import a star system and all its children"""
        system = StarSystem(
            name=element.findtext('name'),
            orbits=galaxy,
            scale='SY'
        )
        system.save()
        self.object_cache[system.name] = system
        
        for star_elem in element.findall('./star'):
            self.import_star(star_elem, system)
            
        return system
    
    def import_star(self, element: ET.Element, system: StarSystem) -> Star:
        """Import a star and all its children"""
        star = Star(
            name=element.findtext('name'),
            star_type=element.findtext('type'),
            star_magnitude=Decimal(element.findtext('magnitude') or '0'),
            orbits=system,
            scale='SR'
        )
        star.save()
        self.object_cache[star.name] = star
        
        # Import moons that orbit the star directly
        for moon_elem in element.findall('./moon'):
            self.import_moon(moon_elem, star)
        
        # Import planets (which will handle their own moons)
        for planet_elem in element.findall('./planet'):
            self.import_planet(planet_elem, star)
        
        # Import stations orbiting the star
        self.import_stations(element, star)
        
        return star
    
    def import_planet(self, element: ET.Element, star: Star) -> Planet:
        """Import a planet and all its children"""
        planet = Planet(
            name=element.findtext('name'),
            planet_type=element.findtext('type'),
            orbits=star,
            scale='PL'
        )
        planet.save()
        self.object_cache[planet.name] = planet
        
        # Import moons orbiting this planet
        for moon_elem in element.findall('./moon'):
            self.import_moon(moon_elem, planet)
            
        # Import stations orbiting this planet
        self.import_stations(element, planet)
            
        return planet
    
    def import_moon(self, element: ET.Element, parent: Location) -> Moon:
        """Import a moon and its stations"""
        moon = Moon(
            name=element.findtext('name'),
            orbits=parent,
            scale='MN',
            variety=element.findtext('variety')
        )
        moon.save()
        self.object_cache[moon.name] = moon
        
        # Import stations orbiting this moon
        self.import_stations(element, moon)
            
        return moon