"""
Tests for ControllerPhysicsService.

Covers:
- get_relevant_body() for all maneuver categories (arrival, departure, transfer)
- get_relevant_body() edge cases (no controller location, station with parent body)
- Parameter generation for each maneuver type
- Fallback behavior when bodies are missing
"""

from django.test import TestCase

from mysite.universe.models.actor import Controller
from mysite.universe.models.celestial import Planet, Star, StarSystem, Galaxy
from mysite.universe.models.scale import Scale
from mysite.universe.models.station import Station
from mysite.universe.services.controller_physics import ControllerPhysicsService


class ControllerPhysicsTestBase(TestCase):
    """Shared fixtures for ControllerPhysicsService tests."""

    @classmethod
    def setUpTestData(cls):
        galaxy = Galaxy.objects.create(name="Test Galaxy CP", scale=Scale.GALAXY)
        system = StarSystem.objects.create(
            name="Test System CP", scale=Scale.STARSYSTEM, orbits=galaxy
        )
        star = Star.objects.create(
            name="Test Star CP", scale=Scale.STAR, star_type="G", orbits=system
        )

        cls.origin_planet = Planet.objects.create(
            name="Origin World",
            scale=Scale.PLANET,
            orbital_distance_au=1.0,
            orbital_period_days=365.25,
            mass_kg=5.972e24,
            radius_km=6371.0,
            axial_tilt_deg=23.4,
            orbital_inclination_deg=0.0,
            orbits=star,
            planet_type="TE",
        )
        cls.destination_planet = Planet.objects.create(
            name="Destination World",
            scale=Scale.PLANET,
            orbital_distance_au=1.52,
            orbital_period_days=686.97,
            mass_kg=6.39e23,
            radius_km=3389.5,
            axial_tilt_deg=25.19,
            orbital_inclination_deg=1.85,
            orbits=star,
            planet_type="TE",
        )

        cls.origin_station = Station.objects.create(
            name="Origin Station",
            scale=Scale.STATION,
            orbits=cls.origin_planet,
            large_berths=1,
        )
        cls.dest_station = Station.objects.create(
            name="Destination Station",
            scale=Scale.STATION,
            orbits=cls.destination_planet,
            large_berths=1,
        )

        cls.controller = Controller.create(location=cls.origin_station)
        cls.controller.name = "Origin Control"
        cls.controller.save()

    def _nav_ctx(self, maneuver_type, **kwargs):
        base = {
            "maneuver_type": maneuver_type,
            "current_location": self.origin_planet.name,
            "origin": self.origin_planet.name,
            "destination": self.destination_planet.name,
        }
        base.update(kwargs)
        return base


class TestGetRelevantBody(ControllerPhysicsTestBase):
    """Tests for ControllerPhysicsService.get_relevant_body()."""

    def test_launch_uses_origin_planet(self):
        """LAUNCH uses origin/current location body."""
        nav_ctx = self._nav_ctx("LAUNCH")
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)
        self.assertEqual(body.name, self.origin_planet.name)

    def test_undock_uses_origin_planet(self):
        """UNDOCK uses origin/current location body."""
        nav_ctx = self._nav_ctx("UNDOCK")
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)

    def test_insertion_uses_destination_planet(self):
        """INSERTION uses destination body."""
        nav_ctx = self._nav_ctx("INSERTION")
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)
        self.assertEqual(body.name, self.destination_planet.name)

    def test_deorbit_uses_destination_planet(self):
        """DEORBIT uses destination body."""
        nav_ctx = self._nav_ctx("DEORBIT")
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)
        self.assertEqual(body.name, self.destination_planet.name)

    def test_landing_uses_destination_planet(self):
        """LANDING uses destination body."""
        nav_ctx = self._nav_ctx("LANDING")
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)
        self.assertEqual(body.name, self.destination_planet.name)

    def test_dock_uses_destination_planet(self):
        """DOCK uses destination body."""
        nav_ctx = self._nav_ctx("DOCK")
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)
        self.assertEqual(body.name, self.destination_planet.name)

    def test_sublight_uses_current_location(self):
        """SUBLIGHT uses current_location body."""
        nav_ctx = self._nav_ctx("SUBLIGHT")
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)
        self.assertEqual(body.name, self.origin_planet.name)

    def test_circularization_uses_current_location(self):
        """CIRCULARIZATION uses current_location body."""
        nav_ctx = self._nav_ctx("CIRCULARIZATION")
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)

    def test_no_controller_location_returns_none(self):
        """Controller without a location returns None."""
        homeless_ctrl = Controller.create()
        homeless_ctrl.location = None
        homeless_ctrl.save()
        nav_ctx = self._nav_ctx("LAUNCH")
        body = ControllerPhysicsService.get_relevant_body(homeless_ctrl, nav_ctx)
        self.assertIsNone(body)

    def test_destination_is_station_resolves_to_parent_planet(self):
        """When destination is a station, resolves to the planet it orbits."""
        nav_ctx = self._nav_ctx("INSERTION", destination=self.dest_station.name)
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        self.assertIsNotNone(body)
        self.assertEqual(body.name, self.destination_planet.name)

    def test_missing_location_name_returns_none(self):
        """Missing origin and current_location returns None without crashing."""
        nav_ctx = {"maneuver_type": "LAUNCH"}  # No origin or current_location
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        # Code returns None early when target_location_name is falsy
        self.assertIsNone(body)

    def test_unknown_location_name_falls_back_to_station_orbits(self):
        """When location name doesn't match a DB record, falls back to controller's station."""
        nav_ctx = {
            "maneuver_type": "LAUNCH",
            "origin": "UnknownPlanetXYZ",
            "current_location": "UnknownPlanetXYZ",
        }
        body = ControllerPhysicsService.get_relevant_body(self.controller, nav_ctx)
        # Falls through to station.orbits → origin_planet
        self.assertIsNotNone(body)
        self.assertEqual(body.name, self.origin_planet.name)


