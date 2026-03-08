"""
Service for location and celestial body queries.

Provides utility functions for querying and navigating the location hierarchy,
finding subordinate bodies, calculating distances, and working with planets, moons, stars, and stations.
"""

import math
from typing import List, Optional, Tuple
from mysite.universe.models.base import Location
from mysite.universe.models.celestial import Planet, Moon, Star, StarSystem
from mysite.universe.models.station import Station


def get_subordinate_bodies(
    location: Optional[Location] = None, location_name: Optional[str] = None
) -> List[Location]:
    """
    Get planets, moons, or stations that are subordinate to a given location.

    For a location near a planet: returns the planet, its moons, and orbiting stations
    For a location near a moon: returns the moon, its parent planet, sibling moons, and stations
    For a location near a star: returns planets in that system, their moons, and stations

    Args:
        location: The Location object to find subordinate bodies for
        location_name: Alternative: name of the location to look up

    Returns:
        List of Location objects (Planets, Moons, Stations) that are subordinate to the given location

    Examples:
        >>> # Get bodies subordinate to a planet
        >>> mars = Location.objects.get(name="Mars")
        >>> bodies = get_subordinate_bodies(location=mars)
        >>> # Returns: [Mars, Phobos, Deimos, ...stations orbiting Mars...]

        >>> # Get bodies subordinate to a star
        >>> sol = Location.objects.get(name="Sol")
        >>> bodies = get_subordinate_bodies(location=sol)
        >>> # Returns: [Mercury, Venus, Earth, Luna, Mars, ...all planets and moons...]
    """
    subordinate_bodies = []

    # Resolve location from name if needed
    if location is None and location_name:
        try:
            location = Location.objects.get(name=location_name)
        except Location.DoesNotExist:
            pass

    # If we have a location, find subordinate bodies
    if location:
        concrete = location.get_concrete_instance()

        # If location is a planet
        if isinstance(concrete, Planet):
            # Add the planet itself
            subordinate_bodies.append(concrete)
            # Add its moons
            subordinate_bodies.extend(Moon.objects.filter(orbits=location))
            # Add stations orbiting this planet
            subordinate_bodies.extend(Station.objects.filter(orbits=location))

        # If location is a moon
        elif isinstance(concrete, Moon):
            # Add the moon itself
            subordinate_bodies.append(concrete)
            # Add the parent planet if it exists
            if concrete.orbits:
                parent = concrete.orbits.get_concrete_instance()
                if isinstance(parent, Planet):
                    subordinate_bodies.append(parent)
            # Add other moons of the same parent
            if concrete.orbits:
                subordinate_bodies.extend(
                    Moon.objects.filter(orbits=concrete.orbits).exclude(pk=concrete.pk)
                )
            # Add stations orbiting this moon
            subordinate_bodies.extend(Station.objects.filter(orbits=location))

        # If location is a star
        elif isinstance(concrete, Star):
            # Add all planets orbiting this star
            subordinate_bodies.extend(Planet.objects.filter(orbits=location))
            # For each planet, add its moons
            for planet in Planet.objects.filter(orbits=location):
                subordinate_bodies.extend(Moon.objects.filter(orbits=planet))
            # Add stations orbiting planets in this system
            for planet in Planet.objects.filter(orbits=location):
                subordinate_bodies.extend(Station.objects.filter(orbits=planet))

        # If location is a StarSystem
        elif isinstance(concrete, StarSystem):
            # Find the star(s) in this system
            stars = Star.objects.filter(orbits=location)
            # For each star, add all planets orbiting it
            for star in stars:
                planets = Planet.objects.filter(orbits=star)
                subordinate_bodies.extend(planets)
                # For each planet, add its moons
                for planet in planets:
                    subordinate_bodies.extend(Moon.objects.filter(orbits=planet))
                # Add stations orbiting planets in this system
                for planet in planets:
                    subordinate_bodies.extend(Station.objects.filter(orbits=planet))

    # No fallback - if no location found, return empty list
    # This prevents satellites from reporting hazards in wrong systems
    return subordinate_bodies


