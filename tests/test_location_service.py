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

