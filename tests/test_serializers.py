"""
Tests for the baseball card serializers.

These tests verify:
- Physical calculations (gravity, velocities) are mathematically correct
- Serializers properly extract and transform data from models
"""

import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase

from mysite.universe.views.serializers import (
    BaseSerializer,
    GalaxySerializer,
    StarSystemSerializer,
    StarSerializer,
    PlanetSerializer,
    MoonSerializer,
    StationSerializer,
    get_serializer_for_instance,
)
from mysite.universe.models.constants import TypeName
from mysite.universe.models import Station


class PhysicsCalculationTests(TestCase):
    """Tests that verify physics calculations are mathematically correct."""

    def setUp(self):
        """Create an Earth-like mock planet for physics tests."""
        self.mock_planet = MagicMock()
        self.mock_planet.name = "Earth"
        self.mock_planet.scale = "PLANET"
        self.mock_planet.get_type_name.return_value = TypeName.PLANET
        self.mock_planet.get_concrete_instance.return_value = self.mock_planet

        # Earth's actual physical properties
        self.mock_planet.mass_kg = 5.972e24
        self.mock_planet.radius_km = 6371
        self.mock_planet.density_kg_m3 = 5514
        self.mock_planet.albedo = 0.306
        self.mock_planet.equilibrium_temperature_k = 255
        self.mock_planet.orbital_distance_au = 1.0
        self.mock_planet.orbital_period_days = 365.25
        self.mock_planet.orbital_eccentricity = 0.0167
        self.mock_planet.orbital_inclination_deg = 0.0
        self.mock_planet.rotation_period_hours = 24.0
        self.mock_planet.axial_tilt_deg = 23.44
        self.mock_planet.is_tidally_locked = False
        self.mock_planet.planet_type = "SILICATE"
        self.mock_planet.get_planet_type_display.return_value = "Silicate"

        mock_star = MagicMock()
        mock_star.name = "Sol"
        mock_star.star_type = "G2V"
        mock_star.get_star_type_display.return_value = "G2V"
        self.mock_planet.orbits = mock_star

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_surface_gravity_earth(self, mock_atmo):
        """
        Surface gravity for Earth should be ~9.81 m/s².

        Formula: g = GM/r² where G = 6.67430e-11
        If this fails, the gravity calculation formula is broken.
        """
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }

        serializer = PlanetSerializer(self.mock_planet)
        details = serializer.serialize()

        self.assertIsNotNone(details["surface_gravity_ms2"])
        self.assertAlmostEqual(details["surface_gravity_ms2"], 9.81, delta=0.1)

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_escape_velocity_earth(self, mock_atmo):
        """
        Escape velocity for Earth should be ~11,186 m/s.

        Formula: v = sqrt(2GM/r)
        If this fails, the escape velocity calculation is broken.
        """
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }

        serializer = PlanetSerializer(self.mock_planet)
        details = serializer.serialize()

        self.assertIsNotNone(details["escape_velocity_ms"])
        self.assertAlmostEqual(details["escape_velocity_ms"], 11186, delta=100)

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_low_mass_body_has_lower_gravity(self, mock_atmo):
        """
        A body with 1/10th Earth's mass and same radius should have ~1/10th gravity.

        This catches bugs where mass/radius aren't used correctly in the formula.
        """
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }

        # Create a low-mass planet
        self.mock_planet.mass_kg = 5.972e23  # 1/10th Earth mass

        serializer = PlanetSerializer(self.mock_planet)
        details = serializer.serialize()

        # Should be ~0.98 m/s² (1/10th of 9.81)
        self.assertLess(details["surface_gravity_ms2"], 2.0)
        self.assertAlmostEqual(details["surface_gravity_ms2"], 0.98, delta=0.1)


