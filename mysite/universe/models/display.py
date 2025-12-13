"""
Display formatting methods for celestial objects.
Moved from template JavaScript to model methods for proper separation of concerns.
"""
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

