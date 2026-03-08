"""
Serializers for converting model instances to presentation-ready dictionaries.

These serializers handle:
- Raw value extraction from models
- Calculated physics values (gravity, escape velocity, etc.)
- Formatted display strings
- Atmosphere lookups

The output is suitable for JSON responses (baseball cards, API endpoints)
and could also feed future renderers (e.g., procedural planet visualization).
"""

from typing import Any, Dict, Optional

from mysite.universe.models import display
from mysite.universe.models.constants import TYPE_DISPLAY_NAMES
from mysite.universe.models import Galaxy, StarSystem, Star, Planet, Moon, Station


class BaseSerializer:
    """Base serializer with common functionality."""

    def __init__(self, instance):
        self.instance = instance
        self.concrete = (
            instance.get_concrete_instance()
            if hasattr(instance, "get_concrete_instance")
            else instance
        )

    def get_base_details(self) -> Dict[str, Any]:
        """Return common fields shared by all object types."""
        type_name = (
            self.instance.get_type_name()
            if hasattr(self.instance, "get_type_name")
            else self.instance.__class__.__name__
        )
        return {
            "name": self.instance.name,
            "type": TYPE_DISPLAY_NAMES.get(type_name, type_name),
            "type_code": type_name,
            "scale": getattr(self.instance, "scale", None),
        }

    def serialize(self) -> Dict[str, Any]:
        """Serialize the instance to a dictionary. Override in subclasses."""
        return self.get_base_details()


class GalaxySerializer(BaseSerializer):
    """Serializer for Galaxy objects."""

    def serialize(self) -> Dict[str, Any]:
        details = self.get_base_details()

        galaxy_type_display = self._get_choice_display("galaxy_type")
        galaxy_size_display = self._get_choice_display("galaxy_size")

        details.update(
            {
                "galaxy_type": galaxy_type_display,
                "galaxy_size": galaxy_size_display,
            }
        )
        return details

    def _get_choice_display(self, field_name: str) -> Optional[str]:
        """Get display value for a Django choice field."""
        if not hasattr(self.concrete, field_name):
            return None

        display_method = f"get_{field_name}_display"
        if hasattr(self.concrete, display_method):
            try:
                return getattr(self.concrete, display_method)()
            except (AttributeError, ValueError):
                pass
        return getattr(self.concrete, field_name)


class StarSystemSerializer(BaseSerializer):
    """Serializer for StarSystem objects."""

    def serialize(self) -> Dict[str, Any]:
        details = self.get_base_details()
        details.update(
            {
                "system_age_years": getattr(self.concrete, "system_age_years", None),
            }
        )
        return details


class StarSerializer(BaseSerializer):
    """Serializer for Star objects."""

    def serialize(self) -> Dict[str, Any]:
        details = self.get_base_details()

        star_magnitude = getattr(self.concrete, "star_magnitude", None)

        details.update(
            {
                "star_type": getattr(self.concrete, "star_type", None),
                "star_magnitude": float(star_magnitude) if star_magnitude else None,
                "temperature_k": getattr(self.concrete, "temperature_k", None),
                "mass_kg": getattr(self.concrete, "mass_kg", None),
                "mass_solar": getattr(self.concrete, "mass_solar", None),
                "radius_km": getattr(self.concrete, "radius_km", None),
                "radius_solar": getattr(self.concrete, "radius_solar", None),
            }
        )
        return details