def get_distance_between(
    location1: Location, location2: Location
) -> Tuple[Optional[float], str]:
    """
    Calculate distance between two locations.

    Handles all cases:
    - Different star systems: distance between star systems in light-years
    - Same star system, different planets: distance between planets in AU
    - Same parent body: triangular distance based on orbital distances and 60° separation

    Args:
        location1: First location
        location2: Second location

    Returns:
        Tuple of (distance_value, unit_string) where:
        - distance_value: Distance as float, or None if cannot calculate
        - unit_string: Unit name ("ly", "au", "km", or "unknown")

    Examples:
        >>> sol = Location.objects.get(name="Sol")
        >>> alpha_centauri = Location.objects.get(name="Alpha Centauri")
        >>> distance, unit = get_distance_between(sol, alpha_centauri)
        >>> # Returns: (4.37, "ly")

        >>> earth = Location.objects.get(name="Earth")
        >>> mars = Location.objects.get(name="Mars")
        >>> distance, unit = get_distance_between(earth, mars)
        >>> # Returns: (0.52, "au")  # approximate
    """
    concrete1 = location1.get_concrete_instance()
    concrete2 = location2.get_concrete_instance()

    # Same object: distance is zero
    if location1 == location2:
        return (0.0, "km")

    # StarSystem to StarSystem: use galactic coordinates
    if isinstance(concrete1, StarSystem) and isinstance(concrete2, StarSystem):
        distance_ly = get_distance_between_star_systems(concrete1, concrete2)
        if distance_ly != float("inf"):
            return (distance_ly, "ly")
        return (None, "ly")

    # Find star systems for both locations
    system1 = find_star_system_for_location(location1)
    system2 = find_star_system_for_location(location2)

    # Different star systems: return distance between star systems
    if system1 and system2 and system1 != system2:
        distance_ly = get_distance_between_star_systems(system1, system2)
        if distance_ly != float("inf"):
            return (distance_ly, "ly")
        return (None, "ly")

    # Same star system (or one/both don't have a system): calculate within-system distance
    # Find what each location orbits
    parent1 = _get_orbital_parent(concrete1)
    parent2 = _get_orbital_parent(concrete2)

    # If one location IS the parent of the other, return orbital distance
    if parent1 == location2:
        # location1 orbits location2, so return location1's distance from its parent
        orbital_dist = _get_orbital_distance_from_parent(concrete1, parent1)
        if orbital_dist is not None:
            return (orbital_dist, "au")
    if parent2 == location1:
        # location2 orbits location1, so return location2's distance from its parent
        orbital_dist = _get_orbital_distance_from_parent(concrete2, parent2)
        if orbital_dist is not None:
            return (orbital_dist, "au")

    # Special case: Planet to Planet (same star system) - use orbital positions
    if isinstance(concrete1, Planet) and isinstance(concrete2, Planet):
        if parent1 and parent2 and parent1 == parent2:
            # Both orbit the same star - use orbital positions
            dist1_au = getattr(concrete1, "orbital_distance_au", None)
            dist2_au = getattr(concrete2, "orbital_distance_au", None)
            if dist1_au is not None and dist2_au is not None:
                distance_au = _calculate_planet_to_planet_distance(
                    concrete1, concrete2, dist1_au, dist2_au
                )
                if distance_au is not None:
                    return (distance_au, "au")

    # If they orbit the same parent, calculate triangular distance (for moons, stations, etc.)
    if parent1 and parent2 and parent1 == parent2:
        return _calculate_same_parent_distance(concrete1, concrete2, parent1)

    # If they orbit different parents, recursively find distance between parents
    # and add the orbital distances of the locations from their parents
    if parent1 and parent2 and parent1 != parent2:
        # Special case: If one location is a Station/Moon and the other is a Planet,
        # calculate distance between the Station/Moon's parent and the Planet directly
        if isinstance(concrete1, (Station, Moon)) and isinstance(concrete2, Planet):
            # Station/Moon orbits parent1, Planet is location2
            # Calculate distance between parent1 and location2, then add orbital altitude
            parent_distance, unit = get_distance_between(parent1, location2)
            if parent_distance is not None:
                loc1_orbital = _get_orbital_distance_from_parent(concrete1, parent1)
                if loc1_orbital is not None and unit == "au":
                    return (parent_distance + loc1_orbital, unit)
                return (parent_distance, unit)
        elif isinstance(concrete2, (Station, Moon)) and isinstance(concrete1, Planet):
            # Station/Moon orbits parent2, Planet is location1
            # Calculate distance between location1 and parent2, then add orbital altitude
            parent_distance, unit = get_distance_between(location1, parent2)
            if parent_distance is not None:
                loc2_orbital = _get_orbital_distance_from_parent(concrete2, parent2)
                if loc2_orbital is not None and unit == "au":
                    return (parent_distance + loc2_orbital, unit)
                return (parent_distance, unit)

        # Special case: Moon to Moon (or Station to Station) with different parent planets
        # Calculate distance between parent planets, then add both orbital distances
        if isinstance(concrete1, (Station, Moon)) and isinstance(
            concrete2, (Station, Moon)
        ):
            parent_distance, unit = get_distance_between(parent1, parent2)
            if parent_distance is not None:
                loc1_orbital = _get_orbital_distance_from_parent(concrete1, parent1)
                loc2_orbital = _get_orbital_distance_from_parent(concrete2, parent2)
                total_distance = parent_distance
                if loc1_orbital is not None and unit == "au":
                    total_distance += loc1_orbital
                elif loc1_orbital is not None and unit == "ly":
                    total_distance += loc1_orbital / 63241.0
                if loc2_orbital is not None and unit == "au":
                    total_distance += loc2_orbital
                elif loc2_orbital is not None and unit == "ly":
                    total_distance += loc2_orbital / 63241.0
                return (total_distance, unit)

        # General case: calculate distance between parents and add orbital distances
        parent_distance, unit = get_distance_between(parent1, parent2)
        if parent_distance is not None:
            # Add orbital distances from locations to their parents
            loc1_orbital = _get_orbital_distance_from_parent(concrete1, parent1)
            loc2_orbital = _get_orbital_distance_from_parent(concrete2, parent2)

            # For Planets/Moons, their orbital distance from parent is already accounted for
            # in the parent_distance calculation, so we only add orbital distances for
            # Stations and other small objects that orbit planets/moons
            total_distance = parent_distance
            if loc1_orbital is not None:
                # Only add if location1 is a Station (tiny orbital altitude)
                if isinstance(concrete1, Station):
                    if unit == "au":
                        total_distance += loc1_orbital
                    elif unit == "ly":
                        # Convert AU to light-years (1 ly ≈ 63241 AU)
                        total_distance += loc1_orbital / 63241.0
            if loc2_orbital is not None:
                # Only add if location2 is a Station (tiny orbital altitude)
                if isinstance(concrete2, Station):
                    if unit == "au":
                        total_distance += loc2_orbital
                    elif unit == "ly":
                        total_distance += loc2_orbital / 63241.0

            return (total_distance, unit)

    # Fallback: try to get orbital distances and approximate
    dist1_au = get_orbital_distance_au(location1)
    dist2_au = get_orbital_distance_au(location2)
    if dist1_au is not None and dist2_au is not None:
        # Simple approximation: difference in orbital distances
        distance_au = abs(dist2_au - dist1_au)
        return (distance_au, "au")

    # Default: unknown distance
    return (None, "unknown")


