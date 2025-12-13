import xml.etree.ElementTree as ET
from django.db import transaction
from typing import Dict, Any
from decimal import Decimal
from mysite.universe.models import (
    Galaxy, StarSystem,
    Star, Planet, Moon, Station, Atmosphere
)
from django.contrib.contenttypes.models import ContentType

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
        # Import orbital_distance_au if it exists (this field exists on Planet)
        if element.findtext("orbital_distance_au"):
            planet.orbital_distance_au = float(element.findtext("orbital_distance_au"))
        # Import physical properties if Planet inherits from PhysicalBody (check if field exists)
        if hasattr(planet, 'mass_kg') and element.findtext("mass_kg"):
            planet.mass_kg = float(element.findtext("mass_kg"))
        if hasattr(planet, 'radius_km') and element.findtext("radius_km"):
            planet.radius_km = float(element.findtext("radius_km"))
        if hasattr(planet, 'density_kg_m3') and element.findtext("density_kg_m3"):
            planet.density_kg_m3 = float(element.findtext("density_kg_m3"))
        if hasattr(planet, 'orbital_period_days') and element.findtext("orbital_period_days"):
            planet.orbital_period_days = float(element.findtext("orbital_period_days"))
        if hasattr(planet, 'rotation_period_hours') and element.findtext("rotation_period_hours"):
            planet.rotation_period_hours = float(element.findtext("rotation_period_hours"))
        if hasattr(planet, 'axial_tilt_deg') and element.findtext("axial_tilt_deg"):
            planet.axial_tilt_deg = float(element.findtext("axial_tilt_deg"))
        if hasattr(planet, 'is_tidally_locked') and element.findtext("is_tidally_locked"):
            planet.is_tidally_locked = element.findtext("is_tidally_locked").lower() == "true"
        if hasattr(planet, 'albedo') and element.findtext("albedo"):
            planet.albedo = float(element.findtext("albedo"))
        if hasattr(planet, 'equilibrium_temperature_k') and element.findtext("equilibrium_temperature_k"):
            planet.equilibrium_temperature_k = float(element.findtext("equilibrium_temperature_k"))
        if hasattr(planet, 'orbital_eccentricity') and element.findtext("orbital_eccentricity"):
            planet.orbital_eccentricity = float(element.findtext("orbital_eccentricity"))
        if hasattr(planet, 'orbital_inclination_deg') and element.findtext("orbital_inclination_deg"):
            planet.orbital_inclination_deg = float(element.findtext("orbital_inclination_deg"))
        planet.save()
        
        # Import atmosphere if it exists
        atmosphere_elem = element.find("./atmosphere")
        if atmosphere_elem is not None:
            atmosphere_type = atmosphere_elem.findtext("atmosphere_type")
            if atmosphere_type and atmosphere_type != "NONE":
                content_type = ContentType.objects.get_for_model(Planet)
                atmosphere, _ = Atmosphere.objects.get_or_create(
                    content_type=content_type,
                    object_id=planet.id,
                    defaults={
                        "atmosphere_type": atmosphere_type,
                        "atmosphere_height_km": float(atmosphere_elem.findtext("atmosphere_height_km") or 0) if atmosphere_elem.findtext("atmosphere_height_km") else None,
                        "surface_pressure_bar": float(atmosphere_elem.findtext("surface_pressure_bar") or 0) if atmosphere_elem.findtext("surface_pressure_bar") else None,
                        "scale_height_km": float(atmosphere_elem.findtext("scale_height_km") or 0) if atmosphere_elem.findtext("scale_height_km") else None,
                    }
                )
                # Update if already exists
                if not _:
                    atmosphere.atmosphere_type = atmosphere_type
                    if atmosphere_elem.findtext("atmosphere_height_km"):
                        atmosphere.atmosphere_height_km = float(atmosphere_elem.findtext("atmosphere_height_km"))
                    if atmosphere_elem.findtext("surface_pressure_bar"):
                        atmosphere.surface_pressure_bar = float(atmosphere_elem.findtext("surface_pressure_bar"))
                    if atmosphere_elem.findtext("scale_height_km"):
                        atmosphere.scale_height_km = float(atmosphere_elem.findtext("scale_height_km"))
                    atmosphere.save()
        
        self.object_cache[planet.name] = planet
        
        for moon_elem in element.findall("./moon"):
            self.import_moon(moon_elem, planet)
        self.import_stations(element, planet)
            
        return planet
    
    def import_moon(self, element: ET.Element, parent) -> Moon:
        """Import a moon and its stations."""
        name = element.findtext("name")
        moon_type = element.findtext("moon_type")
        moon, created = Moon.objects.get_or_create(
            name=name,
            orbits=parent,
            defaults={
                "scale": "MN",
                "moon_type": moon_type,
            }
        )
        # Update fields if they exist in XML (in case moon was already created)
        if not created:
            if moon_type:
                moon.moon_type = moon_type
        # Import physical properties if Moon inherits from PhysicalBody (check if field exists)
        if hasattr(moon, 'mass_kg') and element.findtext("mass_kg"):
            moon.mass_kg = float(element.findtext("mass_kg"))
        if hasattr(moon, 'radius_km') and element.findtext("radius_km"):
            moon.radius_km = float(element.findtext("radius_km"))
        if hasattr(moon, 'density_kg_m3') and element.findtext("density_kg_m3"):
            moon.density_kg_m3 = float(element.findtext("density_kg_m3"))
        if hasattr(moon, 'orbital_distance_km') and element.findtext("orbital_distance_km"):
            moon.orbital_distance_km = float(element.findtext("orbital_distance_km"))
        if hasattr(moon, 'orbital_period_hours') and element.findtext("orbital_period_hours"):
            moon.orbital_period_hours = float(element.findtext("orbital_period_hours"))
        if hasattr(moon, 'rotation_period_hours') and element.findtext("rotation_period_hours"):
            moon.rotation_period_hours = float(element.findtext("rotation_period_hours"))
        if hasattr(moon, 'axial_tilt_deg') and element.findtext("axial_tilt_deg"):
            moon.axial_tilt_deg = float(element.findtext("axial_tilt_deg"))
        if hasattr(moon, 'is_tidally_locked') and element.findtext("is_tidally_locked"):
            moon.is_tidally_locked = element.findtext("is_tidally_locked").lower() == "true"
        if hasattr(moon, 'albedo') and element.findtext("albedo"):
            moon.albedo = float(element.findtext("albedo"))
        if hasattr(moon, 'equilibrium_temperature_k') and element.findtext("equilibrium_temperature_k"):
            moon.equilibrium_temperature_k = float(element.findtext("equilibrium_temperature_k"))
        if hasattr(moon, 'orbital_eccentricity') and element.findtext("orbital_eccentricity"):
            moon.orbital_eccentricity = float(element.findtext("orbital_eccentricity"))
        if hasattr(moon, 'orbital_inclination_deg') and element.findtext("orbital_inclination_deg"):
            moon.orbital_inclination_deg = float(element.findtext("orbital_inclination_deg"))
        moon.save()
        
        # Import atmosphere if it exists
        atmosphere_elem = element.find("./atmosphere")
        if atmosphere_elem is not None:
            atmosphere_type = atmosphere_elem.findtext("atmosphere_type")
            if atmosphere_type and atmosphere_type != "NONE":
                content_type = ContentType.objects.get_for_model(Moon)
                atmosphere, _ = Atmosphere.objects.get_or_create(
                    content_type=content_type,
                    object_id=moon.id,
                    defaults={
                        "atmosphere_type": atmosphere_type,
                        "atmosphere_height_km": float(atmosphere_elem.findtext("atmosphere_height_km") or 0) if atmosphere_elem.findtext("atmosphere_height_km") else None,
                        "surface_pressure_bar": float(atmosphere_elem.findtext("surface_pressure_bar") or 0) if atmosphere_elem.findtext("surface_pressure_bar") else None,
                        "scale_height_km": float(atmosphere_elem.findtext("scale_height_km") or 0) if atmosphere_elem.findtext("scale_height_km") else None,
                    }
                )
                # Update if already exists
                if not _:
                    atmosphere.atmosphere_type = atmosphere_type
                    if atmosphere_elem.findtext("atmosphere_height_km"):
                        atmosphere.atmosphere_height_km = float(atmosphere_elem.findtext("atmosphere_height_km"))
                    if atmosphere_elem.findtext("surface_pressure_bar"):
                        atmosphere.surface_pressure_bar = float(atmosphere_elem.findtext("surface_pressure_bar"))
                    if atmosphere_elem.findtext("scale_height_km"):
                        atmosphere.scale_height_km = float(atmosphere_elem.findtext("scale_height_km"))
                    atmosphere.save()
        
        self.object_cache[moon.name] = moon
        
        self.import_stations(element, moon)
            
        return moon