class SerializerDataExtractionTests(TestCase):
    """Tests that serializers correctly extract parent body relationships."""

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_moon_parent_body_extraction(self, mock_atmo):
        """
        Moon serializer should correctly identify its parent planet.

        This tests the parent body lookup logic which traverses the 'orbits' relation.
        """
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }

        # Set up moon orbiting a planet
        mock_planet = MagicMock()
        mock_planet.name = "Jupiter"
        mock_planet.get_type_name.return_value = TypeName.PLANET
        mock_planet.planet_type = "GAS_GIANT"
        mock_planet.get_planet_type_display.return_value = "Gas Giant"

        mock_moon = MagicMock()
        mock_moon.name = "Europa"
        mock_moon.scale = "MOON"
        mock_moon.get_type_name.return_value = TypeName.MOON
        mock_moon.get_concrete_instance.return_value = mock_moon
        mock_moon.orbits = mock_planet
        mock_moon.moon_type = "ICY"
        mock_moon.get_moon_type_display.return_value = "Icy"
        mock_moon.mass_kg = 4.8e22
        mock_moon.radius_km = 1560
        mock_moon.density_kg_m3 = 3013
        mock_moon.orbital_distance_km = 671000
        mock_moon.orbital_period_hours = 85.2
        mock_moon.orbital_eccentricity = 0.009
        mock_moon.orbital_inclination_deg = 0.47
        mock_moon.rotation_period_hours = 85.2
        mock_moon.axial_tilt_deg = 0.1
        mock_moon.is_tidally_locked = True
        mock_moon.albedo = 0.67
        mock_moon.equilibrium_temperature_k = 102

        serializer = MoonSerializer(mock_moon)
        details = serializer.serialize()

        self.assertEqual(details["parent_body_name"], "Jupiter")
        self.assertEqual(details["parent_body_type"], "Gas Giant")

    def test_station_berth_counts(self):
        """Station serializer should include all berth size categories."""
        mock_station = MagicMock()
        mock_station.name = "Ceres Station"
        mock_station.scale = "STATION"
        mock_station.get_type_name.return_value = TypeName.STATION
        mock_station.get_concrete_instance.return_value = mock_station
        mock_station.large_berths = 2
        mock_station.medium_berths = 5
        mock_station.small_berths = 10

        serializer = StationSerializer(mock_station)
        details = serializer.serialize()

        # All three berth types should be present
        self.assertEqual(details["large_berths"], 2)
        self.assertEqual(details["medium_berths"], 5)
        self.assertEqual(details["small_berths"], 10)


class BaseSerializerFallbackTests(TestCase):
    """Tests for BaseSerializer.serialize() fallback path."""

    def test_base_serialize_returns_base_details(self):
        """BaseSerializer.serialize() returns name/type/scale without subclass override."""
        mock_obj = MagicMock()
        mock_obj.name = "Void"
        mock_obj.get_type_name.return_value = "Unknown"
        mock_obj.scale = None
        # No get_concrete_instance → concrete == instance
        del mock_obj.get_concrete_instance
        serializer = BaseSerializer(mock_obj)
        result = serializer.serialize()
        self.assertEqual(result["name"], "Void")
        self.assertIn("type", result)


class GalaxySerializerTests(TestCase):
    """Tests for GalaxySerializer including _get_choice_display edge cases."""

    def _make_galaxy(self):
        mock = MagicMock()
        mock.name = "Milky Way"
        mock.get_type_name.return_value = "Galaxy"
        mock.scale = "GALAXY"
        mock.get_concrete_instance.return_value = mock
        mock.galaxy_type = "SPIRAL"
        mock.get_galaxy_type_display.return_value = "Spiral"
        mock.galaxy_size = "LARGE"
        mock.get_galaxy_size_display.return_value = "Large"
        return mock

    def test_galaxy_serialize_normal(self):
        """GalaxySerializer returns galaxy_type and galaxy_size display strings."""
        mock = self._make_galaxy()
        result = GalaxySerializer(mock).serialize()
        self.assertEqual(result["galaxy_type"], "Spiral")
        self.assertEqual(result["galaxy_size"], "Large")

    def test_get_choice_display_missing_field_returns_none(self):
        """_get_choice_display returns None when field doesn't exist on concrete."""
        mock = self._make_galaxy()
        del mock.galaxy_type  # remove attribute so hasattr returns False
        result = GalaxySerializer(mock).serialize()
        self.assertIsNone(result["galaxy_type"])

    def test_get_choice_display_raises_falls_back_to_raw(self):
        """_get_choice_display falls back to raw field value when display method raises."""
        mock = self._make_galaxy()
        mock.get_galaxy_type_display.side_effect = ValueError("bad value")
        result = GalaxySerializer(mock).serialize()
        self.assertEqual(result["galaxy_type"], "SPIRAL")


class StarSystemSerializerTests(TestCase):
    """Tests for StarSystemSerializer."""

    def test_star_system_serialize_includes_age(self):
        """StarSystemSerializer includes system_age_years."""
        mock = MagicMock()
        mock.name = "Sol System"
        mock.get_type_name.return_value = "StarSystem"
        mock.scale = "STAR_SYSTEM"
        mock.get_concrete_instance.return_value = mock
        mock.system_age_years = 4.6e9
        result = StarSystemSerializer(mock).serialize()
        self.assertEqual(result["name"], "Sol System")
        self.assertAlmostEqual(result["system_age_years"], 4.6e9)

    def test_star_system_serialize_missing_age_returns_none(self):
        """StarSystemSerializer returns None for missing system_age_years."""
        mock = MagicMock(
            spec=["name", "get_type_name", "scale", "get_concrete_instance"]
        )
        mock.name = "Anonymous System"
        mock.get_type_name.return_value = "StarSystem"
        mock.scale = "STAR_SYSTEM"
        mock.get_concrete_instance.return_value = mock
        result = StarSystemSerializer(mock).serialize()
        self.assertIsNone(result["system_age_years"])


