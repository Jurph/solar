"""
Service for calculating physics-based maneuver durations.

Uses realistic orbital mechanics to determine how long each maneuver takes,
based on planetary properties, distances, and vehicle capabilities.

Key formulas:
- LAUNCH: Time to clear atmosphere at max acceleration
- CIRCULARIZE: Half orbital period (coast to apogee)
- SUBLIGHT: Distance / velocity for interplanetary transit
- INSERTION: Similar to circularize
- DEORBIT/LANDING: Entry and descent time
"""

import math
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Physical constants
EARTH_G = 9.80665  # m/s² - standard gravity
C = 299_792_458  # m/s - speed of light
AU_IN_METERS = 1.496e11  # meters per AU
G = 6.67430e-11  # gravitational constant (m³/kg/s²)


@dataclass
class VehicleParams:
    """Parameters for the spacecraft performing maneuvers."""
    max_proper_accel_gees: float = 3.5  # Crew comfort cap
    avg_vertical_thrust_frac: float = 0.85  # Gravity turn efficiency
    sublight_velocity_c: float = 0.1  # Fraction of light speed for sublight


class ManeuverPhysicsService:
    """
    Calculates physics-based durations for spacecraft maneuvers.
    
    All durations are returned in seconds.
    """
    
    def __init__(self, vehicle: Optional[VehicleParams] = None):
        """
        Initialize with optional vehicle parameters.
        
        Args:
            vehicle: VehicleParams instance, or None to use defaults
        """
        self.vehicle = vehicle or VehicleParams()
    
    # -------------------------------------------------------------------------
    # LAUNCH: Time to clear atmosphere
    # -------------------------------------------------------------------------
    def calculate_launch_duration(
        self,
        atmospheric_height_km: float,
        planet_gravity_gees: float,
        planet_radius_km: float,
        rotation_period_seconds: float,
        launch_latitude_deg: float = 0.0,
    ) -> float:
        """
        Calculate time to clear atmosphere using ascent formula.
        
        Formula: t = √(2H / (a_max·s - g_eff))
        
        Where:
        - H = atmospheric height (meters)
        - a_max = max vehicle acceleration (m/s²)
        - s = vertical thrust fraction (gravity turn efficiency)
        - g_eff = effective gravity (surface gravity - centrifugal)
        
        Args:
            atmospheric_height_km: Height of atmosphere to clear (km)
            planet_gravity_gees: Surface gravity in Earth g's
            planet_radius_km: Planet radius (km)
            rotation_period_seconds: Sidereal rotation period (seconds)
            launch_latitude_deg: Latitude of launch site (degrees)
            
        Returns:
            Time to clear atmosphere in seconds, or float('inf') if cannot ascend
        """
        # Convert units
        H = atmospheric_height_km * 1000  # km → m
        R = planet_radius_km * 1000  # km → m
        phi = math.radians(launch_latitude_deg)
        
        # Planet gravity (m/s²)
        g = planet_gravity_gees * EARTH_G
        
        # Angular rotation rate (rad/s)
        if rotation_period_seconds > 0:
            omega = 2 * math.pi / rotation_period_seconds
        else:
            omega = 0
        
        # Centrifugal reduction of gravity
        centrifugal = omega**2 * R * math.cos(phi)**2
        
        # Effective downward gravity
        g_eff = g - centrifugal
        
        # Vehicle proper acceleration capability
        a_max = self.vehicle.max_proper_accel_gees * EARTH_G
        
        # Net upward vertical acceleration
        a_vertical = a_max * self.vehicle.avg_vertical_thrust_frac - g_eff
        
        if a_vertical <= 0:
            return float('inf')  # Cannot ascend
        
        # Time to clear atmosphere
        time_to_clear_atmo_sec = math.sqrt(2 * H / a_vertical)
        
        return time_to_clear_atmo_sec
    
    # -------------------------------------------------------------------------
    # CIRCULARIZE: Half orbital period (coast to apogee)
    # -------------------------------------------------------------------------
    def calculate_circularization_duration(
        self,
        altitude_km: float,
        planet_radius_km: float,
        planet_mass_kg: float,
    ) -> float:
        """
        Calculate time to coast to apogee (half orbital period).
        
        For a Hohmann-like transfer, the ship coasts from perigee to apogee,
        which takes half the orbital period at the transfer orbit.
        
        Formula: T/2 = π√(a³/μ)
        
        Where:
        - a = semi-major axis (for circular target: planet_radius + altitude)
        - μ = G * M (gravitational parameter)
        
        Args:
            altitude_km: Target circular orbit altitude (km)
            planet_radius_km: Planet radius (km)
            planet_mass_kg: Planet mass (kg)
            
        Returns:
            Time to coast to apogee in seconds
        """
        # Semi-major axis (meters) - for circular orbit, this is just radius + altitude
        a = (planet_radius_km + altitude_km) * 1000  # km → m
        
        # Gravitational parameter
        mu = G * planet_mass_kg
        
        # Orbital period
        T = 2 * math.pi * math.sqrt(a**3 / mu)
        
        # Half period (coast to apogee)
        return T / 2
    
    # -------------------------------------------------------------------------
    # SUBLIGHT: Interplanetary transit time
    # -------------------------------------------------------------------------
    def calculate_sublight_duration(
        self,
        distance_au: float,
        velocity_c: Optional[float] = None,
    ) -> float:
        """
        Calculate transit time for sublight travel.
        
        Formula: t = d / v
        
        Args:
            distance_au: Distance to travel in AU
            velocity_c: Velocity as fraction of c (default: vehicle's sublight_velocity_c)
            
        Returns:
            Transit time in seconds
        """
        if velocity_c is None:
            velocity_c = self.vehicle.sublight_velocity_c
        
        if velocity_c <= 0:
            return float('inf')
        
        # Convert distance to meters
        distance_m = distance_au * AU_IN_METERS
        
        # Velocity in m/s
        velocity_ms = velocity_c * C
        
        # Time = distance / velocity
        return distance_m / velocity_ms
    
    # -------------------------------------------------------------------------
    # INSERTION: Similar to circularize (arriving at destination)
    # -------------------------------------------------------------------------
    def calculate_insertion_duration(
        self,
        altitude_km: float,
        planet_radius_km: float,
        planet_mass_kg: float,
    ) -> float:
        """
        Calculate time for orbital insertion (same as circularization).
        
        Args:
            altitude_km: Target orbit altitude (km)
            planet_radius_km: Planet radius (km)
            planet_mass_kg: Planet mass (kg)
            
        Returns:
            Time for insertion maneuver in seconds
        """
        return self.calculate_circularization_duration(
            altitude_km, planet_radius_km, planet_mass_kg
        )
    
    # -------------------------------------------------------------------------
    # DEORBIT: Time from orbit to entry interface
    # -------------------------------------------------------------------------
    def calculate_deorbit_duration(
        self,
        orbit_altitude_km: float,
        entry_interface_km: float,
        planet_radius_km: float,
        planet_mass_kg: float,
    ) -> float:
        """
        Calculate time from deorbit burn to entry interface.
        
        Approximates as a partial orbit from current altitude to entry interface.
        
        Args:
            orbit_altitude_km: Current orbit altitude (km)
            entry_interface_km: Entry interface altitude (typically ~100km for Earth)
            planet_radius_km: Planet radius (km)
            planet_mass_kg: Planet mass (kg)
            
        Returns:
            Time to reach entry interface in seconds
        """
        # Average altitude for the descent
        avg_altitude = (orbit_altitude_km + entry_interface_km) / 2
        
        # Use half orbital period at average altitude as approximation
        # (actual descent is more complex, but this gives reasonable timing)
        return self.calculate_circularization_duration(
            avg_altitude, planet_radius_km, planet_mass_kg
        ) * 0.5  # Quarter orbit approximation
    
    # -------------------------------------------------------------------------
    # LANDING: Entry interface to surface
    # -------------------------------------------------------------------------
    def calculate_landing_duration(
        self,
        entry_interface_km: float,
        planet_gravity_gees: float,
        has_atmosphere: bool = True,
    ) -> float:
        """
        Calculate time from entry interface to landing.
        
        Rough approximation based on atmospheric entry and descent.
        
        Args:
            entry_interface_km: Entry interface altitude (km)
            planet_gravity_gees: Surface gravity in Earth g's
            has_atmosphere: Whether planet has atmosphere (affects descent profile)
            
        Returns:
            Time to land in seconds
        """
        # Entry interface in meters
        h = entry_interface_km * 1000
        
        # Surface gravity
        g = planet_gravity_gees * EARTH_G
        
        if has_atmosphere:
            # Atmospheric entry: longer due to aerobraking and parachute descent
            # Rough approximation: 10-15 minutes for Earth-like
            # Scale by gravity (higher g = faster descent)
            base_time = 600  # 10 minutes base
            return base_time / math.sqrt(planet_gravity_gees) if planet_gravity_gees > 0 else base_time
        else:
            # No atmosphere: powered descent
            # Time to fall distance h at constant deceleration
            # Assuming max decel of 2g for comfort
            a_decel = 2 * EARTH_G
            # t = √(2h/a) for constant deceleration from rest
            return math.sqrt(2 * h / a_decel)
    
    # -------------------------------------------------------------------------
    # TRANSFER (Hohmann): Half-period of transfer ellipse
    # -------------------------------------------------------------------------
    def calculate_transfer_duration(
        self,
        origin_orbit_au: float,
        dest_orbit_au: float,
        star_mass_kg: float,
    ) -> float:
        """
        Calculate Hohmann transfer time between two circular orbits.
        
        Formula: T_transfer/2 = π√(a³/μ)
        Where a = (r1 + r2) / 2 (semi-major axis of transfer ellipse)
        
        Args:
            origin_orbit_au: Origin orbit radius in AU
            dest_orbit_au: Destination orbit radius in AU
            star_mass_kg: Mass of central star (kg)
            
        Returns:
            Transfer time in seconds (half the transfer orbit period)
        """
        # Convert to meters
        r1 = origin_orbit_au * AU_IN_METERS
        r2 = dest_orbit_au * AU_IN_METERS
        
        # Semi-major axis of transfer ellipse
        a = (r1 + r2) / 2
        
        # Gravitational parameter of star
        mu = G * star_mass_kg
        
        # Transfer time = half period of transfer ellipse
        T_transfer = math.pi * math.sqrt(a**3 / mu)
        
        return T_transfer
    
    # -------------------------------------------------------------------------
    # Convenience method: Get duration for any NavigationEvent
    # -------------------------------------------------------------------------
    def get_maneuver_duration(
        self,
        maneuver_type: str,
        body_params: Dict[str, Any],
        nav_context: Dict[str, Any],
    ) -> float:
        """
        Calculate duration for a maneuver based on type and context.
        
        Args:
            maneuver_type: Type of maneuver (LAUNCH, CIRCULARIZE, etc.)
            body_params: Dict with planet/moon physical properties:
                - atmospheric_height_km
                - gravity_gees
                - radius_km
                - mass_kg
                - rotation_period_seconds
            nav_context: Navigation context with:
                - altitude_km (target orbit altitude)
                - origin_orbit_au, dest_orbit_au (for transfers)
                - distance_au (for sublight)
                
        Returns:
            Duration in seconds
        """
        maneuver = maneuver_type.upper()
        
        if maneuver in ["LAUNCH", "DIRECT_ASCENT"]:
            return self.calculate_launch_duration(
                atmospheric_height_km=body_params.get("atmospheric_height_km", 100),
                planet_gravity_gees=body_params.get("gravity_gees", 1.0),
                planet_radius_km=body_params.get("radius_km", 6371),
                rotation_period_seconds=body_params.get("rotation_period_seconds", 86400),
                launch_latitude_deg=nav_context.get("launch_latitude_deg", 0),
            )
        
        elif maneuver == "CIRCULARIZE":
            return self.calculate_circularization_duration(
                altitude_km=nav_context.get("altitude_km", 300),
                planet_radius_km=body_params.get("radius_km", 6371),
                planet_mass_kg=body_params.get("mass_kg", 5.97e24),
            )
        
        elif maneuver == "INSERTION":
            return self.calculate_insertion_duration(
                altitude_km=nav_context.get("altitude_km", 300),
                planet_radius_km=body_params.get("radius_km", 6371),
                planet_mass_kg=body_params.get("mass_kg", 5.97e24),
            )
        
        elif maneuver == "SUBLIGHT":
            return self.calculate_sublight_duration(
                distance_au=nav_context.get("distance_au", 1.0),
                velocity_c=nav_context.get("velocity_c", self.vehicle.sublight_velocity_c),
            )
        
        elif maneuver == "TRANSFER":
            return self.calculate_transfer_duration(
                origin_orbit_au=nav_context.get("origin_orbit_au", 1.0),
                dest_orbit_au=nav_context.get("dest_orbit_au", 1.5),
                star_mass_kg=nav_context.get("star_mass_kg", 1.989e30),
            )
        
        elif maneuver == "DEORBIT":
            return self.calculate_deorbit_duration(
                orbit_altitude_km=nav_context.get("orbit_altitude_km", 300),
                entry_interface_km=nav_context.get("entry_interface_km", 100),
                planet_radius_km=body_params.get("radius_km", 6371),
                planet_mass_kg=body_params.get("mass_kg", 5.97e24),
            )
        
        elif maneuver in ["LANDING", "DOCK"]:
            return self.calculate_landing_duration(
                entry_interface_km=nav_context.get("entry_interface_km", 100),
                planet_gravity_gees=body_params.get("gravity_gees", 1.0),
                has_atmosphere=body_params.get("has_atmosphere", True),
            )
        
        elif maneuver == "PLANE_CHANGE":
            # Plane changes are typically quick burns
            # Duration is mainly the burn time (seconds to minutes)
            return 60.0  # 1 minute placeholder
        
        else:
            # Default fallback
            return 30.0


# Singleton instance with default vehicle params
_default_service = None

def get_maneuver_physics_service(vehicle: Optional[VehicleParams] = None) -> ManeuverPhysicsService:
    """Get or create the ManeuverPhysicsService instance."""
    global _default_service
    if vehicle is not None:
        return ManeuverPhysicsService(vehicle)
    if _default_service is None:
        _default_service = ManeuverPhysicsService()
    return _default_service