class PhysicalBodySerializer(BaseSerializer):
    """
    Base serializer for physical bodies (Planet, Moon).

    Handles common calculations like surface gravity, escape velocity,
    orbital velocity, and atmosphere data.
    """

    def _get_physical_properties(self) -> Dict[str, Any]:
        """Extract and calculate physical properties."""
        mass_kg = getattr(self.concrete, "mass_kg", None)
        radius_km = getattr(self.concrete, "radius_km", None)
        density_kg_m3 = getattr(self.concrete, "density_kg_m3", None)

        # Calculate derived values
        surface_gravity_ms2 = display.calculate_surface_gravity_ms2(mass_kg, radius_km)
        escape_velocity_ms = display.calculate_escape_velocity_ms(mass_kg, radius_km)
        orbital_velocity_ms = display.calculate_orbital_velocity_ms(mass_kg, radius_km)

        return {
            "mass_kg": mass_kg,
            "mass_formatted": display.format_number(mass_kg),
            "radius_km": radius_km,
            "radius_formatted": display.format_distance_km(radius_km),
            "density_kg_m3": density_kg_m3,
            "density_formatted": f"{density_kg_m3:.0f} kg/m³"
            if density_kg_m3
            else "N/A",
            "surface_gravity_ms2": surface_gravity_ms2,
            "surface_gravity_formatted": display.format_surface_gravity(
                surface_gravity_ms2
            ),
            "escape_velocity_ms": escape_velocity_ms,
            "escape_velocity_formatted": display.format_escape_velocity(
                escape_velocity_ms
            ),
            "orbital_velocity_ms": orbital_velocity_ms,
            "orbital_velocity_formatted": display.format_orbital_velocity(
                orbital_velocity_ms
            ),
        }

    def _get_thermal_properties(self) -> Dict[str, Any]:
        """Extract thermal properties."""
        albedo = getattr(self.concrete, "albedo", None)
        equilibrium_temperature_k = getattr(
            self.concrete, "equilibrium_temperature_k", None
        )

        return {
            "albedo": albedo,
            "albedo_formatted": f"{albedo:.3f}" if albedo is not None else "N/A",
            "equilibrium_temperature_k": equilibrium_temperature_k,
            "equilibrium_temperature_formatted": display.format_temperature_k(
                equilibrium_temperature_k
            ),
        }

    def _get_rotation_properties(self) -> Dict[str, Any]:
        """Extract rotation properties."""
        rotation_period_hours = getattr(self.concrete, "rotation_period_hours", None)
        axial_tilt_deg = getattr(self.concrete, "axial_tilt_deg", None)
        is_tidally_locked = getattr(self.concrete, "is_tidally_locked", None)

        return {
            "rotation_period_hours": rotation_period_hours,
            "rotation_period_formatted": display.format_rotation_period_hours(
                rotation_period_hours
            ),
            "axial_tilt_deg": axial_tilt_deg,
            "axial_tilt_formatted": f"{axial_tilt_deg:.2f}°"
            if axial_tilt_deg is not None
            else "N/A",
            "is_tidally_locked": is_tidally_locked,
        }

    def _get_atmosphere_properties(self, model_class) -> Dict[str, Any]:
        """Extract atmosphere properties using the display utility."""
        atmo_data = display.get_atmosphere_data(self.concrete, model_class)

        return {
            "has_atmosphere": atmo_data["has_atmosphere"],
            "atmosphere_type": atmo_data["atmosphere_type"],
            "atmosphere_height_km": atmo_data["atmosphere_height_km"],
            "atmosphere_height_formatted": display.format_atmosphere_height(
                atmo_data["atmosphere_height_km"]
            ),
            "scale_height_km": atmo_data["scale_height_km"],
            "scale_height_formatted": display.format_atmosphere_height(
                atmo_data["scale_height_km"]
            ),
            "surface_pressure_bar": atmo_data["surface_pressure_bar"],
            "surface_pressure_formatted": (
                f"{atmo_data['surface_pressure_bar']:.3f} bar"
                if atmo_data["surface_pressure_bar"] is not None
                else "N/A"
            ),
        }