class StarSerializerTests(TestCase):
    """Tests for StarSerializer."""

    def _make_star(self):
        mock = MagicMock()
        mock.name = "Sol"
        mock.get_type_name.return_value = "Star"
        mock.scale = "STAR"
        mock.get_concrete_instance.return_value = mock
        mock.star_type = "G2V"
        mock.star_magnitude = 4.83
        mock.temperature_k = 5778
        mock.mass_kg = 1.989e30
        mock.mass_solar = 1.0
        mock.radius_km = 696000
        mock.radius_solar = 1.0
        return mock

    def test_star_serialize_all_fields_present(self):
        """StarSerializer includes all star-specific fields."""
        mock = self._make_star()
        result = StarSerializer(mock).serialize()
        self.assertEqual(result["star_type"], "G2V")
        self.assertAlmostEqual(result["star_magnitude"], 4.83)
        self.assertEqual(result["temperature_k"], 5778)
        self.assertEqual(result["mass_kg"], 1.989e30)
        self.assertEqual(result["radius_km"], 696000)

    def test_star_serialize_none_magnitude_stays_none(self):
        """StarSerializer keeps star_magnitude as None when not set."""
        mock = self._make_star()
        mock.star_magnitude = None
        result = StarSerializer(mock).serialize()
        self.assertIsNone(result["star_magnitude"])


class PlanetSerializerEdgeCaseTests(TestCase):
    """Edge cases for PlanetSerializer type display and parent body paths."""

    def _make_planet(self):
        mock = MagicMock()
        mock.name = "Terra"
        mock.scale = "PLANET"
        mock.get_type_name.return_value = TypeName.PLANET
        mock.get_concrete_instance.return_value = mock
        mock.mass_kg = 5.972e24
        mock.radius_km = 6371
        mock.density_kg_m3 = 5514
        mock.albedo = 0.306
        mock.equilibrium_temperature_k = 255
        mock.orbital_distance_au = 1.0
        mock.orbital_period_days = 365.25
        mock.orbital_eccentricity = 0.0167
        mock.orbital_inclination_deg = 0.0
        mock.rotation_period_hours = 24.0
        mock.axial_tilt_deg = 23.44
        mock.is_tidally_locked = False
        mock.planet_type = "SILICATE"
        mock.get_planet_type_display.return_value = "Silicate"
        parent = MagicMock()
        parent.name = "Sol"
        parent.star_type = "G2V"
        parent.get_star_type_display.return_value = "G2V"
        mock.orbits = parent
        return mock

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_planet_type_display_missing_attr_returns_none(self, mock_atmo):
        """_get_type_display returns None when concrete has no planet_type attr."""
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }
        mock = self._make_planet()
        del mock.planet_type
        result = PlanetSerializer(mock).serialize()
        self.assertIsNone(result["planet_type"])

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_planet_type_display_raises_falls_back_to_raw(self, mock_atmo):
        """_get_type_display falls back to raw planet_type when display raises."""
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }
        mock = self._make_planet()
        mock.get_planet_type_display.side_effect = ValueError("bad choice")
        result = PlanetSerializer(mock).serialize()
        self.assertEqual(result["planet_type"], "SILICATE")

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_planet_parent_body_exception_returns_none(self, mock_atmo):
        """_get_parent_body silently swallows exceptions and returns None, None."""
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }
        mock = self._make_planet()
        # Make .orbits raise when accessed
        type(mock).orbits = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("DB error"))
        )
        result = PlanetSerializer(mock).serialize()
        self.assertIsNone(result["parent_body_name"])
        self.assertIsNone(result["parent_body_type"])


