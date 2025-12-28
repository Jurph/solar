import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional
from mysite.universe.models import (
    Location, Galaxy, StarSystem,
    Star, Planet, Moon, Station
)

class UniverseExporter:
    """Exports the permanent universe structure to XML."""
    
    def __init__(self, compact: bool = False):
        self.compact = compact
        self.root = ET.Element("universe")
    
    def export_universe(self, galaxy_filter: Optional[str] = None, system_filter: Optional[str] = None) -> str:
        """
        Export the entire universe to an XML string.

        Optionally filter by galaxy or star system name.
        """
        galaxies = Galaxy.objects.all()
        if galaxy_filter:
            galaxies = galaxies.filter(name=galaxy_filter)

        for galaxy in galaxies:
            self.export_galaxy(galaxy, system_filter=system_filter)
            
        rough_string = ET.tostring(self.root, 'utf-8')
        if self.compact:
            return rough_string.decode("utf-8")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def export_galaxy(self, galaxy: Galaxy, system_filter: Optional[str] = None) -> ET.Element:
        """Export a galaxy and all its children"""
        galaxy_elem = ET.SubElement(self.root, "galaxy")
        
        ET.SubElement(galaxy_elem, "name").text = galaxy.name
        ET.SubElement(galaxy_elem, "scale").text = galaxy.scale
        ET.SubElement(galaxy_elem, "type").text = galaxy.galaxy_type
        ET.SubElement(galaxy_elem, "size").text = galaxy.galaxy_size
        
        systems = galaxy.star_systems.all()
        if system_filter:
            systems = systems.filter(name=system_filter)

        # Export all systems in the galaxy
        for system in systems:
            self.export_system(system, galaxy_elem)
            
        return galaxy_elem
    
    def export_system(self, system: StarSystem, parent: ET.Element) -> ET.Element:
        """Export a star system and its children"""
        system_elem = ET.SubElement(parent, "system")
        
        ET.SubElement(system_elem, "name").text = system.name
        ET.SubElement(system_elem, "scale").text = system.scale
        if getattr(system, "galactic_x_ly", None) is not None:
            ET.SubElement(system_elem, "galactic_x_ly").text = str(system.galactic_x_ly)
        if getattr(system, "galactic_y_ly", None) is not None:
            ET.SubElement(system_elem, "galactic_y_ly").text = str(system.galactic_y_ly)
        if getattr(system, "galactic_z_ly", None) is not None:
            ET.SubElement(system_elem, "galactic_z_ly").text = str(system.galactic_z_ly)
        if getattr(system, "system_age_years", None) is not None:
            ET.SubElement(system_elem, "system_age_years").text = str(system.system_age_years)
        
        # Export all stars in the system
        for star in system.stars.all():
            self.export_star(star, system_elem)
            
        return system_elem
    
    def export_star(self, star: Star, parent: ET.Element) -> ET.Element:
        """Export a star and its children"""
        star_elem = ET.SubElement(parent, "star")
        
        ET.SubElement(star_elem, "name").text = star.name
        ET.SubElement(star_elem, "scale").text = star.scale
        ET.SubElement(star_elem, "type").text = getattr(star, "star_type", "")
        ET.SubElement(star_elem, "magnitude").text = str(getattr(star, "star_magnitude", "0"))
        if getattr(star, "mass_kg", None) is not None:
            ET.SubElement(star_elem, "mass_kg").text = str(star.mass_kg)
        if getattr(star, "radius_km", None) is not None:
            ET.SubElement(star_elem, "radius_km").text = str(star.radius_km)
        if getattr(star, "density_kg_m3", None) is not None:
            ET.SubElement(star_elem, "density_kg_m3").text = str(star.density_kg_m3)
        if getattr(star, "temperature_k", None) is not None:
            ET.SubElement(star_elem, "temperature_k").text = str(star.temperature_k)
        if getattr(star, "luminosity_solar", None) is not None:
            ET.SubElement(star_elem, "luminosity_solar").text = str(star.luminosity_solar)
        
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
        ET.SubElement(planet_elem, "type").text = getattr(planet, "planet_type", "")
        # Common physical/orbital fields (only emit when present)
        if getattr(planet, "mass_kg", None) is not None:
            ET.SubElement(planet_elem, "mass_kg").text = str(planet.mass_kg)
        if getattr(planet, "radius_km", None) is not None:
            ET.SubElement(planet_elem, "radius_km").text = str(planet.radius_km)
        if getattr(planet, "density_kg_m3", None) is not None:
            ET.SubElement(planet_elem, "density_kg_m3").text = str(planet.density_kg_m3)
        if getattr(planet, "orbital_distance_au", None) is not None:
            ET.SubElement(planet_elem, "orbital_distance_au").text = str(planet.orbital_distance_au)
        if getattr(planet, "orbital_period_days", None) is not None:
            ET.SubElement(planet_elem, "orbital_period_days").text = str(planet.orbital_period_days)
        if getattr(planet, "rotation_period_hours", None) is not None:
            ET.SubElement(planet_elem, "rotation_period_hours").text = str(planet.rotation_period_hours)
        if getattr(planet, "axial_tilt_deg", None) is not None:
            ET.SubElement(planet_elem, "axial_tilt_deg").text = str(planet.axial_tilt_deg)
        if getattr(planet, "is_tidally_locked", None) is not None:
            ET.SubElement(planet_elem, "is_tidally_locked").text = "true" if planet.is_tidally_locked else "false"
        if getattr(planet, "albedo", None) is not None:
            ET.SubElement(planet_elem, "albedo").text = str(planet.albedo)
        if getattr(planet, "equilibrium_temperature_k", None) is not None:
            ET.SubElement(planet_elem, "equilibrium_temperature_k").text = str(planet.equilibrium_temperature_k)
        if getattr(planet, "orbital_eccentricity", None) is not None:
            ET.SubElement(planet_elem, "orbital_eccentricity").text = str(planet.orbital_eccentricity)
        if getattr(planet, "orbital_inclination_deg", None) is not None:
            ET.SubElement(planet_elem, "orbital_inclination_deg").text = str(planet.orbital_inclination_deg)

        # Atmosphere (ContentType-based; export if present)
        try:
            atmosphere = planet.get_atmosphere() if hasattr(planet, "get_atmosphere") else None
        except Exception:
            atmosphere = None
        if atmosphere:
            atmo_elem = ET.SubElement(planet_elem, "atmosphere")
            if getattr(atmosphere, "atmosphere_type", None) is not None:
                ET.SubElement(atmo_elem, "atmosphere_type").text = str(atmosphere.atmosphere_type)
            if getattr(atmosphere, "atmosphere_height_km", None) is not None:
                ET.SubElement(atmo_elem, "atmosphere_height_km").text = str(atmosphere.atmosphere_height_km)
            if getattr(atmosphere, "surface_pressure_bar", None) is not None:
                ET.SubElement(atmo_elem, "surface_pressure_bar").text = str(atmosphere.surface_pressure_bar)
            if getattr(atmosphere, "scale_height_km", None) is not None:
                ET.SubElement(atmo_elem, "scale_height_km").text = str(atmosphere.scale_height_km)

        # Composition (PhysicalBody fields)
        composition_fields = [
            ("iron_content", getattr(planet, "iron_content", None)),
            ("ice_content", getattr(planet, "ice_content", None)),
            ("has_methane", getattr(planet, "has_methane", None)),
            ("has_sulfur", getattr(planet, "has_sulfur", None)),
            ("water_coverage", getattr(planet, "water_coverage", None)),
            ("carbon_content", getattr(planet, "carbon_content", None)),
            ("organic_haze", getattr(planet, "organic_haze", None)),
        ]
        if any(v is not None for _, v in composition_fields):
            comp_elem = ET.SubElement(planet_elem, "composition")
            for key, val in composition_fields:
                if val is None:
                    continue
                if isinstance(val, bool):
                    ET.SubElement(comp_elem, key).text = "true" if val else "false"
                else:
                    ET.SubElement(comp_elem, key).text = str(val)
        
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
        ET.SubElement(moon_elem, "moon_type").text = moon.moon_type
        if getattr(moon, "mass_kg", None) is not None:
            ET.SubElement(moon_elem, "mass_kg").text = str(moon.mass_kg)
        if getattr(moon, "radius_km", None) is not None:
            ET.SubElement(moon_elem, "radius_km").text = str(moon.radius_km)
        if getattr(moon, "density_kg_m3", None) is not None:
            ET.SubElement(moon_elem, "density_kg_m3").text = str(moon.density_kg_m3)
        if getattr(moon, "orbital_distance_km", None) is not None:
            ET.SubElement(moon_elem, "orbital_distance_km").text = str(moon.orbital_distance_km)
        if getattr(moon, "orbital_period_hours", None) is not None:
            ET.SubElement(moon_elem, "orbital_period_hours").text = str(moon.orbital_period_hours)
        if getattr(moon, "rotation_period_hours", None) is not None:
            ET.SubElement(moon_elem, "rotation_period_hours").text = str(moon.rotation_period_hours)
        if getattr(moon, "axial_tilt_deg", None) is not None:
            ET.SubElement(moon_elem, "axial_tilt_deg").text = str(moon.axial_tilt_deg)
        if getattr(moon, "is_tidally_locked", None) is not None:
            ET.SubElement(moon_elem, "is_tidally_locked").text = "true" if moon.is_tidally_locked else "false"
        if getattr(moon, "albedo", None) is not None:
            ET.SubElement(moon_elem, "albedo").text = str(moon.albedo)

        # Atmosphere (ContentType-based; export if present)
        try:
            atmosphere = moon.get_atmosphere() if hasattr(moon, "get_atmosphere") else None
        except Exception:
            atmosphere = None
        if atmosphere:
            atmo_elem = ET.SubElement(moon_elem, "atmosphere")
            if getattr(atmosphere, "atmosphere_type", None) is not None:
                ET.SubElement(atmo_elem, "atmosphere_type").text = str(atmosphere.atmosphere_type)
            if getattr(atmosphere, "atmosphere_height_km", None) is not None:
                ET.SubElement(atmo_elem, "atmosphere_height_km").text = str(atmosphere.atmosphere_height_km)
            if getattr(atmosphere, "surface_pressure_bar", None) is not None:
                ET.SubElement(atmo_elem, "surface_pressure_bar").text = str(atmosphere.surface_pressure_bar)
            if getattr(atmosphere, "scale_height_km", None) is not None:
                ET.SubElement(atmo_elem, "scale_height_km").text = str(atmosphere.scale_height_km)

        # Composition (PhysicalBody fields)
        composition_fields = [
            ("iron_content", getattr(moon, "iron_content", None)),
            ("ice_content", getattr(moon, "ice_content", None)),
            ("has_methane", getattr(moon, "has_methane", None)),
            ("has_sulfur", getattr(moon, "has_sulfur", None)),
            ("water_coverage", getattr(moon, "water_coverage", None)),
            ("carbon_content", getattr(moon, "carbon_content", None)),
            ("organic_haze", getattr(moon, "organic_haze", None)),
        ]
        if any(v is not None for _, v in composition_fields):
            comp_elem = ET.SubElement(moon_elem, "composition")
            for key, val in composition_fields:
                if val is None:
                    continue
                if isinstance(val, bool):
                    ET.SubElement(comp_elem, key).text = "true" if val else "false"
                else:
                    ET.SubElement(comp_elem, key).text = str(val)
        
        # Export stations orbiting this moon
        self.export_stations(moon, moon_elem)
            
        return moon_elem
    
    def export_stations(self, parent_body: Location, parent_elem: ET.Element) -> None:
        """Export all stations orbiting a celestial body"""
        for station in Station.objects.filter(orbits=parent_body):
            station_elem = ET.SubElement(parent_elem, "station")
            ET.SubElement(station_elem, "name").text = station.name
            ET.SubElement(station_elem, "scale").text = station.scale
            if getattr(station, "orbital_distance_km", None) is not None:
                ET.SubElement(station_elem, "orbital_distance_km").text = str(station.orbital_distance_km)
            ET.SubElement(station_elem, "large_berths").text = str(getattr(station, "large_berths", 0))
            ET.SubElement(station_elem, "medium_berths").text = str(getattr(station, "medium_berths", 0))
            ET.SubElement(station_elem, "small_berths").text = str(getattr(station, "small_berths", 0))