class TestGenerateParameters(ControllerPhysicsTestBase):
    """Tests for parameter generation methods."""

    def test_launch_parameters_have_required_keys(self):
        """generate_launch_parameters() returns inclination, apogee, azimuth."""
        body = self.origin_planet
        params = ControllerPhysicsService.generate_launch_parameters(body, {})
        self.assertIn("inclination_deg", params)
        self.assertIn("apogee_km", params)
        self.assertIn("azimuth_deg", params)

    def test_launch_azimuth_in_valid_range(self):
        """Launch azimuth is 0–360 degrees."""
        body = self.origin_planet
        for _ in range(10):
            params = ControllerPhysicsService.generate_launch_parameters(body, {})
            self.assertGreaterEqual(params["azimuth_deg"], 0.0)
            self.assertLessEqual(params["azimuth_deg"], 360.0)

    def test_launch_inclination_in_valid_range(self):
        """Launch inclination is 0–180 degrees."""
        body = self.origin_planet
        params = ControllerPhysicsService.generate_launch_parameters(body, {})
        self.assertGreaterEqual(params["inclination_deg"], 0.0)
        self.assertLess(params["inclination_deg"], 180.0)

    def test_circularization_parameters_have_required_keys(self):
        """generate_circularization_parameters() returns altitude and inclination."""
        body = self.origin_planet
        params = ControllerPhysicsService.generate_circularization_parameters(body, {})
        self.assertIn("altitude_km", params)
        self.assertIn("inclination_deg", params)

    def test_circularization_altitude_positive(self):
        """Circularization altitude is a positive number."""
        body = self.origin_planet
        params = ControllerPhysicsService.generate_circularization_parameters(body, {})
        self.assertGreater(params["altitude_km"], 0.0)

    def test_insertion_same_as_circularization(self):
        """Insertion returns same structure as circularization."""
        body = self.destination_planet
        params = ControllerPhysicsService.generate_insertion_parameters(body, {})
        self.assertIn("altitude_km", params)
        self.assertIn("inclination_deg", params)

    def test_sublight_parameters_have_azimuth(self):
        """generate_sublight_parameters() returns azimuth_deg."""
        nav_ctx = self._nav_ctx("SUBLIGHT")
        params = ControllerPhysicsService.generate_sublight_parameters(
            self.origin_planet, nav_ctx
        )
        self.assertIn("azimuth_deg", params)
        self.assertIn("departure_angle_deg", params)

    def test_sublight_fallback_when_no_locations(self):
        """Fallback to random azimuth when origin/destination are unknown."""
        params = ControllerPhysicsService.generate_sublight_parameters(
            self.origin_planet,
            {"maneuver_type": "SUBLIGHT"},  # No origin/destination
        )
        self.assertIn("azimuth_deg", params)
        self.assertGreaterEqual(params["azimuth_deg"], 0.0)
        self.assertLessEqual(params["azimuth_deg"], 360.0)

    def test_hyperspace_returns_same_structure_as_sublight(self):
        """Hyperspace parameters have the same structure as sublight."""
        nav_ctx = self._nav_ctx("HYPERSPACE")
        params = ControllerPhysicsService.generate_hyperspace_parameters(
            self.origin_planet, nav_ctx
        )
        self.assertIn("azimuth_deg", params)

    def test_deorbit_parameters_have_required_keys(self):
        """generate_deorbit_parameters() returns deorbit_altitude and entry_angle."""
        body = self.destination_planet
        params = ControllerPhysicsService.generate_deorbit_parameters(body, {})
        self.assertIn("deorbit_altitude_km", params)
        self.assertIn("entry_angle_deg", params)

    def test_deorbit_altitude_positive(self):
        """Deorbit altitude is positive."""
        body = self.destination_planet
        params = ControllerPhysicsService.generate_deorbit_parameters(body, {})
        self.assertGreater(params["deorbit_altitude_km"], 0.0)

    def test_landing_parameters_have_required_keys(self):
        """generate_landing_parameters() returns heading and speed."""
        body = self.destination_planet
        params = ControllerPhysicsService.generate_landing_parameters(body, {})
        self.assertIn("approach_heading_deg", params)
        self.assertIn("approach_speed_ms", params)

    def test_landing_speed_positive(self):
        """Landing approach speed is positive."""
        body = self.destination_planet
        params = ControllerPhysicsService.generate_landing_parameters(body, {})
        self.assertGreater(params["approach_speed_ms"], 0.0)

    def test_plane_change_parameters_have_required_keys(self):
        """generate_plane_change_parameters() returns target_inclination_deg."""
        body = self.origin_planet
        nav_ctx = self._nav_ctx("PLANE_CHANGE")
        params = ControllerPhysicsService.generate_plane_change_parameters(
            body, nav_ctx
        )
        self.assertIn("target_inclination_deg", params)

    def test_plane_change_inclination_in_valid_range(self):
        """Plane change inclination is 0–180 degrees."""
        body = self.origin_planet
        nav_ctx = self._nav_ctx("PLANE_CHANGE")
        params = ControllerPhysicsService.generate_plane_change_parameters(
            body, nav_ctx
        )
        self.assertGreaterEqual(params["target_inclination_deg"], 0.0)
        self.assertLessEqual(params["target_inclination_deg"], 180.0)


