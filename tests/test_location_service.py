"""
Comprehensive tests for location_service distance calculations.

Tests get_distance_between() using meaningful combinations from test_universe data.
Verifies exact distances based on system age and orbital positions, not just ranges.
"""
import os
import math
from django.conf import settings
from django.test import TestCase
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.base import Location
from mysite.universe.models.celestial import Planet, Moon, StarSystem
from mysite.universe.models.station import Station
from mysite.universe.services.location_service import (
    get_distance_between,
    get_distance_between_star_systems,
    find_star_system_for_location,
    get_orbital_distance_au,
    get_subordinate_bodies,
)
from mysite.universe.services.location_service import (
    _calculate_same_parent_distance,
    _calculate_planet_to_planet_distance,
    _get_orbital_parent,
    _get_orbital_distance_from_parent,
)


def calculate_solar_angle_deg(system_age_years: float, orbital_period_days: float) -> float:
    """Calculate current orbital position from system age and period."""
    orbital_period_years = orbital_period_days / 365.25
    revolutions = system_age_years / orbital_period_years
    angle_deg = (revolutions % 1.0) * 360.0
    return angle_deg


def calculate_expected_planet_distance(planet1: Planet, planet2: Planet, 
                                       system_age_years: float) -> float:
    """
    Calculate expected distance between two planets using their orbital positions.
    
    Uses law of cosines with actual orbital angles derived from system age.
    """
    dist1_au = getattr(planet1, 'orbital_distance_au', None)
    dist2_au = getattr(planet2, 'orbital_distance_au', None)
    period1_days = getattr(planet1, 'orbital_period_days', None)
    period2_days = getattr(planet2, 'orbital_period_days', None)
    
    if not all([dist1_au, dist2_au, period1_days, period2_days]):
        return None
    
    # Calculate orbital positions
    angle1_deg = calculate_solar_angle_deg(system_age_years, period1_days)
    angle2_deg = calculate_solar_angle_deg(system_age_years, period2_days)
    
    # Angle difference (take smaller angle)
    angle_diff_deg = abs(angle2_deg - angle1_deg)
    if angle_diff_deg > 180.0:
        angle_diff_deg = 360.0 - angle_diff_deg
    
    # Law of cosines
    angle_diff_rad = math.radians(angle_diff_deg)
    cos_angle = math.cos(angle_diff_rad)
    
    distance_squared = dist1_au**2 + dist2_au**2 - 2 * dist1_au * dist2_au * cos_angle
    return math.sqrt(distance_squared)