class PlanetSerializer(PhysicalBodySerializer):
    """Serializer for Planet objects."""

    def serialize(self) -> Dict[str, Any]:
        details = self.get_base_details()

        # Planet type
        planet_type_display = self._get_type_display()

        # Parent body (star)
        parent_body_name, parent_body_type = self._get_parent_body()

        # Orbital properties
        orbital_props = self._get_orbital_properties()

        # Surface composition hint
        density_kg_m3 = getattr(self.concrete, "density_kg_m3", None)
        surface_composition = display.get_surface_composition_hint(
            planet_type=getattr(self.concrete, "planet_type", None),
            density_kg_m3=density_kg_m3,
        )

        details.update(
            {
                "planet_type": planet_type_display,
                "planet_type_code": getattr(self.concrete, "planet_type", None),
                "parent_body_name": parent_body_name,
                "parent_body_type": parent_body_type,
                "surface_composition": surface_composition,
            }
        )

        # Add all property groups
        details.update(self._get_physical_properties())
        details.update(self._get_thermal_properties())
        details.update(orbital_props)
        details.update(self._get_rotation_properties())
        details.update(self._get_atmosphere_properties(Planet))

        return details

    def _get_type_display(self) -> Optional[str]:
        """Get planet type display value."""
        if not hasattr(self.concrete, "planet_type"):
            return None

        if hasattr(self.concrete, "get_planet_type_display"):
            try:
                return self.concrete.get_planet_type_display()
            except (AttributeError, ValueError):
                pass
        return self.concrete.planet_type

    def _get_parent_body(self) -> tuple:
        """Get parent body (star) information."""
        parent_body_name = None
        parent_body_type = None

        try:
            if hasattr(self.concrete, "orbits"):
                parent_star = self.concrete.orbits
                parent_body_name = parent_star.name
                if hasattr(parent_star, "star_type"):
                    parent_body_type = (
                        parent_star.get_star_type_display()
                        if hasattr(parent_star, "get_star_type_display")
                        else parent_star.star_type
                    )
        except Exception:
            pass  # Parent body lookup failed silently

        return parent_body_name, parent_body_type

    def _get_orbital_properties(self) -> Dict[str, Any]:
        """Get planet orbital properties."""
        orbital_distance_au = getattr(self.concrete, "orbital_distance_au", None)
        orbital_period_days = getattr(self.concrete, "orbital_period_days", None)
        orbital_eccentricity = getattr(self.concrete, "orbital_eccentricity", None)
        orbital_inclination_deg = getattr(
            self.concrete, "orbital_inclination_deg", None
        )

        return {
            "orbital_distance_au": orbital_distance_au,
            "orbital_period_days": orbital_period_days,
            "orbital_period_formatted": display.format_orbital_period_days(
                orbital_period_days
            ),
            "orbital_eccentricity": orbital_eccentricity,
            "orbital_eccentricity_formatted": (
                f"{orbital_eccentricity:.3f}"
                if orbital_eccentricity is not None
                else "N/A"
            ),
            "orbital_inclination_deg": orbital_inclination_deg,
            "orbital_inclination_formatted": (
                f"{orbital_inclination_deg:.2f}°"
                if orbital_inclination_deg is not None
                else "N/A"
            ),
        }