class TestGenerateParametersDispatch(ControllerPhysicsTestBase):
    """Tests for generate_parameters() dispatch logic."""

    def test_returns_empty_when_no_body(self):
        """Returns empty dict when no relevant body found."""
        homeless_ctrl = Controller.create()
        homeless_ctrl.location = None
        homeless_ctrl.save()
        params = ControllerPhysicsService.generate_parameters(
            homeless_ctrl, {"maneuver_type": "LAUNCH"}
        )
        self.assertEqual(params, {})

    def test_launch_maneuver_dispatches_correctly(self):
        """LAUNCH maneuver returns launch-specific keys."""
        nav_ctx = self._nav_ctx("LAUNCH")
        params = ControllerPhysicsService.generate_parameters(self.controller, nav_ctx)
        self.assertIn("inclination_deg", params)
        self.assertIn("apogee_km", params)

    def test_circularization_maneuver_dispatches_correctly(self):
        """CIRCULARIZATION maneuver returns altitude and inclination."""
        nav_ctx = self._nav_ctx("CIRCULARIZATION")
        params = ControllerPhysicsService.generate_parameters(self.controller, nav_ctx)
        self.assertIn("altitude_km", params)

    def test_insertion_maneuver_dispatches_correctly(self):
        """INSERTION maneuver returns altitude and inclination."""
        nav_ctx = self._nav_ctx("INSERTION")
        params = ControllerPhysicsService.generate_parameters(self.controller, nav_ctx)
        self.assertIn("altitude_km", params)

    def test_sublight_maneuver_dispatches_correctly(self):
        """SUBLIGHT maneuver returns azimuth."""
        nav_ctx = self._nav_ctx("SUBLIGHT")
        params = ControllerPhysicsService.generate_parameters(self.controller, nav_ctx)
        self.assertIn("azimuth_deg", params)

    def test_hyperspace_maneuver_dispatches_correctly(self):
        """HYPERSPACE maneuver returns azimuth."""
        nav_ctx = self._nav_ctx("HYPERSPACE")
        params = ControllerPhysicsService.generate_parameters(self.controller, nav_ctx)
        self.assertIn("azimuth_deg", params)

    def test_deorbit_maneuver_dispatches_correctly(self):
        """DEORBIT maneuver returns deorbit_altitude_km."""
        nav_ctx = self._nav_ctx("DEORBIT")
        params = ControllerPhysicsService.generate_parameters(self.controller, nav_ctx)
        self.assertIn("deorbit_altitude_km", params)

    def test_landing_maneuver_dispatches_correctly(self):
        """LANDING maneuver returns approach_heading_deg."""
        nav_ctx = self._nav_ctx("LANDING")
        params = ControllerPhysicsService.generate_parameters(self.controller, nav_ctx)
        self.assertIn("approach_heading_deg", params)

    def test_unknown_maneuver_returns_empty(self):
        """Unknown maneuver type returns empty dict."""
        nav_ctx = self._nav_ctx("WARP_DRIVE")
        params = ControllerPhysicsService.generate_parameters(self.controller, nav_ctx)
        self.assertEqual(params, {})
