from typing import Optional, TYPE_CHECKING

from mysite.universe.models.event import NavigationEvent

if TYPE_CHECKING:
    from mysite.universe.models.celestial import PhysicalBody


def get_event_duration(service, event: NavigationEvent) -> float:
    """
    Returns the physics-based duration of a navigation event.

    This is considered part of route-building correctness (it affects pacing/scheduling),
    even though it delegates to a physics service for the actual computation.
    """
    from mysite.universe.services.maneuver_physics import get_maneuver_physics_service

    physics = get_maneuver_physics_service()
    maneuver_type = event.maneuver.value if hasattr(event.maneuver, "value") else str(event.maneuver)

    body = get_relevant_body_for_maneuver(service, event)
    body_params = extract_body_params(body) if body else {}
    nav_context = build_physics_nav_context(service, event, body)

    return physics.get_maneuver_duration(
        maneuver_type=maneuver_type,
        body_params=body_params,
        nav_context=nav_context,
    )


def get_relevant_body_for_maneuver(service, event: NavigationEvent) -> Optional["PhysicalBody"]:
    """
    Determine the relevant planet/moon for physics calculations.

    Rules:
    - Arrival maneuvers (DEORBIT, LANDING, DOCK, INSERTION): use destination/next
    - Departure maneuvers (LAUNCH, UNDOCK): use current/origin
    - Transfer maneuvers: use current/origin for departure calculations
    """
    from mysite.universe.models.celestial import Moon, Planet
    from mysite.universe.models.station import Station

    maneuver = event.maneuver.value.upper() if hasattr(event.maneuver, "value") else str(event.maneuver).upper()

    if maneuver in ["DEORBIT", "LANDING", "DOCK", "INSERTION"]:
        target_location = event.next or event.destination
    else:
        target_location = event.current or event.origin

    if not target_location:
        return None

    concrete = target_location.get_concrete_instance()

    if isinstance(concrete, (Planet, Moon)):
        return concrete

    if isinstance(concrete, Station) and concrete.orbits:
        parent = concrete.orbits.get_concrete_instance()
        if isinstance(parent, (Planet, Moon)):
            return parent

    return None


def extract_body_params(body) -> dict:
    """Extract physical parameters from a celestial body."""
    if body is None:
        return {}

    radius_km = getattr(body, "radius_km", None)
    mass_kg = getattr(body, "mass_kg", None)
    gravity_gees = getattr(body, "surface_gravity_gees", None)
    atmospheric_height_km = getattr(body, "atmospheric_height_km", None)
    rotation_period_seconds = getattr(body, "rotation_period_seconds", None)

    params = {
        "radius_km": radius_km if radius_km is not None else 6371.0,
        "mass_kg": mass_kg if mass_kg is not None else 5.97e24,
        "atmospheric_height_km": atmospheric_height_km if atmospheric_height_km is not None else 100.0,
        "rotation_period_seconds": rotation_period_seconds if rotation_period_seconds is not None else 86400.0,
        "has_atmosphere": (atmospheric_height_km or 0) > 0,
    }

    if gravity_gees is None:
        if params["mass_kg"] and params["radius_km"]:
            G = 6.67430e-11
            EARTH_G = 9.80665
            surface_g = (G * params["mass_kg"]) / ((params["radius_km"] * 1000) ** 2)
            params["gravity_gees"] = surface_g / EARTH_G
        else:
            params["gravity_gees"] = 1.0
    else:
        params["gravity_gees"] = gravity_gees

    return params


def build_physics_nav_context(service, event: NavigationEvent, body) -> dict:
    """Build navigation context for physics calculations."""
    from mysite.universe.models.celestial import Planet

    context = {
        "altitude_km": 300,
        "entry_interface_km": 100,
        "orbit_altitude_km": 300,
    }

    maneuver = event.maneuver.value.upper() if hasattr(event.maneuver, "value") else str(event.maneuver).upper()

    if maneuver in ["SUBLIGHT", "TRANSFER"]:
        context["velocity_c"] = 0.1

        origin_au = None
        dest_au = None

        if event.origin:
            origin_concrete = event.origin.get_concrete_instance()
            if isinstance(origin_concrete, Planet):
                origin_au = getattr(origin_concrete, "orbital_distance_au", None)

        if event.destination:
            dest_concrete = event.destination.get_concrete_instance()
            if isinstance(dest_concrete, Planet):
                dest_au = getattr(dest_concrete, "orbital_distance_au", None)

        if origin_au and dest_au:
            context["distance_au"] = abs(dest_au - origin_au)
            context["origin_orbit_au"] = origin_au
            context["dest_orbit_au"] = dest_au
        else:
            context["distance_au"] = 0.5

    elif maneuver == "HYPERSPACE":
        from mysite.universe.services.location_service import find_star_system_for_location
        
        origin_system = None
        dest_system = None

        if event.origin:
            origin_system = find_star_system_for_location(event.origin)

        if event.destination:
            dest_system = find_star_system_for_location(event.destination)

        context["velocity_c"] = 1000.0

        if origin_system and dest_system:
            from mysite.universe.services.location_service import get_distance_between_star_systems
            distance_ly = get_distance_between_star_systems(origin_system, dest_system)
            if distance_ly != float("inf"):
                context["distance_ly"] = distance_ly
            else:
                context["distance_ly"] = 10.0
        else:
            context["distance_ly"] = 10.0

    if body and hasattr(body, "get_leo_band_altitude_km"):
        try:
            context["altitude_km"] = body.get_leo_band_altitude_km()
        except Exception:
            pass

    return context


