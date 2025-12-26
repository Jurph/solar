"""
Display formatting methods for celestial objects.
Moved from template JavaScript to model methods for proper separation of concerns.
"""
import math
from typing import Optional, Dict, Any


def format_number(num: Optional[float]) -> str:
    """Format a number with appropriate SI prefix."""
    if num is None:
        return 'N/A'
    if num >= 1e24:
        return f"{num / 1e24:.2f} Yg"
    if num >= 1e21:
        return f"{num / 1e21:.2f} Zg"
    if num >= 1e18:
        return f"{num / 1e18:.2f} Eg"
    if num >= 1e15:
        return f"{num / 1e15:.2f} Pg"
    if num >= 1e12:
        return f"{num / 1e12:.2f} Tg"
    if num >= 1e9:
        return f"{num / 1e9:.2f} Gg"
    if num >= 1e6:
        return f"{num / 1e6:.2f} Mg"
    if num >= 1e3:
        return f"{num / 1e3:.2f} kg"
    return f"{num:.2f}"


def format_distance_km(distance_km: Optional[float]) -> str:
    """Format a distance in kilometers with appropriate units."""
    if distance_km is None:
        return 'N/A'
    if distance_km >= 1e9:
        return f"{distance_km / 1e9:.2f} Gm"
    if distance_km >= 1e6:
        return f"{distance_km / 1e6:.2f} Mm"
    if distance_km >= 1e3:
        return f"{distance_km / 1e3:.2f} km"
    return f"{distance_km:.2f} km"


def format_temperature_k(temp_k: Optional[float]) -> str:
    """Format temperature in Kelvin with Celsius conversion."""
    if temp_k is None:
        return 'N/A'
    temp_c = temp_k - 273.15
    return f"{temp_k:.0f} K ({temp_c:.0f}°C)"


def format_orbital_period_days(period_days: Optional[float]) -> str:
    """Format orbital period in days with years conversion."""
    if period_days is None:
        return 'N/A'
    years = period_days / 365.25
    return f"{period_days:.2f} days ({years:.2f} years)"


def format_orbital_period_hours(period_hours: Optional[float]) -> str:
    """Format orbital period in hours with days conversion."""
    if period_hours is None:
        return 'N/A'
    days = period_hours / 24
    return f"{period_hours:.2f} hours ({days:.2f} days)"


def format_rotation_period_hours(period_hours: Optional[float]) -> str:
    """Format rotation period (day length) in hours with days conversion."""
    if period_hours is None:
        return 'N/A'
    days = period_hours / 24
    return f"{period_hours:.2f} hours ({days:.2f} days)"


def calculate_surface_gravity_ms2(mass_kg: Optional[float], radius_km: Optional[float]) -> Optional[float]:
    """
    Calculate surface gravity in m/s².
    Formula: g = GM/r²
    where G = 6.67430e-11 m³/(kg·s²), M = mass_kg, r = radius_m
    """
    if mass_kg is None or radius_km is None:
        return None
    G = 6.67430e-11  # Gravitational constant
    radius_m = radius_km * 1000
    return (G * mass_kg) / (radius_m ** 2)


def format_surface_gravity(gravity_ms2: Optional[float]) -> str:
    """Format surface gravity in m/s² with Earth g conversion."""
    if gravity_ms2 is None:
        return 'N/A'
    earth_g = 9.80665
    g_ratio = gravity_ms2 / earth_g
    return f"{gravity_ms2:.2f} m/s² ({g_ratio:.2f}g)"


def format_atmosphere_height(height_km: Optional[float]) -> str:
    """Format atmosphere height in kilometers."""
    if height_km is None:
        return 'N/A'
    return f"{height_km:.2f} km"


def calculate_escape_velocity_ms(mass_kg: Optional[float], radius_km: Optional[float]) -> Optional[float]:
    """
    Calculate escape velocity in m/s.
    Formula: v_escape = √(2GM/r)
    where G = 6.67430e-11 m³/(kg·s²), M = mass_kg, r = radius_m
    """
    if mass_kg is None or radius_km is None:
        return None
    G = 6.67430e-11  # Gravitational constant
    radius_m = radius_km * 1000
    return math.sqrt(2 * G * mass_kg / radius_m)


