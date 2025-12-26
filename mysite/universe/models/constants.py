"""
Constants for the universe module.

This module contains shared constants used across models, services, and views
to avoid magic strings and ensure consistency.
"""

# Type names returned by Location.get_type_name()
# These match the class names of the concrete Location subclasses
class TypeName:
    """Constants for celestial object type names."""
    GALAXY = "Galaxy"
    STAR_SYSTEM = "StarSystem"
    STAR = "Star"
    PLANET = "Planet"
    MOON = "Moon"
    STATION = "Station"
    
    # Grouped constants for common checks
    PLANETARY_BODIES = (PLANET, MOON)
    SURFACE_LOCATIONS = (PLANET, MOON, STATION)
    CELESTIAL_BODIES = (STAR, PLANET, MOON)
    LANDABLE = (PLANET, MOON)  # Bodies you can land on
    DOCKABLE = (STATION,)  # Bodies you can dock at


# Keywords used to identify control stations
CONTROL_STATION_KEYWORDS = ("Control", "Dispatch")


# Display names for type presentation
TYPE_DISPLAY_NAMES = {
    TypeName.GALAXY: "Galaxy",
    TypeName.STAR_SYSTEM: "Star System",
    TypeName.STAR: "Star",
    TypeName.PLANET: "Planet",
    TypeName.MOON: "Moon",
    TypeName.STATION: "Space Station",
}

