import xml.etree.ElementTree as ET
from .models import *
from django.db import transaction
from typing import Optional, Dict, Any
from decimal import Decimal

class UniverseImporter:
    def __init__(self, xml_path: str):
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        self.object_cache: Dict[str, Any] = {}
    
    def count_objects(self):
        """Count objects in the XML without importing them"""
        counts = {
            'galaxies': len(self.root.findall('galaxy')),
            'systems': len(self.root.findall('.//system')),
            'stars': len(self.root.findall('.//star')),
            'planets': len(self.root.findall('.//planet')),
            'moons': len(self.root.findall('.//satellite')),
            'stations': len(self.root.findall('.//station')),
        }
        return counts
    
    @transaction.atomic
    def import_universe(self) -> None:
        """Import entire universe, wrapped in a transaction"""
        for galaxy_elem in self.root.findall('.//galaxy'):
            self.import_galaxy(galaxy_elem)
    
    def import_galaxy(self, element: ET.Element) -> Galaxy:
        """Import a galaxy and all its children"""
        galaxy = Galaxy(
            name=element.findtext('galaxyName'),
            type=element.findtext('galaxyType'),
            size=element.findtext('galaxySize'),
            scale='GX'
        )
        galaxy.save()
        self.object_cache[galaxy.name] = galaxy
        
        for system_elem in element.findall('.//system'):
            self.import_system(system_elem, galaxy)
        
        return galaxy
    
    def import_system(self, element: ET.Element, parent: Galaxy) -> Optional[StarSystem]:
        """Import a star system and its children"""
        system = StarSystem(
            name=element.findtext('systemName', 'Sol System'),  # Default name if not specified
            orbits=parent,
            scale='SY'
        )
        system.save()
        self.object_cache[system.name] = system
        
        for star_elem in element.findall('.//star'):
            self.import_star(star_elem, system)
            
        return system

    def import_star(self, element: ET.Element, parent: StarSystem) -> Optional[Star]:
        """Import a star and its children"""
        star = Star(
            scale=Location.Scale.STAR,
            name=element.findtext('starName'),
            startype=element.findtext('starType'),
            starmagnitude=Decimal(element.findtext('starMagnitude', '0')),
            orbits=parent
        )
        star.save()
        self.object_cache[star.name] = star
        
        # Cache othernames for future use
        othernames = [e.text for e in element.findall('othername')]
        if othernames:
            self.object_cache[f"{star.name}_othernames"] = othernames
        
        for planet_elem in element.findall('.//planet'):
            self.import_planet(planet_elem, star)
        
        return star

    def import_planet(self, element: ET.Element, parent: Star) -> Optional[Planet]:
        """Import a planet and its children"""
        planet = Planet(
            scale=Location.Scale.PLANET,
            name=element.findtext('planetName'),
            orbits=parent,
            planettype=element.findtext('planetType', 'TE')  # Default to Terrestrial
        )
        planet.save()
        self.object_cache[planet.name] = planet
        
        # Handle othernames
        othernames = [e.text for e in element.findall('othername')]
        if othernames:
            self.object_cache[f"{planet.name}_othernames"] = othernames
        
        # Import any stations orbiting the planet
        for station_elem in element.findall('.//station'):
            self.import_station(station_elem, planet)
            
        # Import any moons
        for moon_elem in element.findall('.//satellite'):
            self.import_moon(moon_elem, planet)
            
        return planet

    def import_moon(self, element: ET.Element, parent: Planet) -> Optional[Moon]:
        """Import a moon and its children"""
        moon = Moon(
            scale=Location.Scale.MOON,
            name=element.findtext('satelliteName'),
            orbits=parent
        )
        moon.save()
        self.object_cache[moon.name] = moon
        
        # Import any stations orbiting the moon
        for station_elem in element.findall('.//station'):
            self.import_station(station_elem, moon)
            
        return moon

    def import_station(self, element: ET.Element, parent: Any) -> Optional[Station]:
        """Import a station, including berth information"""
        station = Station(
            scale=Location.Scale.STATION,
            name=element.findtext('stationName'),
            orbits=parent,
            large_berths=int(element.findtext('large_berths', '0')),
            medium_berths=int(element.findtext('medium_berths', '0')),
            small_berths=int(element.findtext('small_berths', '0'))
        )
        station.save()
        self.object_cache[station.name] = station
        return station

    def import_commodities(self, element: ET.Element, location: Any) -> None:
        """Placeholder for future commodity import/export support"""
        pass