class MoonSerializer(PhysicalBodySerializer):
    """Serializer for Moon objects."""

    def serialize(self) -> Dict[str, Any]:
        details = self.get_base_details()

        # Moon type
        moon_type_display = self._get_type_display()

        # Parent body (planet or star)
        parent_body_name, parent_body_type = self._get_parent_body()

        # Orbital properties
        orbital_props = self._get_orbital_properties()

        # Surface composition hint
        density_kg_m3 = getattr(self.concrete, "density_kg_m3", None)
        surface_composition = display.get_surface_composition_hint(
            moon_type=getattr(self.concrete, "moon_type", None),
            density_kg_m3=density_kg_m3,
        )

        details.update(
            {
                "moon_type": moon_type_display,
                "moon_type_code": getattr(self.concrete, "moon_type", None),
                "parent_body_name": parent_body_name,
                "parent_body_type": parent_body_type,
                "surface_composition": surface_composition,
            }
        )

        # Add all property groups
        details.update(self._get_physical_properties())
        details.update(self._get_thermal_properties())
        details.update(orbital_props)
        details.update(self._get_rotation_properties())
        details.update(self._get_atmosphere_properties(Moon))

        return details

    def _get_type_display(self) -> Optional[str]:
        """Get moon type display value."""
        if not hasattr(self.concrete, "moon_type"):
            return None

        if hasattr(self.concrete, "get_moon_type_display"):
            try:
                return self.concrete.get_moon_type_display()
            except (AttributeError, ValueError):
                pass
        return self.concrete.moon_type

    def _get_parent_body(self) -> tuple:
        """Get parent body (planet or star) information."""
        parent_body_name = None
        parent_body_type = None

        try:
            if hasattr(self.concrete, "orbits"):
                parent_location = self.concrete.orbits
                parent_body_name = parent_location.name

                if hasattr(parent_location, "get_type_name"):
                    parent_type_name = parent_location.get_type_name()
                    if parent_type_name == "Planet":
                        if hasattr(parent_location, "planet_type"):
                            parent_body_type = (
                                parent_location.get_planet_type_display()
                                if hasattr(parent_location, "get_planet_type_display")
                                else parent_location.planet_type
                            )
                    elif parent_type_name == "Star":
                        if hasattr(parent_location, "star_type"):
                            parent_body_type = (
                                parent_location.get_star_type_display()
                                if hasattr(parent_location, "get_star_type_display")
                                else parent_location.star_type
                            )
                else:
                    parent_body_type = (
                        parent_location.get_type_name()
                        if hasattr(parent_location, "get_type_name")
                        else "Unknown"
                    )
        except Exception:
            pass  # Parent body lookup failed silently

        return parent_body_name, parent_body_type

    def _get_orbital_properties(self) -> Dict[str, Any]:
        """Get moon orbital properties."""
        orbital_distance_km = getattr(self.concrete, "orbital_distance_km", None)
        orbital_period_hours = getattr(self.concrete, "orbital_period_hours", None)
        orbital_eccentricity = getattr(self.concrete, "orbital_eccentricity", None)
        orbital_inclination_deg = getattr(
            self.concrete, "orbital_inclination_deg", None
        )

        return {
            "orbital_distance_km": orbital_distance_km,
            "orbital_distance_formatted": display.format_distance_km(
                orbital_distance_km
            ),
            "orbital_period_hours": orbital_period_hours,
            "orbital_period_formatted": display.format_orbital_period_hours(
                orbital_period_hours
            ),
            "orbital_eccentricity": orbital_eccentricity,
            "orbital_eccentricity_formatted": (
                f"{orbital_eccentricity:.3f}"
                if orbital_eccentricity is not None
                else "N/A"
            ),
            "orbital_inclination_deg": orbital_inclination_deg,
            "orbital_inclination_formatted": (
                f"{orbital_inclination_deg:.2f}°"
                if orbital_inclination_deg is not None
                else "N/A"
            ),
        }


class StationSerializer(BaseSerializer):
    """Serializer for Station objects."""

    def serialize(self) -> Dict[str, Any]:
        details = self.get_base_details()
        details.update(
            {
                "large_berths": getattr(self.concrete, "large_berths", None),
                "medium_berths": getattr(self.concrete, "medium_berths", None),
                "small_berths": getattr(self.concrete, "small_berths", None),
            }
        )
        return details


# Factory function to get the appropriate serializer for a model instance
SERIALIZER_MAP = {
    Galaxy: GalaxySerializer,
    StarSystem: StarSystemSerializer,
    Star: StarSerializer,
    Planet: PlanetSerializer,
    Moon: MoonSerializer,
    Station: StationSerializer,
}


def get_serializer_for_instance(instance) -> BaseSerializer:
    """
    Factory function to get the appropriate serializer for a model instance.

    Args:
        instance: A model instance (Galaxy, Star, Planet, etc.)

    Returns:
        An appropriate serializer instance

    Raises:
        ValueError: If no serializer exists for the instance type
    """
    # Get the concrete instance to determine actual type
    concrete = (
        instance.get_concrete_instance()
        if hasattr(instance, "get_concrete_instance")
        else instance
    )

    for model_class, serializer_class in SERIALIZER_MAP.items():
        if isinstance(concrete, model_class):
            return serializer_class(instance)

    # Fallback to base serializer
    return BaseSerializer(instance)