def _calculate_planet_to_planet_distance(
    planet1: Planet, planet2: Planet, dist1_au: float, dist2_au: float
) -> Optional[float]:
    """
    Calculate distance between two planets using their actual orbital positions.

    Uses system_age and orbital_period to determine current positions, then
    applies law of cosines with the angle between them.

    Args:
        planet1: First Planet instance
        planet2: Second Planet instance
        dist1_au: Orbital distance of planet1 in AU
        dist2_au: Orbital distance of planet2 in AU

    Returns:
        Distance in AU, or None if cannot calculate
    """
    # Get system age from the star system
    star = planet1.orbits if hasattr(planet1, "orbits") else None
    if not star:
        return None

    system = star.orbits if hasattr(star, "orbits") else None
    if not system or not isinstance(system, StarSystem):
        return None

    system_age_years = getattr(system, "system_age_years", None)
    if system_age_years is None:
        # Fallback: use simple difference if no system age
        return abs(dist2_au - dist1_au)

    # Get orbital periods
    period1_days = getattr(planet1, "orbital_period_days", None)
    period2_days = getattr(planet2, "orbital_period_days", None)

    if period1_days is None or period2_days is None:
        # Fallback: use simple difference if no periods
        return abs(dist2_au - dist1_au)

    # Calculate current orbital positions (solar angles)
    # Formula: angle = (system_age / orbital_period_years) % 1.0 * 360.0
    period1_years = period1_days / 365.25
    period2_years = period2_days / 365.25

    angle1_deg = (system_age_years / period1_years) % 1.0 * 360.0
    angle2_deg = (system_age_years / period2_years) % 1.0 * 360.0

    # Calculate angle difference
    angle_diff_deg = abs(angle2_deg - angle1_deg)
    # Take the smaller angle (planets could be 350° apart or 10° apart)
    if angle_diff_deg > 180.0:
        angle_diff_deg = 360.0 - angle_diff_deg

    # Law of cosines: c² = a² + b² - 2ab*cos(C)
    angle_diff_rad = math.radians(angle_diff_deg)
    cos_angle = math.cos(angle_diff_rad)

    distance_squared = dist1_au**2 + dist2_au**2 - 2 * dist1_au * dist2_au * cos_angle
    distance_au = math.sqrt(distance_squared)

    return distance_au