class MoonSerializerEdgeCaseTests(TestCase):
    """Edge cases for MoonSerializer type display and parent body paths."""

    def _make_moon(self, parent_mock=None):
        mock = MagicMock()
        mock.name = "Luna"
        mock.scale = "MOON"
        mock.get_type_name.return_value = TypeName.MOON
        mock.get_concrete_instance.return_value = mock
        mock.mass_kg = 7.34e22
        mock.radius_km = 1737
        mock.density_kg_m3 = 3346
        mock.albedo = 0.12
        mock.equilibrium_temperature_k = 270
        mock.orbital_distance_km = 384400
        mock.orbital_period_hours = 655.7
        mock.orbital_eccentricity = 0.055
        mock.orbital_inclination_deg = 5.1
        mock.rotation_period_hours = 655.7
        mock.axial_tilt_deg = 6.7
        mock.is_tidally_locked = True
        mock.moon_type = "ROCKY"
        mock.get_moon_type_display.return_value = "Rocky"
        if parent_mock is not None:
            mock.orbits = parent_mock
        return mock

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_moon_type_display_missing_attr_returns_none(self, mock_atmo):
        """_get_type_display returns None when concrete has no moon_type attr."""
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }
        parent = MagicMock()
        parent.name = "Earth"
        parent.get_type_name.return_value = "Planet"
        parent.planet_type = "SILICATE"
        parent.get_planet_type_display.return_value = "Silicate"
        mock = self._make_moon(parent_mock=parent)
        del mock.moon_type
        result = MoonSerializer(mock).serialize()
        self.assertIsNone(result["moon_type"])

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_moon_type_display_raises_falls_back_to_raw(self, mock_atmo):
        """_get_type_display falls back to raw moon_type when display raises."""
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }
        parent = MagicMock()
        parent.name = "Earth"
        parent.get_type_name.return_value = "Planet"
        parent.planet_type = "SILICATE"
        parent.get_planet_type_display.return_value = "Silicate"
        mock = self._make_moon(parent_mock=parent)
        mock.get_moon_type_display.side_effect = ValueError("bad choice")
        result = MoonSerializer(mock).serialize()
        self.assertEqual(result["moon_type"], "ROCKY")

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_moon_parent_body_is_star(self, mock_atmo):
        """_get_parent_body returns star type display when moon orbits a star."""
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }
        parent_star = MagicMock()
        parent_star.name = "Proxima"
        parent_star.get_type_name.return_value = "Star"
        parent_star.star_type = "M5V"
        parent_star.get_star_type_display.return_value = "Red Dwarf"
        mock = self._make_moon(parent_mock=parent_star)
        result = MoonSerializer(mock).serialize()
        self.assertEqual(result["parent_body_name"], "Proxima")
        self.assertEqual(result["parent_body_type"], "Red Dwarf")

    @patch("mysite.universe.views.serializers.display.get_atmosphere_data")
    def test_moon_parent_body_no_get_type_name_uses_fallback(self, mock_atmo):
        """_get_parent_body uses else branch when parent has no get_type_name."""
        mock_atmo.return_value = {
            "has_atmosphere": False,
            "atmosphere_type": None,
            "atmosphere_height_km": None,
            "surface_pressure_bar": None,
            "scale_height_km": None,
        }
        # parent that lacks get_type_name entirely
        parent = MagicMock(spec=["name"])
        parent.name = "Asteroid 42"
        mock = self._make_moon(parent_mock=parent)
        result = MoonSerializer(mock).serialize()
        self.assertEqual(result["parent_body_name"], "Asteroid 42")
        # parent_body_type falls back to 'Unknown' (else branch, no get_type_name)
        self.assertEqual(result["parent_body_type"], "Unknown")


class GetSerializerForInstanceTests(TestCase):
    """Tests for the get_serializer_for_instance factory function."""

    def test_returns_base_serializer_for_unknown_type(self):
        """get_serializer_for_instance falls back to BaseSerializer for unknown types."""
        mock_obj = MagicMock()
        mock_obj.name = "Mystery Object"
        mock_obj.get_type_name.return_value = "Unknown"
        mock_obj.scale = None
        # get_concrete_instance returns itself but it's not any known model class
        mock_obj.get_concrete_instance.return_value = mock_obj
        serializer = get_serializer_for_instance(mock_obj)
        self.assertIsInstance(serializer, BaseSerializer)

    def test_returns_station_serializer_for_station(self):
        """get_serializer_for_instance returns StationSerializer for Station instances."""
        mock_station = MagicMock(spec=Station)
        mock_station.name = "Waypoint Alpha"
        mock_station.get_type_name.return_value = TypeName.STATION
        mock_station.scale = "STATION"
        mock_station.get_concrete_instance.return_value = mock_station
        mock_station.large_berths = 1
        mock_station.medium_berths = 2
        mock_station.small_berths = 3
        serializer = get_serializer_for_instance(mock_station)
        self.assertIsInstance(serializer, StationSerializer)


if __name__ == "__main__":
    unittest.main()
