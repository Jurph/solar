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
    PlanetSerializer,
    MoonSerializer,
    StationSerializer,
)
from mysite.universe.models.constants import TypeName


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
    
    @patch('mysite.universe.views.serializers.display.get_atmosphere_data')
    def test_surface_gravity_earth(self, mock_atmo):
        """
        Surface gravity for Earth should be ~9.81 m/s².
        
        Formula: g = GM/r² where G = 6.67430e-11
        If this fails, the gravity calculation formula is broken.
        """
        mock_atmo.return_value = {
            'has_atmosphere': False, 'atmosphere_type': None,
            'atmosphere_height_km': None, 'surface_pressure_bar': None,
            'scale_height_km': None,
        }
        
        serializer = PlanetSerializer(self.mock_planet)
        details = serializer.serialize()
        
        self.assertIsNotNone(details['surface_gravity_ms2'])
        self.assertAlmostEqual(details['surface_gravity_ms2'], 9.81, delta=0.1)
    
    @patch('mysite.universe.views.serializers.display.get_atmosphere_data')
    def test_escape_velocity_earth(self, mock_atmo):
        """
        Escape velocity for Earth should be ~11,186 m/s.
        
        Formula: v = sqrt(2GM/r)
        If this fails, the escape velocity calculation is broken.
        """
        mock_atmo.return_value = {
            'has_atmosphere': False, 'atmosphere_type': None,
            'atmosphere_height_km': None, 'surface_pressure_bar': None,
            'scale_height_km': None,
        }
        
        serializer = PlanetSerializer(self.mock_planet)
        details = serializer.serialize()
        
        self.assertIsNotNone(details['escape_velocity_ms'])
        self.assertAlmostEqual(details['escape_velocity_ms'], 11186, delta=100)
    
    @patch('mysite.universe.views.serializers.display.get_atmosphere_data')
    def test_low_mass_body_has_lower_gravity(self, mock_atmo):
        """
        A body with 1/10th Earth's mass and same radius should have ~1/10th gravity.
        
        This catches bugs where mass/radius aren't used correctly in the formula.
        """
        mock_atmo.return_value = {
            'has_atmosphere': False, 'atmosphere_type': None,
            'atmosphere_height_km': None, 'surface_pressure_bar': None,
            'scale_height_km': None,
        }
        
        # Create a low-mass planet
        self.mock_planet.mass_kg = 5.972e23  # 1/10th Earth mass
        
        serializer = PlanetSerializer(self.mock_planet)
        details = serializer.serialize()
        
        # Should be ~0.98 m/s² (1/10th of 9.81)
        self.assertLess(details['surface_gravity_ms2'], 2.0)
        self.assertAlmostEqual(details['surface_gravity_ms2'], 0.98, delta=0.1)


class SerializerDataExtractionTests(TestCase):
    """Tests that serializers correctly extract parent body relationships."""
    
    @patch('mysite.universe.views.serializers.display.get_atmosphere_data')
    def test_moon_parent_body_extraction(self, mock_atmo):
        """
        Moon serializer should correctly identify its parent planet.
        
        This tests the parent body lookup logic which traverses the 'orbits' relation.
        """
        mock_atmo.return_value = {
            'has_atmosphere': False, 'atmosphere_type': None,
            'atmosphere_height_km': None, 'surface_pressure_bar': None,
            'scale_height_km': None,
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
        
        self.assertEqual(details['parent_body_name'], "Jupiter")
        self.assertEqual(details['parent_body_type'], "Gas Giant")
    
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
        self.assertEqual(details['large_berths'], 2)
        self.assertEqual(details['medium_berths'], 5)
        self.assertEqual(details['small_berths'], 10)


if __name__ == '__main__':
    unittest.main()