class LocationDistanceTest(TestCase):
    """
    Test distance calculations between locations using test_universe data.
    
    These tests measure distances empirically and verify they're realistic,
    then assert that our calculations are correct.
    """
    
    @classmethod
    def setUpTestData(cls):
        """Import test universe and cache location references."""
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        importer = UniverseImporter(xml_file)
        importer.import_universe()
        
        # Cache all locations we'll need for tests
        cls.earth = Location.objects.get(name="Earth")
        cls.mars = Location.objects.get(name="Mars")
        cls.moon = Location.objects.get(name="Moon")
        cls.luna = Location.objects.get(name="Luna")
        cls.phobos = Location.objects.get(name="Phobos")
        cls.deimos = Location.objects.get(name="Deimos")
        cls.ceres = Location.objects.get(name="Ceres")
        
        cls.earth_control = Location.objects.get(name="Earth Orbital Control")
        cls.mars_control = Location.objects.get(name="Mars Control")
        cls.luna_control = Location.objects.get(name="Luna Orbital Control")
        cls.phobos_control = Location.objects.get(name="Phobos Control")
        cls.deimos_control = Location.objects.get(name="Deimos Control")
        
        cls.sol_system = Location.objects.get(name="Sol System")
        cls.binary_system = Location.objects.get(name="Binary System")
        
        cls.alpha_prime = Location.objects.get(name="Alpha Prime")
        cls.alpha_minor = Location.objects.get(name="Alpha Minor")
        cls.beta_major = Location.objects.get(name="Beta Major")
        cls.beta_minor = Location.objects.get(name="Beta Minor")
        
        cls.alpha_moon_1 = Location.objects.get(name="Alpha Moon 1")
        cls.alpha_moon_2 = Location.objects.get(name="Alpha Moon 2")
        cls.beta_moon_1 = Location.objects.get(name="Beta Moon 1")
        cls.beta_moon_2 = Location.objects.get(name="Beta Moon 2")
    
    def _get_orbital_data(self, location):
        """Helper to extract orbital data for verification."""
        concrete = location.get_concrete_instance()
        if isinstance(concrete, Planet):
            return {
                'type': 'Planet',
                'orbital_distance_au': getattr(concrete, 'orbital_distance_au', None),
                'orbits': concrete.orbits if hasattr(concrete, 'orbits') else None,
            }
        elif isinstance(concrete, Moon):
            return {
                'type': 'Moon',
                'orbital_distance_km': getattr(concrete, 'orbital_distance_km', None),
                'orbits': concrete.orbits if hasattr(concrete, 'orbits') else None,
            }
        elif isinstance(concrete, Station):
            return {
                'type': 'Station',
                'orbital_distance_km': getattr(concrete, 'orbital_distance_km', None),
                'orbits': concrete.orbits if hasattr(concrete, 'orbits') else None,
            }
        elif isinstance(concrete, StarSystem):
            return {
                'type': 'StarSystem',
                'galactic_x_ly': getattr(concrete, 'galactic_x_ly', None),
                'galactic_y_ly': getattr(concrete, 'galactic_y_ly', None),
                'galactic_z_ly': getattr(concrete, 'galactic_z_ly', None),
            }
        return {'type': type(concrete).__name__}
    
    def test_same_location_distance_is_zero(self):
        """Distance from a location to itself should be zero."""
        distance, unit = get_distance_between(self.earth, self.earth)
        self.assertEqual(distance, 0.0)
        self.assertEqual(unit, "km")
    
    def test_starsystem_to_starsystem_same_system(self):
        """Distance between same StarSystem should be zero."""
        distance, unit = get_distance_between(self.sol_system, self.sol_system)
        self.assertEqual(distance, 0.0)
        # Unit is "km" because same-object check happens before StarSystem-specific logic
        self.assertEqual(unit, "km")
    
    def test_starsystem_to_starsystem_exact(self):
        """Distance between different star systems uses exact galactic coordinates."""
        sol_concrete = self.sol_system.get_concrete_instance()
        binary_concrete = self.binary_system.get_concrete_instance()
        
        if not (isinstance(sol_concrete, StarSystem) and isinstance(binary_concrete, StarSystem)):
            self.skipTest("Star systems not found")
        
        # Check if both have galactic coordinates
        sol_has_coords = all([
            sol_concrete.galactic_x_ly is not None,
            sol_concrete.galactic_y_ly is not None,
            sol_concrete.galactic_z_ly is not None,
        ])
        binary_has_coords = all([
            binary_concrete.galactic_x_ly is not None,
            binary_concrete.galactic_y_ly is not None,
            binary_concrete.galactic_z_ly is not None,
        ])
        
        if not (sol_has_coords and binary_has_coords):
            self.skipTest("Star systems missing galactic coordinates")
        
        # Calculate expected distance
        expected_distance = get_distance_between_star_systems(sol_concrete, binary_concrete)
        
        # Get actual distance
        distance, unit = get_distance_between(self.sol_system, self.binary_system)
        
        self.assertEqual(unit, "ly", "StarSystem-to-StarSystem distance should be in light-years")
        self.assertIsNotNone(distance, "Distance should be calculated")
        self.assertGreater(distance, 0.0, "Distance should be positive")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=6,
            msg=f"StarSystem distance {distance} ly should match calculated {expected_distance} ly")
    
    def test_starsystem_to_starsystem_symmetry(self):
        """Verify StarSystem-to-StarSystem distance is symmetric."""
        distance_sol_binary, unit1 = get_distance_between(self.sol_system, self.binary_system)
        distance_binary_sol, unit2 = get_distance_between(self.binary_system, self.sol_system)
        
        self.assertEqual(unit1, unit2, "Units should match")
        if distance_sol_binary is not None and distance_binary_sol is not None:
            self.assertAlmostEqual(distance_sol_binary, distance_binary_sol, places=6,
                msg="StarSystem-to-StarSystem distances should be symmetric")
    
    def test_planet_to_planet_same_system_exact(self):
        """Distance between planets in same system uses exact orbital positions."""
        earth_concrete = self.earth.get_concrete_instance()
        mars_concrete = self.mars.get_concrete_instance()
        
        if not (isinstance(earth_concrete, Planet) and isinstance(mars_concrete, Planet)):
            self.skipTest("Earth or Mars not found as Planet")
        
        # Both should orbit the same star (Sol)
        if earth_concrete.orbits != mars_concrete.orbits:
            self.skipTest("Earth and Mars don't orbit the same star")
        
        # Get system age
        star = earth_concrete.orbits
        system = star.orbits if hasattr(star, 'orbits') else None
        if not system or not isinstance(system, StarSystem):
            self.skipTest("Cannot find star system")
        
        system_age_years = getattr(system, 'system_age_years', None)
        
        # Get orbital distances
        earth_au = getattr(earth_concrete, 'orbital_distance_au', None)
        mars_au = getattr(mars_concrete, 'orbital_distance_au', None)
        earth_period = getattr(earth_concrete, 'orbital_period_days', None)
        mars_period = getattr(mars_concrete, 'orbital_period_days', None)
        
        if earth_au is None or mars_au is None:
            self.skipTest("Missing orbital distance data")
        
        # Calculate expected distance
        if system_age_years is not None and earth_period is not None and mars_period is not None:
            # Use exact orbital positions
            expected_distance = calculate_expected_planet_distance(
                earth_concrete, mars_concrete, system_age_years
            )
        else:
            # Fallback: simple difference (what the code does when system_age is missing)
            expected_distance = abs(mars_au - earth_au)
        
        # Get actual distance
        distance, unit = get_distance_between(self.earth, self.mars)
        
        self.assertEqual(unit, "au", "Planet-to-planet distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match (allowing small floating point differences)
        self.assertAlmostEqual(distance, expected_distance, places=6,
            msg=f"Earth-Mars distance {distance} AU should match calculated {expected_distance} AU based on orbital positions")
    
    def test_planet_to_planet_symmetry(self):
        """Verify planet-to-planet distance is symmetric."""
        distance_earth_mars, unit1 = get_distance_between(self.earth, self.mars)
        distance_mars_earth, unit2 = get_distance_between(self.mars, self.earth)
        
        self.assertEqual(unit1, unit2, "Units should match")
        if distance_earth_mars is not None and distance_mars_earth is not None:
            self.assertAlmostEqual(distance_earth_mars, distance_mars_earth, places=6,
                msg="Planet-to-planet distances should be symmetric")
    
    def test_planet_to_planet_different_systems(self):
        """Distance between planets in different systems uses star system distance."""
        distance, unit = get_distance_between(self.earth, self.alpha_prime)
        
        # Should use light-years (different star systems)
        self.assertEqual(unit, "ly")
        
        # If star systems have coordinates, distance should be calculated
        sol_system = find_star_system_for_location(self.earth)
        binary_system = find_star_system_for_location(self.alpha_prime)
        
        if sol_system and binary_system:
            system_distance = get_distance_between_star_systems(sol_system, binary_system)
            if system_distance != float('inf'):
                # Distance should be approximately the star system distance
                # (plus small orbital distances, but those are negligible at interstellar scale)
                self.assertAlmostEqual(distance, system_distance, delta=0.1,
                    msg=f"Planet-to-planet distance {distance} ly should approximate system distance {system_distance} ly")
    
    def test_moon_to_moon_same_parent_exact(self):
        """Distance between moons of same parent uses exact triangular calculation."""
        phobos_concrete = self.phobos.get_concrete_instance()
        deimos_concrete = self.deimos.get_concrete_instance()
        
        if not (isinstance(phobos_concrete, Moon) and isinstance(deimos_concrete, Moon)):
            self.skipTest("Phobos or Deimos not found as Moon")
        
        if phobos_concrete.orbits != deimos_concrete.orbits:
            self.skipTest("Phobos and Deimos don't orbit the same parent")
        
        phobos_km = getattr(phobos_concrete, 'orbital_distance_km', None)
        deimos_km = getattr(deimos_concrete, 'orbital_distance_km', None)
        
        if phobos_km is None or deimos_km is None:
            self.skipTest("Missing orbital distance data")
        
        # Calculate expected distance using 60° separation (as per implementation)
        phobos_au = phobos_km / 1.496e8
        deimos_au = deimos_km / 1.496e8
        angle_rad = math.radians(60.0)
        cos_angle = math.cos(angle_rad)
        expected_distance = math.sqrt(
            phobos_au**2 + deimos_au**2 - 2 * phobos_au * deimos_au * cos_angle
        )
        
        # Get actual distance
        distance, unit = get_distance_between(self.phobos, self.deimos)
        
        self.assertEqual(unit, "au", "Moon-to-moon distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=8,
            msg=f"Phobos-Deimos distance {distance} AU should match calculated {expected_distance} AU")
    
    def test_moon_to_moon_symmetry(self):
        """Verify moon-to-moon distance is symmetric."""
        distance_phobos_deimos, unit1 = get_distance_between(self.phobos, self.deimos)
        distance_deimos_phobos, unit2 = get_distance_between(self.deimos, self.phobos)
        
        self.assertEqual(unit1, unit2, "Units should match")
        if distance_phobos_deimos is not None and distance_deimos_phobos is not None:
            self.assertAlmostEqual(distance_phobos_deimos, distance_deimos_phobos, places=8,
                msg="Moon-to-moon distances should be symmetric")
    
    def test_moon_to_different_planet_moon_exact(self):
        """Distance between moons of different planets uses exact parent distance."""
        # Moon (orbits Earth) to Phobos (orbits Mars)
        earth_mars_distance, _ = get_distance_between(self.earth, self.mars)
        if earth_mars_distance is None:
            self.skipTest("Cannot calculate Earth-Mars distance")
        
        moon_concrete = self.moon.get_concrete_instance()
        phobos_concrete = self.phobos.get_concrete_instance()
        
        moon_km = getattr(moon_concrete, 'orbital_distance_km', None) if isinstance(moon_concrete, Moon) else None
        phobos_km = getattr(phobos_concrete, 'orbital_distance_km', None) if isinstance(phobos_concrete, Moon) else None
        
        # Expected: Earth-Mars distance + both moon orbital distances
        expected_distance = earth_mars_distance
        if moon_km is not None:
            expected_distance += moon_km / 1.496e8
        if phobos_km is not None:
            expected_distance += phobos_km / 1.496e8
        
        # Get actual distance
        distance, unit = get_distance_between(self.moon, self.phobos)
        
        self.assertEqual(unit, "au", "Moon-to-moon distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=6,
            msg=f"Moon-to-moon distance {distance} AU should match {expected_distance} AU")
    
    def test_station_to_planet_exact(self):
        """Distance from station to different planet uses exact calculations."""
        # Earth Orbital Control (station orbiting Earth) to Mars (planet)
        earth_control_concrete = self.earth_control.get_concrete_instance()
        mars_concrete = self.mars.get_concrete_instance()
        
        if not isinstance(earth_control_concrete, Station):
            self.skipTest("Earth Orbital Control not found as Station")
        if not isinstance(mars_concrete, Planet):
            self.skipTest("Mars not found as Planet")
        
        if earth_control_concrete.orbits != self.earth:
            self.skipTest("Earth Orbital Control doesn't orbit Earth")
        
        # Get Earth-Mars distance (exact, based on orbital positions)
        earth_mars_distance, _ = get_distance_between(self.earth, self.mars)
        if earth_mars_distance is None:
            self.skipTest("Cannot calculate Earth-Mars distance")
        
        # Get station orbital altitude
        # Note: _get_orbital_distance_from_parent uses a 400 km fallback if orbital_distance_km is not set
        station_km = getattr(earth_control_concrete, 'orbital_distance_km', None)
        if station_km is None:
            # Use fallback value (400 km) that _get_orbital_distance_from_parent uses
            station_km = 400.0
        station_au = station_km / 1.496e8
        
        # Calculate expected: Earth-Mars distance + station altitude
        # (Station altitude is tiny, so this is approximately Earth-Mars distance)
        expected_distance = earth_mars_distance + station_au
        
        # Get actual distance
        distance, unit = get_distance_between(self.earth_control, self.mars)
        
        self.assertEqual(unit, "au", "Station-to-planet distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match (station altitude is tiny, so should be very close to Earth-Mars)
        self.assertAlmostEqual(distance, expected_distance, places=6,
            msg=f"Station-to-planet distance {distance} AU should match {expected_distance} AU")
    
    def test_station_to_planet_symmetry(self):
        """Verify station-to-planet distance is symmetric."""
        distance_station_planet, unit1 = get_distance_between(self.earth_control, self.mars)
        distance_planet_station, unit2 = get_distance_between(self.mars, self.earth_control)
        
        self.assertEqual(unit1, unit2, "Units should match")
        if distance_station_planet is not None and distance_planet_station is not None:
            self.assertAlmostEqual(distance_station_planet, distance_planet_station, places=6,
                msg="Station-to-planet distances should be symmetric")
    
    def test_station_to_different_planet_moon_exact(self):
        """Distance from station to different planet's moon uses exact calculations."""
        # Earth Orbital Control (station orbiting Earth) to Phobos (moon orbiting Mars)
        earth_control_concrete = self.earth_control.get_concrete_instance()
        phobos_concrete = self.phobos.get_concrete_instance()
        
        if not isinstance(earth_control_concrete, Station):
            self.skipTest("Earth Orbital Control not found as Station")
        if not isinstance(phobos_concrete, Moon):
            self.skipTest("Phobos not found as Moon")
        
        # Get Earth-Mars distance (exact)
        earth_mars_distance, _ = get_distance_between(self.earth, self.mars)
        if earth_mars_distance is None:
            self.skipTest("Cannot calculate Earth-Mars distance")
        
        # Get Phobos orbital distance from Mars
        phobos_km = getattr(phobos_concrete, 'orbital_distance_km', None)
        phobos_au = phobos_km / 1.496e8 if phobos_km is not None else None
        
        # Get station orbital altitude (use 400 km fallback if not set)
        station_km = getattr(earth_control_concrete, 'orbital_distance_km', None)
        if station_km is None:
            station_km = 400.0
        station_au = station_km / 1.496e8
        
        # Expected: Earth-Mars distance + Phobos orbital distance + station altitude
        expected_distance = earth_mars_distance + station_au
        if phobos_au is not None:
            expected_distance += phobos_au
        
        # Get actual distance
        distance, unit = get_distance_between(self.earth_control, self.phobos)
        
        self.assertEqual(unit, "au", "Station-to-moon distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=6,
            msg=f"Station-to-moon distance {distance} AU should match {expected_distance} AU")
    
    def test_station_to_station_same_planet_exact(self):
        """Distance between stations orbiting same planet uses exact triangular calculation."""
        luna_control = Location.objects.get(name="Luna Orbital Control")
        luna_secondary = Location.objects.get(name="Luna Secondary Control")
        
        control_concrete = luna_control.get_concrete_instance()
        secondary_concrete = luna_secondary.get_concrete_instance()
        
        if not (isinstance(control_concrete, Station) and isinstance(secondary_concrete, Station)):
            self.skipTest("Stations not found")
        
        if control_concrete.orbits != secondary_concrete.orbits:
            self.skipTest("Stations don't orbit the same parent")
        
        control_km = getattr(control_concrete, 'orbital_distance_km', None)
        secondary_km = getattr(secondary_concrete, 'orbital_distance_km', None)
        
        if control_km is None or secondary_km is None:
            self.skipTest("Missing orbital distance data")
        
        # Calculate expected distance using 60° separation
        control_au = control_km / 1.496e8
        secondary_au = secondary_km / 1.496e8
        angle_rad = math.radians(60.0)
        cos_angle = math.cos(angle_rad)
        expected_distance = math.sqrt(
            control_au**2 + secondary_au**2 - 2 * control_au * secondary_au * cos_angle
        )
        
        # Get actual distance
        distance, unit = get_distance_between(luna_control, luna_secondary)
        
        self.assertEqual(unit, "au", "Station-to-station distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=8,
            msg=f"Station-to-station distance {distance} AU should match {expected_distance} AU")
    
    def test_station_to_station_different_planets_exact(self):
        """Distance between stations orbiting different planets uses exact parent distance."""
        # Earth Orbital Control to Mars Control
        earth_mars_distance, _ = get_distance_between(self.earth, self.mars)
        if earth_mars_distance is None:
            self.skipTest("Cannot calculate Earth-Mars distance")
        
        # Get station orbital altitudes
        earth_control_concrete = self.earth_control.get_concrete_instance()
        mars_control_concrete = self.mars_control.get_concrete_instance()
        
        control1_km = getattr(earth_control_concrete, 'orbital_distance_km', None) if isinstance(earth_control_concrete, Station) else None
        control2_km = getattr(mars_control_concrete, 'orbital_distance_km', None) if isinstance(mars_control_concrete, Station) else None
        
        # Use 400 km fallback if orbital_distance_km is not set (matches _get_orbital_distance_from_parent)
        if control1_km is None:
            control1_km = 400.0
        if control2_km is None:
            control2_km = 400.0
        
        # Expected: Earth-Mars distance + both station altitudes
        expected_distance = earth_mars_distance + (control1_km / 1.496e8) + (control2_km / 1.496e8)
        
        # Get actual distance
        distance, unit = get_distance_between(self.earth_control, self.mars_control)
        
        self.assertEqual(unit, "au", "Station-to-station distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=6,
            msg=f"Station-to-station distance {distance} AU should match {expected_distance} AU")
    
    def test_planet_to_own_moon_exact(self):
        """Distance from planet to its own moon uses exact moon orbital distance."""
        moon_concrete = self.moon.get_concrete_instance()
        if not isinstance(moon_concrete, Moon):
            self.skipTest("Moon not found as Moon")
        if moon_concrete.orbits != self.earth:
            self.skipTest("Moon doesn't orbit Earth")
        
        moon_km = getattr(moon_concrete, 'orbital_distance_km', None)
        if moon_km is None:
            self.skipTest("Moon orbital distance not available")
        
        expected_au = moon_km / 1.496e8
        
        # Get actual distance
        distance, unit = get_distance_between(self.earth, self.moon)
        
        self.assertEqual(unit, "au", "Planet-to-moon distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_au, places=8,
            msg=f"Earth-Moon distance {distance} AU should equal moon orbital distance {expected_au} AU")
    
    def test_planet_to_different_planet_moon_exact(self):
        """Distance from planet to different planet's moon uses exact calculations."""
        # Earth to Phobos (Phobos orbits Mars)
        earth_mars_distance, _ = get_distance_between(self.earth, self.mars)
        if earth_mars_distance is None:
            self.skipTest("Cannot calculate Earth-Mars distance")
        
        phobos_concrete = self.phobos.get_concrete_instance()
        phobos_km = getattr(phobos_concrete, 'orbital_distance_km', None) if isinstance(phobos_concrete, Moon) else None
        
        # Expected: Earth-Mars distance + Phobos orbital distance
        expected_distance = earth_mars_distance
        if phobos_km is not None:
            expected_distance += phobos_km / 1.496e8
        
        # Get actual distance
        distance, unit = get_distance_between(self.earth, self.phobos)
        
        self.assertEqual(unit, "au", "Planet-to-moon distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=6,
            msg=f"Planet-to-moon distance {distance} AU should match {expected_distance} AU")
    
    def test_station_to_different_star_system_planet_exact(self):
        """Distance from station to planet in different star system uses exact system distance."""
        # Earth Orbital Control (Sol System) to Alpha Prime (Binary System)
        sol_system = find_star_system_for_location(self.earth)
        binary_system = find_star_system_for_location(self.alpha_prime)
        
        if not (sol_system and binary_system):
            self.skipTest("Cannot find star systems")
        
        system_distance = get_distance_between_star_systems(sol_system, binary_system)
        if system_distance == float('inf'):
            self.skipTest("Star systems missing galactic coordinates")
        
        # Expected: system distance (station altitude is negligible at interstellar scale)
        expected_distance = system_distance
        
        # Get actual distance
        distance, unit = get_distance_between(self.earth_control, self.alpha_prime)
        
        self.assertEqual(unit, "ly", "Cross-system distance should be in light-years")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match (allowing small difference for station altitude)
        self.assertAlmostEqual(distance, expected_distance, places=2,
            msg=f"Cross-system distance {distance} ly should match system distance {expected_distance} ly")
    
    def test_moon_to_different_star_system_star_exact(self):
        """Distance from moon to star in different system uses exact system distance."""
        # Moon (Sol System) to Alpha Centauri A (Binary System)
        sol_system = find_star_system_for_location(self.moon)
        binary_system = find_star_system_for_location(self.alpha_prime)
        
        if not (sol_system and binary_system):
            self.skipTest("Cannot find star systems")
        
        system_distance = get_distance_between_star_systems(sol_system, binary_system)
        if system_distance == float('inf'):
            self.skipTest("Star systems missing galactic coordinates")
        
        # Get Alpha Centauri A star
        alpha_centauri_a = Location.objects.filter(name="Alpha Centauri A").first()
        if not alpha_centauri_a:
            self.skipTest("Alpha Centauri A not found")
        
        # Expected: system distance (moon orbital distance is negligible)
        expected_distance = system_distance
        
        # Get actual distance
        distance, unit = get_distance_between(self.moon, alpha_centauri_a)
        
        self.assertEqual(unit, "ly", "Cross-system distance should be in light-years")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=2,
            msg=f"Cross-system distance {distance} ly should match system distance {expected_distance} ly")
    
    def test_station_to_same_planet_moon_exact(self):
        """Distance from station to moon of same planet uses exact calculations."""
        # Earth Orbital Control (station) to Moon (moon, both orbit Earth)
        earth_control_concrete = self.earth_control.get_concrete_instance()
        moon_concrete = self.moon.get_concrete_instance()
        
        if not (isinstance(earth_control_concrete, Station) and isinstance(moon_concrete, Moon)):
            self.skipTest("Station or Moon not found")
        
        if earth_control_concrete.orbits != moon_concrete.orbits:
            self.skipTest("Station and Moon don't orbit the same parent")
        
        # Get orbital distances
        station_km = getattr(earth_control_concrete, 'orbital_distance_km', None)
        moon_km = getattr(moon_concrete, 'orbital_distance_km', None)
        
        if station_km is None or moon_km is None:
            self.skipTest("Missing orbital distance data")
        
        # Calculate expected distance using 60° separation
        station_au = station_km / 1.496e8
        moon_au = moon_km / 1.496e8
        angle_rad = math.radians(60.0)
        cos_angle = math.cos(angle_rad)
        expected_distance = math.sqrt(
            station_au**2 + moon_au**2 - 2 * station_au * moon_au * cos_angle
        )
        
        # Get actual distance
        distance, unit = get_distance_between(self.earth_control, self.moon)
        
        self.assertEqual(unit, "au", "Station-to-moon distance should be in AU")
        self.assertIsNotNone(distance, "Distance should be calculated")
        
        # Verify exact match
        self.assertAlmostEqual(distance, expected_distance, places=8,
            msg=f"Station-to-moon distance {distance} AU should match {expected_distance} AU")


class LocationServiceHierarchyTest(TestCase):
    """Tests for subordinate body selection and star-system traversal helpers."""

    @classmethod
    def setUpTestData(cls):
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        importer = UniverseImporter(xml_file)
        importer.import_universe()

        cls.sol_system = Location.objects.get(name="Sol System")
        cls.sol = Location.objects.get(name="Sol")
        cls.earth = Location.objects.get(name="Earth")
        cls.mars = Location.objects.get(name="Mars")
        cls.moon = Location.objects.get(name="Moon")
        cls.earth_control = Location.objects.get(name="Earth Orbital Control")

    def test_get_subordinate_bodies_returns_empty_when_no_location(self):
        """No location and no name should return empty list (no random fallback)."""
        self.assertEqual(get_subordinate_bodies(), [])

    def test_get_subordinate_bodies_location_name_not_found_returns_empty(self):
        """Unknown location_name should return empty list (no random fallback)."""
        self.assertEqual(get_subordinate_bodies(location_name="THIS DOES NOT EXIST"), [])

    def test_get_subordinate_bodies_for_planet_includes_moons_and_stations(self):
        bodies = get_subordinate_bodies(location=self.earth)
        names = {b.name for b in bodies}
        self.assertIn("Earth", names)
        self.assertIn("Moon", names)
        self.assertIn("Earth Orbital Control", names)

    def test_get_subordinate_bodies_for_moon_includes_parent(self):
        bodies = get_subordinate_bodies(location=self.moon)
        names = {b.name for b in bodies}
        self.assertIn("Moon", names)
        self.assertIn("Earth", names)

    def test_get_subordinate_bodies_for_star_includes_planets_moons_and_stations(self):
        bodies = get_subordinate_bodies(location=self.sol)
        names = {b.name for b in bodies}
        self.assertIn("Earth", names)
        self.assertIn("Mars", names)
        self.assertIn("Moon", names)
        self.assertIn("Earth Orbital Control", names)

    def test_get_subordinate_bodies_for_starsystem_includes_down_graph_only(self):
        bodies = get_subordinate_bodies(location=self.sol_system)
        names = {b.name for b in bodies}
        self.assertIn("Earth", names)
        self.assertIn("Mars", names)
        self.assertIn("Moon", names)
        self.assertIn("Earth Orbital Control", names)
        self.assertNotIn("Sol System", names)

    def test_find_star_system_for_location_returns_system_for_station(self):
        system = find_star_system_for_location(self.earth_control)
        self.assertIsNotNone(system)
        self.assertEqual(system.name, "Sol System")

    def test_find_star_system_for_location_returns_none_for_disconnected_location(self):
        from mysite.universe.models.scale import Scale

        isolated = Location.objects.create(name="Isolated", scale=Scale.STATION)
        self.assertIsNone(find_star_system_for_location(isolated))

    def test_get_orbital_distance_au_returns_none_for_station(self):
        self.assertIsNone(get_orbital_distance_au(self.earth_control))

    def test_get_distance_between_returns_none_when_star_system_coords_missing(self):
        """
        If either StarSystem lacks galactic coordinates, we can't compute ly distance.
        """
        from mysite.universe.models.celestial import Galaxy, StarSystem

        g = Galaxy.objects.create(name="Coords Galaxy", galaxy_type="SP", galaxy_size="L")
        sys_with = StarSystem.objects.create(
            name="WithCoords",
            orbits=g,
            galactic_x_ly=1.0,
            galactic_y_ly=2.0,
            galactic_z_ly=3.0,
            system_age_years=1e9,
        )
        sys_without = StarSystem.objects.create(name="NoCoords", orbits=g)

        d, unit = get_distance_between(sys_with, sys_without)
        self.assertEqual(unit, "ly")
        self.assertIsNone(d)

    def test_same_parent_distance_returns_none_when_missing_orbital_distance(self):
        """
        If two siblings orbit the same parent but we lack orbital distances,
        we should return (None, 'au') rather than invent a number.
        """
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet
        from mysite.universe.models.scale import Scale

        g = Galaxy.objects.create(name="Sibling Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="Sibling System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
            system_age_years=1e9,
        )
        star = Star.objects.create(name="Sibling Star", orbits=system, star_type="G")
        planet = Planet.objects.create(name="Sibling Planet", orbits=star, planet_type="TE", orbital_distance_au=1.0)

        s1 = Station.objects.create(name="S1", orbits=planet, scale=Scale.STATION, orbital_distance_km=None)
        s2 = Station.objects.create(name="S2", orbits=planet, scale=Scale.STATION, orbital_distance_km=400.0)

        d, unit = get_distance_between(s1, s2)
        self.assertEqual(unit, "au")
        self.assertIsNone(d)

    def test_station_to_parent_uses_min_safe_orbit_fallback_when_station_missing_orbit(self):
        """
        When a Station has no orbital_distance_km, we fall back to the parent's
        min-safe-orbit + 300 km.
        """
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet
        from mysite.universe.models.scale import Scale

        g = Galaxy.objects.create(name="Orbit Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="Orbit System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
            system_age_years=1e9,
        )
        star = Star.objects.create(
            name="Orbit Star",
            orbits=system,
            star_type="G",
            radius_km=1000.0,
        )
        planet = Planet.objects.create(
            name="Orbit Planet",
            orbits=star,
            planet_type="TE",
            radius_km=1000.0,
            orbital_distance_au=1.0,
        )

        station = Station.objects.create(
            name="Orbit Station",
            orbits=planet,
            scale=Scale.STATION,
            orbital_distance_km=None,
        )

        d, unit = get_distance_between(station, planet)
        self.assertEqual(unit, "au")
        self.assertIsNotNone(d)

        min_orbit_km = planet.get_min_safe_orbit_km()
        expected_au = (min_orbit_km + 300.0) / 1.496e8
        self.assertAlmostEqual(d, expected_au, places=12)

    def test_planet_to_planet_same_system_different_stars_falls_back_to_orbital_distance_difference(self):
        """
        In a multi-star system, planets may orbit different stars. We currently fall back
        to the simple |a2-a1| approximation when we can't compute a meaningful inter-star distance.
        """
        alpha_prime = Location.objects.get(name="Alpha Prime").get_concrete_instance()
        beta_major = Location.objects.get(name="Beta Major").get_concrete_instance()

        if not (isinstance(alpha_prime, Planet) and isinstance(beta_major, Planet)):
            self.skipTest("Binary system planets not available as Planet instances")

        # Guard: different parent stars
        if alpha_prime.orbits == beta_major.orbits:
            self.skipTest("Planets unexpectedly orbit same star; cannot exercise different-parent fallback")

        a1 = getattr(alpha_prime, "orbital_distance_au", None)
        a2 = getattr(beta_major, "orbital_distance_au", None)
        if a1 is None or a2 is None:
            self.skipTest("Missing orbital_distance_au for binary system planets")

        d, unit = get_distance_between(alpha_prime, beta_major)
        self.assertEqual(unit, "au")
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, abs(a2 - a1), places=12)

    def test_station_to_parent_uses_default_orbit_when_min_safe_orbit_raises(self):
        """
        Defensive fallback: if parent.get_min_safe_orbit_km() errors, we fall back to ~400 km.
        """
        from unittest.mock import patch
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet
        from mysite.universe.models.scale import Scale

        g = Galaxy.objects.create(name="Error Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="Error System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
            system_age_years=1e9,
        )
        star = Star.objects.create(name="Error Star", orbits=system, star_type="G")
        planet = Planet.objects.create(
            name="Error Planet",
            orbits=star,
            planet_type="TE",
            radius_km=1000.0,
            orbital_distance_au=1.0,
        )
        station = Station.objects.create(
            name="Error Station",
            orbits=planet,
            scale=Scale.STATION,
            orbital_distance_km=None,
        )

        with patch.object(planet, "get_min_safe_orbit_km", side_effect=RuntimeError("boom")):
            d, unit = get_distance_between(station, planet)

        self.assertEqual(unit, "au")
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 400.0 / 1.496e8, places=12)


