"""
Service for generating physics-based parameters for controller responses.

This service calculates realistic orbital mechanics parameters based on
the physical properties of the relevant planet or moon.
"""

import random
import math
from typing import Dict, Optional
from mysite.universe.models.actor import Controller
from mysite.universe.models.base import Location
from mysite.universe.models.celestial import Planet, Moon, PhysicalBody
from mysite.universe.models.station import Station


class ControllerPhysicsService:
    """
    Generates physics-based parameters for controller clearance responses.
    
    Parameters are derived from the physical properties of the planet or moon
    that the controller is managing (either departure or arrival location).
    """
    
    @staticmethod
    def get_relevant_body(controller: Controller, nav_context: Dict) -> Optional[PhysicalBody]:
        """
        Determine the relevant planet/moon for physics calculations.
        
        Rules:
        - Arrival maneuvers (DEORBIT, LANDING, DOCK, INSERTION): use destination
        - Departure maneuvers (LAUNCH, UNDOCK): use origin/current
        - Transfer maneuvers (SUBLIGHT, TRANSFER, PLANE_CHANGE, CIRCULARIZE): use current
        
        Args:
            controller: Controller actor
            nav_context: Navigation context dictionary with maneuver_type, destination, origin, current_location
            
        Returns:
            Planet or Moon instance, or None if not found
        """
        maneuver_type = nav_context.get("maneuver_type", "").upper()
        
        # Determine which location to use
        target_location_name = None
        if maneuver_type in ["DEORBIT", "LANDING", "DOCK", "INSERTION"]:
            # Arrival: use destination
            target_location_name = nav_context.get("destination")
        elif maneuver_type in ["LAUNCH", "UNDOCK"]:
            # Departure: use origin or current
            target_location_name = nav_context.get("origin") or nav_context.get("current_location")
        else:
            # Transfer: use current
            target_location_name = nav_context.get("current_location")
        
        if not target_location_name:
            return None
        
        # Get the controller's location (Station)
        if not controller.location:
            return None
        
        station = controller.location.get_concrete_instance()
        if not isinstance(station, Station):
            return None
        
        # Find the planet/moon that the station orbits
        # Or find the target location directly
        # Try to find target location by name
        # Use filter().first() to handle duplicate names gracefully
        target_location = Location.objects.filter(name=target_location_name).first()
        if target_location:
            concrete = target_location.get_concrete_instance()
            
            if isinstance(concrete, (Planet, Moon)):
                return concrete
            
            # If target is a station, get what it orbits
            if isinstance(concrete, Station) and concrete.orbits:
                parent = concrete.orbits.get_concrete_instance()
                if isinstance(parent, (Planet, Moon)):
                    return parent
        
        # Fallback: use what the controller's station orbits
        if station.orbits:
            parent = station.orbits.get_concrete_instance()
            if isinstance(parent, (Planet, Moon)):
                return parent
        
        return None
    
    @staticmethod
    def generate_launch_parameters(body: PhysicalBody, nav_context: Dict) -> Dict[str, float]:
        """
        Generate parameters for LAUNCH/DIRECT_ASCENT maneuver.
        
        Returns:
            Dict with: inclination_deg, apogee_km, azimuth_deg
        """
        # Select a random circularization orbit lane
        target_circular_orbit = body.get_leo_band_altitude_km()
        
        # Launch apogee should be slightly above target
        apogee_km = body.get_launch_apogee_km(target_circular_orbit)
        
        # Inclination: near equatorial, within tolerance of axial tilt
        axial_tilt = body.axial_tilt_deg or 0.0
        # Inclination should be close to axial tilt (equatorial plane)
        base_inclination = axial_tilt
        # Add small random variation (±5 degrees)
        inclination_deg = base_inclination + random.uniform(-5.0, 5.0)
        # Normalize to 0-180 range
        inclination_deg = abs(inclination_deg) % 180.0
        
        # Azimuth: random 0-360 (for planet-oriented thinking)
        azimuth_deg = random.uniform(0.0, 360.0)
        
        return {
            "inclination_deg": round(inclination_deg, 1),
            "apogee_km": round(apogee_km, 1),
            "azimuth_deg": round(azimuth_deg, 1),
        }
    
    @staticmethod
    def generate_circularization_parameters(body: PhysicalBody, nav_context: Dict) -> Dict[str, float]:
        """
        Generate parameters for CIRCULARIZATION maneuver.
        
        Returns:
            Dict with: altitude_km, inclination_deg
        """
        # Select a random orbit lane
        altitude_km = body.get_leo_band_altitude_km()
        
        # Inclination: close to axial tilt (minor adjustments from launch)
        axial_tilt = body.axial_tilt_deg or 0.0
        # Small variation from axial tilt (±3 degrees)
        inclination_deg = axial_tilt + random.uniform(-3.0, 3.0)
        inclination_deg = abs(inclination_deg) % 180.0
        
        return {
            "altitude_km": round(altitude_km, 1),
            "inclination_deg": round(inclination_deg, 1),
        }
    
    @staticmethod
    def generate_insertion_parameters(body: PhysicalBody, nav_context: Dict) -> Dict[str, float]:
        """
        Generate parameters for INSERTION maneuver.
        
        Same as circularization, but for arrival at destination.
        
        Returns:
            Dict with: altitude_km, inclination_deg
        """
        return ControllerPhysicsService.generate_circularization_parameters(body, nav_context)
    
    @staticmethod
    def generate_sublight_parameters(body: PhysicalBody, nav_context: Dict) -> Dict[str, float]:
        """
        Generate parameters for SUBLIGHT/TRANSFER maneuver.
        
        Calculates a heading as an azimuth (0-360°) using a straight-line approximation.
        
        Returns:
            Dict with: azimuth_deg (and legacy alias departure_angle_deg for backward compatibility)
        """
        # Get origin and destination locations
        origin_name = nav_context.get("origin") or nav_context.get("current_location")
        destination_name = nav_context.get("destination")
        
        if not origin_name or not destination_name:
            # Fallback: random angle
            azimuth = round(random.uniform(0.0, 360.0), 1)
            return {
                "azimuth_deg": azimuth,
                "departure_angle_deg": azimuth,
            }
        
        # Try to get origin and destination bodies
        try:
            # Names are not guaranteed unique; use filter().first() for robustness.
            origin_loc = Location.objects.filter(name=origin_name).first()
            dest_loc = Location.objects.filter(name=destination_name).first()
            if origin_loc is None or dest_loc is None:
                raise ValueError("Origin or destination not found")
            
            origin_body = origin_loc.get_concrete_instance()
            dest_body = dest_loc.get_concrete_instance()
            
            # Get orbital distances (for planets, this is orbital_distance_au)
            origin_au = getattr(origin_body, 'orbital_distance_au', None) if isinstance(origin_body, Planet) else None
            dest_au = getattr(dest_body, 'orbital_distance_au', None) if isinstance(dest_body, Planet) else None
            
            if origin_au and dest_au:
                # Calculate angle using polar coordinates
                # Assume solar "north" is 0° azimuth
                # Calculate positions based on system age and orbital periods
                # Get system age (simplified: use current time or default)
                system_age_years = 4.5e9  # Default: 4.5 billion years
                if hasattr(origin_body, 'orbits') and origin_body.orbits:
                    star = origin_body.orbits
                    if hasattr(star, 'orbits') and star.orbits:
                        system = star.orbits
                        if hasattr(system, 'system_age_years') and system.system_age_years:
                            system_age_years = system.system_age_years
                
                # Calculate angular positions (theta)
                origin_period = getattr(origin_body, 'orbital_period_days', 365.25) * 365.25  # Convert to years
                dest_period = getattr(dest_body, 'orbital_period_days', 365.25) * 365.25
                
                origin_theta = (system_age_years / origin_period) % 1.0 * 360.0
                dest_theta = (system_age_years / dest_period) % 1.0 * 360.0
                
                # Calculate straight-line angle from origin to destination
                # Using law of cosines in polar coordinates
                dx = dest_au * math.cos(math.radians(dest_theta)) - origin_au * math.cos(math.radians(origin_theta))
                dy = dest_au * math.sin(math.radians(dest_theta)) - origin_au * math.sin(math.radians(origin_theta))
                
                departure_angle_deg = math.degrees(math.atan2(dy, dx))
                # Normalize to 0-360
                if departure_angle_deg < 0:
                    departure_angle_deg += 360.0
                
                azimuth = round(departure_angle_deg, 1)
                return {
                    "azimuth_deg": azimuth,
                    "departure_angle_deg": azimuth,
                }
        except Exception:
            pass
        
        # Fallback: random angle
        azimuth = round(random.uniform(0.0, 360.0), 1)
        return {
            "azimuth_deg": azimuth,
            "departure_angle_deg": azimuth,
        }

    @staticmethod
    def generate_hyperspace_parameters(body: PhysicalBody, nav_context: Dict) -> Dict[str, float]:
        """
        Generate parameters for HYPERSPACE maneuver.

        For now, we use the same azimuth generator as sublight/transfer; the difference
        is in dialogue wording ("jump" vs "burn").
        """
        return ControllerPhysicsService.generate_sublight_parameters(body, nav_context)
    
    @staticmethod
    def generate_plane_change_parameters(body: PhysicalBody, nav_context: Dict) -> Dict[str, float]:
        """
        Generate parameters for PLANE_CHANGE maneuver.
        
        Target inclination is the relative angle between current orbital plane
        and destination's orbital plane (or solar ecliptic).
        
        Returns:
            Dict with: target_inclination_deg
        """
        # Get destination for plane change target
        destination_name = nav_context.get("destination")
        current_inclination = nav_context.get("current_inclination", 0.0)  # Assume 0 if not provided
        
        if destination_name:
            from mysite.universe.models.base import Location
            try:
                dest_loc = Location.objects.get(name=destination_name)
                dest_body = dest_loc.get_concrete_instance()
                
                if isinstance(dest_body, (Planet, Moon)):
                    # Use destination's orbital inclination or axial tilt
                    target_inclination = dest_body.orbital_inclination_deg or dest_body.axial_tilt_deg or 0.0
                    # Calculate relative angle
                    target_inclination_deg = abs(target_inclination - current_inclination)
                    # Normalize to 0-180
                    if target_inclination_deg > 180.0:
                        target_inclination_deg = 360.0 - target_inclination_deg
                    
                    return {
                        "target_inclination_deg": round(target_inclination_deg, 1),
                    }
            except Exception:
                pass
        
        # Fallback: use body's axial tilt as target
        axial_tilt = body.axial_tilt_deg or 0.0
        return {
            "target_inclination_deg": round(axial_tilt, 1),
        }
    
    @staticmethod
    def generate_deorbit_parameters(body: PhysicalBody, nav_context: Dict) -> Dict[str, float]:
        """
        Generate parameters for DEORBIT maneuver.
        
        Returns:
            Dict with: deorbit_altitude_km, entry_angle_deg
        """
        # Deorbit typically happens at current orbit altitude
        # Use a standard LEO altitude if not specified
        deorbit_altitude_km = body.get_leo_band_altitude_km(lane_number=10)  # Default to lane 10
        
        # Calculate safe entry angle
        entry_angle_deg = body.get_safe_entry_angle_deg()
        
        return {
            "deorbit_altitude_km": round(deorbit_altitude_km, 1),
            "entry_angle_deg": round(entry_angle_deg, 1),
        }
    
    @staticmethod
    def generate_landing_parameters(body: PhysicalBody, nav_context: Dict) -> Dict[str, float]:
        """
        Generate parameters for LANDING/DOCK maneuver.
        
        Returns:
            Dict with: approach_heading_deg, approach_speed_ms
        """
        # Approach heading: random (would be calculated from position in real scenario)
        approach_heading_deg = random.uniform(0.0, 360.0)
        
        # Approach speed: function of surface gravity
        # Higher gravity = faster approach (more aggressive descent)
        surface_gravity = body.surface_gravity_ms2 if hasattr(body, 'surface_gravity_ms2') else None
        if surface_gravity is None and body.mass_kg and body.radius_km:
            # Calculate surface gravity: g = GM/r²
            G = 6.67430e-11  # Gravitational constant
            surface_gravity = (G * body.mass_kg) / ((body.radius_km * 1000) ** 2)
        
        # Base approach speed on gravity (Earth = 9.8 m/s² → ~50 m/s approach)
        if surface_gravity:
            # Scale: Earth gravity → 50 m/s, higher gravity → faster
            approach_speed_ms = 30.0 + (surface_gravity / 9.8) * 20.0
        else:
            approach_speed_ms = 50.0  # Default
        
        return {
            "approach_heading_deg": round(approach_heading_deg, 1),
            "approach_speed_ms": round(approach_speed_ms, 1),
        }
    
    @classmethod
    def generate_parameters(cls, controller: Controller, nav_context: Dict) -> Dict[str, any]:
        """
        Generate physics-based parameters for controller response.
        
        Args:
            controller: Controller actor
            nav_context: Navigation context dictionary
            
        Returns:
            Dictionary of parameters appropriate for the maneuver type
        """
        # Get relevant body (planet/moon)
        body = cls.get_relevant_body(controller, nav_context)
        if not body:
            return {}
        
        maneuver_type = nav_context.get("maneuver_type", "").upper()
        
        # Route to appropriate generator
        if maneuver_type in ["LAUNCH", "DIRECT_ASCENT"]:
            return cls.generate_launch_parameters(body, nav_context)
        elif maneuver_type == "CIRCULARIZATION":
            return cls.generate_circularization_parameters(body, nav_context)
        elif maneuver_type == "INSERTION":
            return cls.generate_insertion_parameters(body, nav_context)
        elif maneuver_type in ["SUBLIGHT", "TRANSFER"]:
            return cls.generate_sublight_parameters(body, nav_context)
        elif maneuver_type == "HYPERSPACE":
            return cls.generate_hyperspace_parameters(body, nav_context)
        elif maneuver_type == "PLANE_CHANGE":
            return cls.generate_plane_change_parameters(body, nav_context)
        elif maneuver_type == "DEORBIT":
            return cls.generate_deorbit_parameters(body, nav_context)
        elif maneuver_type in ["LANDING", "DOCK"]:
            return cls.generate_landing_parameters(body, nav_context)
        else:
            return {}

