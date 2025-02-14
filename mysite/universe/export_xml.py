import xml.etree.ElementTree as ET
from xml.dom import minidom
from .models import *
from typing import Optional, Dict, Any

class UniverseExporter:
    def __init__(self):
        self.root = ET.Element("universe")
        
    def export_universe(self) -> str:
        """Export entire universe to XML string"""
        for galaxy in Galaxy.objects.all():
            self.export_galaxy(galaxy)
            
        # Pretty print the XML
        rough_string = ET.tostring(self.root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def export_galaxy(self, galaxy: Galaxy) -> ET.Element:
        """Export a galaxy and all its children"""
        galaxy_elem = ET.SubElement(self.root, "galaxy")
        
        ET.SubElement(galaxy_elem, "galaxyName").text = galaxy.name
        ET.SubElement(galaxy_elem, "galaxyType").text = galaxy.type
        ET.SubElement(galaxy_elem, "galaxySize").text = galaxy.size
        
        # Export all systems in the galaxy
        for system in StarSystem.objects.filter(orbits=galaxy):
            self.export_system(system, galaxy_elem)
            
        return galaxy_elem
    
    def export_system(self, system: StarSystem, parent: ET.Element) -> ET.Element:
        """Export a star system and its children"""
        system_elem = ET.SubElement(parent, "system")
        ET.SubElement(system_elem, "systemName").text = system.name
        
        # Export all stars in the system
        for star in Star.objects.filter(orbits=system):
            self.export_star(star, system_elem)
            
        return system_elem
    
    def export_star(self, star: Star, parent: ET.Element) -> ET.Element:
        """Export a star and its children"""
        star_elem = ET.SubElement(parent, "star")
        
        ET.SubElement(star_elem, "starName").text = star.name
        ET.SubElement(star_elem, "starType").text = star.startype
        ET.SubElement(star_elem, "starMagnitude").text = str(star.starmagnitude)
        
        # Export all planets orbiting the star
        for planet in Planet.objects.filter(orbits=star):
            self.export_planet(planet, star_elem)
            
        return star_elem
    
    def export_planet(self, planet: Planet, parent: ET.Element) -> ET.Element:
        """Export a planet and its children"""
        planet_elem = ET.SubElement(parent, "planet")
        
        ET.SubElement(planet_elem, "planetName").text = planet.name
        ET.SubElement(planet_elem, "planetType").text = planet.planettype
        
        # Export stations orbiting the planet
        for station in Station.objects.filter(orbits=planet):
            self.export_station(station, planet_elem)
            
        # Export moons orbiting the planet
        for moon in Moon.objects.filter(orbits=planet):
            self.export_moon(moon, planet_elem)
            
        return planet_elem
    
    def export_moon(self, moon: Moon, parent: ET.Element) -> ET.Element:
        """Export a moon and its children"""
        moon_elem = ET.SubElement(parent, "satellite")
        
        ET.SubElement(moon_elem, "satelliteName").text = moon.name
        
        # Export stations orbiting the moon
        for station in Station.objects.filter(orbits=moon):
            self.export_station(station, moon_elem)
            
        return moon_elem
    
    def export_station(self, station: Station, parent: ET.Element) -> ET.Element:
        """Export a station"""
        station_elem = ET.SubElement(parent, "station")
        
        ET.SubElement(station_elem, "stationName").text = station.name
        ET.SubElement(station_elem, "large_berths").text = str(station.large_berths)
        ET.SubElement(station_elem, "medium_berths").text = str(station.medium_berths)
        ET.SubElement(station_elem, "small_berths").text = str(station.small_berths)
        
        return station_elem

    def export_single_galaxy(self, galaxy_name: str) -> str:
        """Export a single galaxy by name"""
        try:
            galaxy = Galaxy.objects.get(name=galaxy_name)
            self.export_galaxy(galaxy)
            rough_string = ET.tostring(self.root, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")
        except Galaxy.DoesNotExist:
            raise ValueError(f"Galaxy '{galaxy_name}' not found")

    def export_single_system(self, system_name: str) -> str:
        """Export a single star system by name"""
        try:
            system = StarSystem.objects.get(name=system_name)
            system_elem = ET.SubElement(self.root, "universe")
            self.export_system(system, system_elem)
            rough_string = ET.tostring(self.root, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")
        except StarSystem.DoesNotExist:
            raise ValueError(f"Star system '{system_name}' not found")

    def compact_output(self, xml_content: str) -> str:
        """Remove pretty printing for compact output"""
        return ''.join(line.strip() for line in xml_content.splitlines())

    def add_template_docs(self, xml_content: str) -> str:
        """Add documentation comments for template usage"""
        template_docs = """<!--
Universe XML Template
===================
<universe>
  <galaxy>
    <galaxyName>Name</galaxyName>
    <galaxyType>Type (SP=Spiral, SB=Barred Spiral, etc)</galaxyType>
    <galaxySize>Size (S/M/L)</galaxySize>
    
    <system>
      <systemName>System Name</systemName>
      <star>
        <starName>Star Name</starName>
        <starType>Type (O/B/A/F/G/K/M)</starType>
        <starMagnitude>Absolute magnitude</starMagnitude>
        <othername>Alternative name</othername>
        
        <planet>
          <planetName>Planet Name</planetName>
          <planetType>Type (TE/GG/IG)</planetType>
          
          <station>
            <stationName>Station Name</stationName>
            <large_berths>4</large_berths>
            <medium_berths>8</medium_berths>
            <small_berths>16</small_berths>
          </station>
          
          <satellite>
            <satelliteName>Moon Name</satelliteName>
          </satellite>
        </planet>
      </star>
    </system>
  </galaxy>
</universe>
-->

"""
        return template_docs + xml_content