def format_escape_velocity(velocity_ms: Optional[float]) -> str:
    """Format escape velocity in m/s with km/s conversion and Earth comparison."""
    if velocity_ms is None:
        return 'N/A'
    velocity_kms = velocity_ms / 1000
    earth_escape_velocity_ms = 11186.0  # Earth's escape velocity in m/s
    earth_ratio = velocity_ms / earth_escape_velocity_ms
    return f"{velocity_kms:.2f} km/s ({earth_ratio:.2f}× Earth)"


def calculate_orbital_velocity_ms(mass_kg: Optional[float], radius_km: Optional[float]) -> Optional[float]:
    """
    Calculate orbital velocity at surface in m/s.
    Formula: v_orbital = √(GM/r)
    where G = 6.67430e-11 m³/(kg·s²), M = mass_kg, r = radius_m
    """
    if mass_kg is None or radius_km is None:
        return None
    G = 6.67430e-11  # Gravitational constant
    radius_m = radius_km * 1000
    return math.sqrt(G * mass_kg / radius_m)


def format_orbital_velocity(velocity_ms: Optional[float]) -> str:
    """Format orbital velocity in m/s with km/s conversion."""
    if velocity_ms is None:
        return 'N/A'
    velocity_kms = velocity_ms / 1000
    return f"{velocity_kms:.2f} km/s"


def get_atmosphere_data(body_instance, body_model_class) -> Dict[str, Any]:
    """
    Look up atmosphere data for a celestial body using ContentType.
    
    Args:
        body_instance: The concrete Planet or Moon instance
        body_model_class: The model class (Planet or Moon)
        
    Returns:
        Dict with keys: has_atmosphere, atmosphere_type, atmosphere_height_km,
                       surface_pressure_bar, scale_height_km
    """
    result = {
        'has_atmosphere': False,
        'atmosphere_type': None,
        'atmosphere_height_km': None,
        'surface_pressure_bar': None,
        'scale_height_km': None,
    }
    
    try:
        from django.contrib.contenttypes.models import ContentType
        from mysite.universe.models import Atmosphere
        
        content_type = ContentType.objects.get_for_model(body_model_class)
        atmosphere = Atmosphere.objects.get(content_type=content_type, object_id=body_instance.id)
        
        result['has_atmosphere'] = True
        result['atmosphere_type'] = atmosphere.atmosphere_type
        result['atmosphere_height_km'] = atmosphere.atmosphere_height_km
        result['surface_pressure_bar'] = atmosphere.surface_pressure_bar
        result['scale_height_km'] = atmosphere.scale_height_km
    except Exception:
        # Atmosphere doesn't exist or model not available
        pass
    
    return result


def get_surface_composition_hint(planet_type: Optional[str] = None, moon_type: Optional[str] = None, 
                                  density_kg_m3: Optional[float] = None) -> Optional[str]:
    """
    Derive surface composition hint from type and density.
    Returns a human-readable description of the surface.
    """
    # For planets
    if planet_type:
        if planet_type in ['GG', 'IG']:  # Gas Giant, Ice Giant
            return "No solid surface"
        elif planet_type == 'AB':  # Asteroid Belt
            return "Rocky fragments"
        elif planet_type in ['TE', 'SE', 'SI']:  # Terrestrial, Super-earth, Silicate
            if density_kg_m3:
                if density_kg_m3 > 5000:
                    return "Dense rocky surface"
                elif density_kg_m3 > 3000:
                    return "Rocky surface"
                else:
                    return "Light rocky/icy surface"
            return "Rocky surface"
        elif planet_type == 'CT':  # Cthonian
            return "Exposed rocky core"
        elif planet_type == 'MP':  # Mesoplanet
            return "Small rocky body"
    
    # For moons
    if moon_type:
        if moon_type == 'I':  # Icy
            return "Ice/water surface"
        elif moon_type == 'O':  # Organic
            if density_kg_m3 and density_kg_m3 < 2000:
                return "Ice/water surface with organic compounds"
            return "Organic-rich surface"
        elif moon_type == 'T':  # Terrestrial
            return "Earth-like surface (potentially habitable)"
        elif moon_type == 'R':  # Rocky
            if density_kg_m3:
                if density_kg_m3 > 4000:
                    return "Dense rocky surface"
                else:
                    return "Rocky surface"
            return "Rocky surface"
    
    return None

