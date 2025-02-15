import xml.etree.ElementTree as ET
from django.db import transaction
from typing import Optional, Dict, Any
from decimal import Decimal
from .models import (
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
            'moons': len(self.root.findall('.//satellite')),
            'stations': len(self.root.findall('.//station')),
        }
        return counts
    
    def import_stations(self, element: ET.Element, parent: Location) -> None:
        """Import all stations that are direct children of any celestial object"""
        for station_elem in element.findall('./station'):
            station = Station(
                name=station_elem.findtext('name'),  # Updated from stationName
                orbits=parent,
                scale='ST',
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
            galaxyType=element.findtext('galaxyType'),  # Updated from type
            galaxySize=element.findtext('galaxySize'),  # Updated from size
            scale='GX'
        )
        galaxy.save()
        self.object_cache[galaxy.name] = galaxy
        
        self.import_stations(element, galaxy)
        
        for system_elem in element.findall('./system'):
            self.import_system(system_elem, galaxy)
        
        return galaxy
    
    def import_system(self, element: ET.Element, galaxy: Galaxy) -> StarSystem:
        """Import a star system and all its children"""
        system = StarSystem(
            name=element.findtext('name'),  # Updated from systemName
            orbits=galaxy,
            scale='SY'
        )
        system.save()
        self.object_cache[system.name] = system
        
        self.import_stations(element, system)
        
        for star_elem in element.findall('./star'):
            self.import_star(star_elem, system)
            
        return system
    
    def import_star(self, element: ET.Element, system: StarSystem) -> Star:
        """Import a star and all its children"""
        star = Star(
            name=element.findtext('name'),  # Updated from starName
            starType=element.findtext('starType'),  # Updated from type
            starMagnitude=Decimal(element.findtext('starMagnitude') or '0'),  # Updated from magnitude
            orbits=system,
            scale='ST'
        )
        star.save()
        self.object_cache[star.name] = star
        
        self.import_stations(element, star)
        
        for planet_elem in element.findall('./planet'):
            self.import_planet(planet_elem, star)
        
        for satellite_elem in element.findall('./satellite'):
            self.import_moon(satellite_elem, star)
        
        return star
    
    def import_planet(self, element: ET.Element, star: Star) -> Planet:
        """Import a planet and all its children"""
        planet = Planet(
            name=element.findtext('name'),  # Updated from planetName
            planetType=element.findtext('planetType'),  # Updated from type
            orbits=star,
            scale='PL'
        )
        planet.save()
        self.object_cache[planet.name] = planet
        
        self.import_stations(element, planet)
        
        for moon_elem in element.findall('./satellite'):
            self.import_moon(moon_elem, planet)
            
        return planet
    
    def import_moon(self, element: ET.Element, parent: Location) -> Moon:
        """Import a moon and its direct child stations"""
        moon = Moon(
            name=element.findtext('name'),  # Updated from satelliteName
            orbits=parent,
            scale='MN'
        )
        moon.save()
        self.object_cache[moon.name] = moon
        
        self.import_stations(element, moon)
            
        return moon