class LocationServiceFallbacksTest(TestCase):
    """Targeted tests for location_service fallback branches that can bite later."""

    def test_get_distance_between_different_systems_returns_none_when_system_coords_missing(self):
        """
        If two locations are in different star systems and either system lacks coords,
        we must return (None, 'ly') rather than a bogus distance.
        """
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet

        g = Galaxy.objects.create(name="MissingCoords Galaxy", galaxy_type="SP", galaxy_size="L")
        sys1 = StarSystem.objects.create(
            name="Sys1",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
            system_age_years=1e9,
        )
        sys2 = StarSystem.objects.create(name="Sys2", orbits=g)  # missing coords

        s1 = Star.objects.create(name="S1", orbits=sys1, star_type="G")
        s2 = Star.objects.create(name="S2", orbits=sys2, star_type="G")
        p1 = Planet.objects.create(name="P1", orbits=s1, planet_type="TE", orbital_distance_au=1.0, orbital_period_days=365.25)
        p2 = Planet.objects.create(name="P2", orbits=s2, planet_type="TE", orbital_distance_au=1.5, orbital_period_days=500.0)

        d, unit = get_distance_between(p1, p2)
        self.assertEqual(unit, "ly")
        self.assertIsNone(d)

    def test_get_distance_between_star_systems_returns_inf_when_first_missing_coords(self):
        """Cover the 'system1 missing coords' branch in get_distance_between_star_systems()."""
        from mysite.universe.models.celestial import Galaxy, StarSystem

        g = Galaxy.objects.create(name="Inf Galaxy", galaxy_type="SP", galaxy_size="L")
        sys_missing = StarSystem.objects.create(name="Inf Missing", orbits=g)
        sys_with = StarSystem.objects.create(
            name="Inf With",
            orbits=g,
            galactic_x_ly=1.0,
            galactic_y_ly=2.0,
            galactic_z_ly=3.0,
        )
        self.assertEqual(get_distance_between_star_systems(sys_missing, sys_with), float("inf"))

    def test_planet_to_planet_same_star_falls_back_when_system_age_missing(self):
        """If system_age_years is missing, planet distance falls back to |a2-a1|."""
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet

        g = Galaxy.objects.create(name="Age Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="Age System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
            system_age_years=None,
        )
        star = Star.objects.create(name="Age Star", orbits=system, star_type="G")
        p1 = Planet.objects.create(name="Age P1", orbits=star, planet_type="TE", orbital_distance_au=1.0, orbital_period_days=300.0)
        p2 = Planet.objects.create(name="Age P2", orbits=star, planet_type="TE", orbital_distance_au=1.6, orbital_period_days=500.0)

        d, unit = get_distance_between(p1, p2)
        self.assertEqual(unit, "au")
        self.assertAlmostEqual(d, abs(1.6 - 1.0), places=12)

    def test_planet_to_planet_same_star_falls_back_when_orbital_period_missing(self):
        """If orbital periods are missing, planet distance falls back to |a2-a1|."""
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet

        g = Galaxy.objects.create(name="Period Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="Period System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
            system_age_years=4.0e9,
        )
        star = Star.objects.create(name="Period Star", orbits=system, star_type="G")
        p1 = Planet.objects.create(name="Period P1", orbits=star, planet_type="TE", orbital_distance_au=1.0, orbital_period_days=300.0)
        p2 = Planet.objects.create(name="Period P2", orbits=star, planet_type="TE", orbital_distance_au=1.6, orbital_period_days=None)

        d, unit = get_distance_between(p1, p2)
        self.assertEqual(unit, "au")
        self.assertAlmostEqual(d, abs(1.6 - 1.0), places=12)

    def test_calculate_same_parent_distance_prefers_orbital_distance_au(self):
        """Directly exercise the helper branch that reads orbital_distance_au."""
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet

        g = Galaxy.objects.create(name="Tri Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="Tri System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Tri Star", orbits=system, star_type="G")
        p1 = Planet.objects.create(name="Tri P1", orbits=star, planet_type="TE", orbital_distance_au=1.0)
        p2 = Planet.objects.create(name="Tri P2", orbits=star, planet_type="TE", orbital_distance_au=2.0)

        d, unit = _calculate_same_parent_distance(p1, p2, star)
        self.assertEqual(unit, "au")
        # law of cosines with 60 degrees
        expected = math.sqrt(1.0**2 + 2.0**2 - 2 * 1.0 * 2.0 * math.cos(math.radians(60.0)))
        self.assertAlmostEqual(d, expected, places=12)

    def test_get_orbital_distance_from_parent_converts_km_to_au_for_moon(self):
        """Directly exercise km→AU conversion branch for Moon orbital_distance_km."""
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet, Moon

        g = Galaxy.objects.create(name="Moon Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="Moon System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Moon Star", orbits=system, star_type="G")
        planet = Planet.objects.create(name="Moon Parent", orbits=star, planet_type="TE", orbital_distance_au=1.0)
        moon = Moon.objects.create(name="Moon Child", orbits=planet, moon_type="R", orbital_distance_km=384400.0)

        d_au = _get_orbital_distance_from_parent(moon, planet)
        self.assertAlmostEqual(d_au, 384400.0 / 1.496e8, places=12)

    def test_get_orbital_parent_returns_orbits_for_orbiting_objects(self):
        """Directly exercise _get_orbital_parent's happy path."""
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet

        g = Galaxy.objects.create(name="Parent Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="Parent System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Parent Star", orbits=system, star_type="G")
        planet = Planet.objects.create(name="Parent Planet", orbits=star, planet_type="TE", orbital_distance_au=1.0)

        self.assertEqual(_get_orbital_parent(planet), star)

    def test_get_orbital_distance_from_parent_returns_au_for_planet(self):
        """Planet orbital_distance_au should round-trip through _get_orbital_distance_from_parent()."""
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet

        g = Galaxy.objects.create(name="AU Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="AU System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
            system_age_years=1e9,
        )
        star = Star.objects.create(name="AU Star", orbits=system, star_type="G")
        planet = Planet.objects.create(name="AU Planet", orbits=star, planet_type="TE", orbital_distance_au=1.234)

        self.assertAlmostEqual(_get_orbital_distance_from_parent(planet, star), 1.234, places=12)

        # Also cover the public path: planet to its parent should return orbital distance
        d, unit = get_distance_between(planet, star)
        self.assertEqual(unit, "au")
        self.assertAlmostEqual(d, 1.234, places=12)

    def test_get_distance_between_returns_unknown_when_no_orbital_context(self):
        """Two disconnected galaxies have no distance model; should return (None, 'unknown')."""
        from mysite.universe.models.celestial import Galaxy

        g1 = Galaxy.objects.create(name="NoCtx G1", galaxy_type="SP", galaxy_size="L")
        g2 = Galaxy.objects.create(name="NoCtx G2", galaxy_type="SP", galaxy_size="L")
        d, unit = get_distance_between(g1, g2)
        self.assertEqual(unit, "unknown")
        self.assertIsNone(d)

    def test_calculate_planet_to_planet_distance_returns_none_without_star(self):
        """Defensive: if a planet has no star, helper returns None (no crash)."""

        class _FakePlanet:
            orbits = None

        d = _calculate_planet_to_planet_distance(_FakePlanet(), _FakePlanet(), 1.0, 2.0)
        self.assertIsNone(d)

    def test_calculate_planet_to_planet_distance_returns_none_when_system_is_not_starsystem(self):
        """Defensive: if star.orbits is not a StarSystem, helper returns None."""
        from mysite.universe.models.base import Location
        from mysite.universe.models.scale import Scale

        class _FakeStar:
            def __init__(self, orbits):
                self.orbits = orbits

        class _FakePlanet:
            def __init__(self, orbits):
                self.orbits = orbits

        not_a_system = Location.objects.create(name="NotAStarSystem", scale=Scale.STATION)
        star = _FakeStar(orbits=not_a_system)
        planet = _FakePlanet(orbits=star)

        d = _calculate_planet_to_planet_distance(planet, planet, 1.0, 2.0)
        self.assertIsNone(d)

    def test_get_orbital_distance_from_parent_returns_none_for_star(self):
        """Stars do not have orbital distances from their parent StarSystem in this model."""
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star

        g = Galaxy.objects.create(name="NoOrbit Galaxy", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="NoOrbit System",
            orbits=g,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="NoOrbit Star", orbits=system, star_type="G")
        self.assertIsNone(_get_orbital_distance_from_parent(star, system))
