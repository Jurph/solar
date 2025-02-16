import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional
from mysite.universe.models import (
    Location, Galaxy, StarSystem,
    Star, Planet, Moon, Station
)

class UniverseExporter:
    """Exports the permanent universe structure to XML."""
    
    def __init__(self):
        self.root = ET.Element("universe")
    
    def export_universe(self) -> str:
        """Export entire universe to XML string"""
        for galaxy in Galaxy.objects.all():
            self.export_galaxy(galaxy)
            
        rough_string = ET.tostring(self.root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def export_galaxy(self, galaxy: Galaxy) -> ET.Element:
        """Export a galaxy and all its children"""
        galaxy_elem = ET.SubElement(self.root, "galaxy")
        
        ET.SubElement(galaxy_elem, "name").text = galaxy.name
        ET.SubElement(galaxy_elem, "scale").text = galaxy.scale
        ET.SubElement(galaxy_elem, "type").text = galaxy.galaxy_type
        ET.SubElement(galaxy_elem, "size").text = galaxy.galaxy_size
        
        # Export all systems in the galaxy
        for system in galaxy.star_systems.all():
            self.export_system(system, galaxy_elem)
            
        return galaxy_elem
    
    def export_system(self, system: StarSystem, parent: ET.Element) -> ET.Element:
        """Export a star system and its children"""
        system_elem = ET.SubElement(parent, "system")
        
        ET.SubElement(system_elem, "name").text = system.name
        ET.SubElement(system_elem, "scale").text = system.scale
        
        # Export all stars in the system
        for star in system.stars.all():
            self.export_star(star, system_elem)
            
        return system_elem
    
    def export_star(self, star: Star, parent: ET.Element) -> ET.Element:
        """Export a star and its children"""
        star_elem = ET.SubElement(parent, "star")
        
        ET.SubElement(star_elem, "name").text = star.name
        ET.SubElement(star_elem, "scale").text = star.scale
        ET.SubElement(star_elem, "type").text = star.star_type
        ET.SubElement(star_elem, "magnitude").text = str(star.star_magnitude)
        
        # Export planets
        for planet in star.planets.all():
            self.export_planet(planet, star_elem)

        # Export moons
        for moon in star.moons.all():
            self.export_moon(moon, star_elem)
          
        # Export stations orbiting the star
        self.export_stations(star, star_elem)
            
        return star_elem
    
    def export_planet(self, planet: Planet, parent: ET.Element) -> ET.Element:
        """Export a planet and its children"""
        planet_elem = ET.SubElement(parent, "planet")
        
        ET.SubElement(planet_elem, "name").text = planet.name
        ET.SubElement(planet_elem, "scale").text = planet.scale
        ET.SubElement(planet_elem, "type").text = planet.planet_type
        
        # Export moons
        for moon in planet.moons.all():
            self.export_moon(moon, planet_elem)
            
        # Export stations orbiting this planet
        self.export_stations(planet, planet_elem)
            
        return planet_elem
    
    def export_moon(self, moon: Moon, parent: ET.Element) -> ET.Element:
        """Export a moon and its stations"""
        moon_elem = ET.SubElement(parent, "moon")
        
        ET.SubElement(moon_elem, "name").text = moon.name
        ET.SubElement(moon_elem, "scale").text = moon.scale
        ET.SubElement(moon_elem, "variety").text = moon.variety
        
        # Export stations orbiting this moon
        self.export_stations(moon, moon_elem)
            
        return moon_elem
    
    def export_stations(self, parent_body: Location, parent_elem: ET.Element) -> None:
        """Export all stations orbiting a celestial body"""
        for station in Station.objects.filter(orbits=parent_body):
            station_elem = ET.SubElement(parent_elem, "station")
            ET.SubElement(station_elem, "name").text = station.name
            ET.SubElement(station_elem, "scale").text = station.scale
            ET.SubElement(station_elem, "large_berths").text = str(station.large_berths)
            ET.SubElement(station_elem, "medium_berths").text = str(station.medium_berths)
            ET.SubElement(station_elem, "small_berths").text = str(station.small_berths)