def _get_orbital_parent(location) -> Optional[Location]:
    """
    Get the Location that this location orbits.

    Args:
        location: Location instance (concrete)

    Returns:
        Parent Location if it exists, None otherwise
    """
    if hasattr(location, "orbits") and location.orbits:
        return location.orbits
    return None


def _get_orbital_distance_from_parent(location, parent: Location) -> Optional[float]:
    """
    Get the orbital distance of a location from its parent, in AU.

    For Stations, this is typically a small orbital altitude.
    For Planets/Moons, this is their orbital_distance_au.

    Args:
        location: Location instance (concrete)
        parent: The parent Location it orbits

    Returns:
        Orbital distance in AU, or None if not available
    """
    # For Planets and Moons, use their orbital_distance_au
    if isinstance(location, (Planet, Moon)):
        if (
            hasattr(location, "orbital_distance_au")
            and location.orbital_distance_au is not None
        ):
            return location.orbital_distance_au
        elif (
            hasattr(location, "orbital_distance_km")
            and location.orbital_distance_km is not None
        ):
            # Convert km to AU (1 AU ≈ 1.496e8 km)
            return location.orbital_distance_km / 1.496e8

    # For Stations, use their orbital_distance_km field if available
    if isinstance(location, Station):
        # First, check if Station has orbital_distance_km set
        if (
            hasattr(location, "orbital_distance_km")
            and location.orbital_distance_km is not None
        ):
            # Convert km to AU (1 AU ≈ 1.496e8 km)
            return location.orbital_distance_km / 1.496e8

        # Fallback: estimate based on parent body's orbital zones
        if parent and hasattr(parent, "get_min_safe_orbit_km"):
            try:
                min_orbit_km = parent.get_min_safe_orbit_km()
                # Add a typical station altitude (e.g., 300 km above minimum)
                station_altitude_km = min_orbit_km + 300.0
                return station_altitude_km / 1.496e8  # Convert to AU
            except Exception:
                pass

        # Last resort: use default LEO altitude (~400 km)
        return 400.0 / 1.496e8  # ~400 km in AU

    return None


def _calculate_same_parent_distance(
    location1, location2, parent: Location
) -> Tuple[Optional[float], str]:
    """
    Calculate distance between two locations that orbit the same parent.

    Assumes 60-degree separation and uses law of cosines:
    c² = a² + b² - 2ab*cos(C)
    where a and b are orbital distances, C is 60 degrees

    Args:
        location1: First location (concrete instance)
        location2: Second location (concrete instance)
        parent: The parent Location they both orbit

    Returns:
        Tuple of (distance_value, unit_string)
    """
    # Get orbital distances from the locations themselves
    dist1_au = None
    dist2_au = None

    # Try to get orbital distance for location1
    if (
        hasattr(location1, "orbital_distance_au")
        and location1.orbital_distance_au is not None
    ):
        dist1_au = location1.orbital_distance_au
    elif (
        hasattr(location1, "orbital_distance_km")
        and location1.orbital_distance_km is not None
    ):
        # Convert km to AU (1 AU ≈ 1.496e8 km)
        dist1_au = location1.orbital_distance_km / 1.496e8

    # Try to get orbital distance for location2
    if (
        hasattr(location2, "orbital_distance_au")
        and location2.orbital_distance_au is not None
    ):
        dist2_au = location2.orbital_distance_au
    elif (
        hasattr(location2, "orbital_distance_km")
        and location2.orbital_distance_km is not None
    ):
        # Convert km to AU (1 AU ≈ 1.496e8 km)
        dist2_au = location2.orbital_distance_km / 1.496e8

    # If we have both distances, calculate triangular distance
    if dist1_au is not None and dist2_au is not None:
        # Law of cosines: c² = a² + b² - 2ab*cos(60°)
        # cos(60°) = 0.5
        angle_rad = math.radians(60.0)
        cos_angle = math.cos(angle_rad)

        distance_squared = (
            dist1_au**2 + dist2_au**2 - 2 * dist1_au * dist2_au * cos_angle
        )
        distance_au = math.sqrt(distance_squared)

        return (distance_au, "au")

    # If we only have one distance or neither, return None
    return (None, "au")


def get_distance_between_star_systems(
    system1: StarSystem, system2: StarSystem
) -> float:
    """
    Calculate distance between two StarSystem instances in light-years.

    Uses Euclidean distance: sqrt((x2-x1)² + (y2-y1)² + (z2-z1)²)

    Args:
        system1: First StarSystem instance
        system2: Second StarSystem instance

    Returns:
        Distance in light-years, or float('inf') if coordinates are missing

    Examples:
        >>> sol = StarSystem.objects.get(name="Sol")
        >>> alpha_centauri = StarSystem.objects.get(name="Alpha Centauri")
        >>> distance = get_distance_between_star_systems(sol, alpha_centauri)
        >>> # Returns: 4.37 (approximately)
    """
    if not all(
        [
            system1.galactic_x_ly is not None,
            system1.galactic_y_ly is not None,
            system1.galactic_z_ly is not None,
        ]
    ):
        return float("inf")
    if not all(
        [
            system2.galactic_x_ly is not None,
            system2.galactic_y_ly is not None,
            system2.galactic_z_ly is not None,
        ]
    ):
        return float("inf")

    dx = system2.galactic_x_ly - system1.galactic_x_ly
    dy = system2.galactic_y_ly - system1.galactic_y_ly
    dz = system2.galactic_z_ly - system1.galactic_z_ly

    return math.sqrt(dx * dx + dy * dy + dz * dz)


def get_orbital_distance_au(location: Location) -> Optional[float]:
    """
    Get the orbital distance in AU for a planet or moon.

    Args:
        location: Location (should be a Planet or Moon)

    Returns:
        Orbital distance in AU, or None if not applicable or not available
    """
    concrete = location.get_concrete_instance()
    if isinstance(concrete, (Planet, Moon)):
        return getattr(concrete, "orbital_distance_au", None)
    return None


def calculate_station_orbit(
    station: Station, parent_body: Location
) -> tuple[float, str]:
    """
    Calculate the best orbital distance and type for a station orbiting a given body.

    Tries orbit types in order: GEO → HALF_GEO → L4 → LOW → CUSTOM (fallback).

    The GEO and HALF_GEO orbits are validated against:
    - The parent body's Hill sphere radius (must be inside it)
    - The parent body's minimum safe orbit altitude (must be above it)

    L4 is only offered for Planets with at least one moon; the Trojan point
    distance equals the most massive moon's orbital distance.

    Args:
        station: The Station whose orbit is being calculated (unused except for
            typing; the function is pure given parent_body).
        parent_body: The Location (Planet or Moon) the station orbits.

    Returns:
        Tuple of (orbital_distance_km, orbit_type_code) where orbit_type_code is
        one of: "GEO", "HALF_GEO", "L4", "LOW", "CUSTOM".
    """
    AU_KM = 1.496e8  # km per AU

    concrete = parent_body.get_concrete_instance()

    # --- Hill sphere radius --------------------------------------------------
    hill_sphere_km: Optional[float] = None
    if isinstance(concrete, Planet) and concrete.mass_kg and concrete.orbits:
        star = concrete.orbits.get_concrete_instance()
        if (
            isinstance(star, Star)
            and star.mass_kg
            and getattr(concrete, "orbital_distance_au", None)
        ):
            a_km = concrete.orbital_distance_au * AU_KM
            hill_sphere_km = a_km * (concrete.mass_kg / (3.0 * star.mass_kg)) ** (
                1.0 / 3.0
            )
    elif isinstance(concrete, Moon) and concrete.mass_kg and concrete.orbits:
        planet = concrete.orbits.get_concrete_instance()
        if (
            isinstance(planet, Planet)
            and planet.mass_kg
            and getattr(concrete, "orbital_distance_km", None)
        ):
            hill_sphere_km = concrete.orbital_distance_km * (
                concrete.mass_kg / (3.0 * planet.mass_kg)
            ) ** (1.0 / 3.0)

    # --- Minimum safe orbit altitude -----------------------------------------
    min_safe_km: Optional[float] = None
    if hasattr(concrete, "get_min_safe_orbit_km"):
        try:
            min_safe_km = concrete.get_min_safe_orbit_km()
        except Exception:
            pass

    def _above_min(alt_km: float) -> bool:
        return min_safe_km is None or alt_km > min_safe_km

    def _inside_hill(alt_km: float) -> bool:
        return hill_sphere_km is None or alt_km < hill_sphere_km

    # --- GEO / HALF_GEO ------------------------------------------------------
    if hasattr(concrete, "get_geostationary_altitude_km"):
        geo_km = concrete.get_geostationary_altitude_km()
        if geo_km is not None and geo_km > 0:
            if _above_min(geo_km) and _inside_hill(geo_km):
                return (round(geo_km), "GEO")
            half_geo_km = geo_km / 2.0
            if _above_min(half_geo_km) and _inside_hill(half_geo_km):
                return (round(half_geo_km), "HALF_GEO")

    # --- L4 Lagrange (planets with moons only) -------------------------------
    if isinstance(concrete, Planet):
        moons = Moon.objects.filter(orbits=parent_body)
        if moons.exists():
            best_moon = moons.filter(mass_kg__isnull=False).order_by("-mass_kg").first()
            if best_moon is None:
                best_moon = moons.first()
            if best_moon and getattr(best_moon, "orbital_distance_km", None):
                l4_km = best_moon.orbital_distance_km
                if _above_min(l4_km) and _inside_hill(l4_km):
                    return (round(l4_km), "L4")

    # --- LOW orbit -----------------------------------------------------------
    if hasattr(concrete, "get_low_orbit_altitude_km"):
        try:
            low_km = concrete.get_low_orbit_altitude_km()
            if low_km is not None and low_km > 0:
                return (round(low_km), "LOW")
        except Exception:
            pass

    # --- CUSTOM fallback -----------------------------------------------------
    if min_safe_km is not None:
        return (round(min_safe_km + 200.0), "CUSTOM")
    return (400, "CUSTOM")


def find_star_system_for_location(location: Location) -> Optional[StarSystem]:
    """
    Find the StarSystem that contains a given location.

    Traverses up the orbital hierarchy to find the parent StarSystem.

    Args:
        location: Any Location (Planet, Moon, Star, Station, etc.)

    Returns:
        StarSystem instance if found, None otherwise

    Examples:
        >>> earth = Location.objects.get(name="Earth")
        >>> system = find_star_system_for_location(earth)
        >>> # Returns: StarSystem(name="Sol")
    """
    concrete = location.get_concrete_instance()
    current = concrete

    while current:
        if isinstance(current, StarSystem):
            return current
        if hasattr(current, "orbits") and current.orbits:
            current = current.orbits.get_concrete_instance()
        else:
            break

    return None
