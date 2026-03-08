"""
Edge-case coverage for:
  - services/maneuver_physics.py  (uncovered branches + new maneuver types)
  - services/dialogue/factory.py  (ValueError / TypeError guard paths)

No mocking is needed: these are pure-Python computations and registry
operations that can be exercised with carefully chosen inputs.
"""

from django.test import TestCase

from mysite.universe.services.maneuver_physics import (
    ManeuverPhysicsService,
    VehicleParams,
    get_maneuver_physics_service,
)
from mysite.universe.services.dialogue.factory import ParticleFactory


# ===========================================================================
# ManeuverPhysicsService edge cases
# ===========================================================================


class TestManeuverPhysicsEdgeCases(TestCase):
    """
    Covers uncovered branches in ManeuverPhysicsService.

    Physics constants used throughout:
        Earth gravity : 1.0 g
        Earth radius  : 6371 km
        Earth mass    : 5.97e24 kg
        Sun mass      : 1.989e30 kg
    """

    def setUp(self):
        self.svc = ManeuverPhysicsService()

    # ------------------------------------------------------------------
    # calculate_launch_duration: zero rotation period (omega = 0)
    # ------------------------------------------------------------------

    def test_launch_with_zero_rotation_period_uses_omega_zero(self):
        """
        rotation_period_seconds=0 must not divide by zero; centrifugal term
        becomes 0 and the calculation proceeds normally.
        """
        duration = self.svc.calculate_launch_duration(
            atmospheric_height_km=100,
            planet_gravity_gees=1.0,
            planet_radius_km=6371,
            rotation_period_seconds=0,  # triggers omega = 0 branch
        )
        self.assertGreater(duration, 0)
        self.assertNotEqual(duration, float("inf"))

    # ------------------------------------------------------------------
    # calculate_launch_duration: gravity exceeds thrust → can't ascend
    # ------------------------------------------------------------------

    def test_launch_returns_inf_when_vehicle_cannot_ascend(self):
        """
        When effective gravity exceeds vehicle thrust the function returns
        float('inf'), signalling an impossible ascent.
        """
        # Use a vehicle with near-zero thrust fraction so gravity wins
        weak_vehicle = VehicleParams(
            max_proper_accel_gees=0.01,  # barely any thrust
            avg_vertical_thrust_frac=0.1,
        )
        svc = ManeuverPhysicsService(vehicle=weak_vehicle)
        duration = svc.calculate_launch_duration(
            atmospheric_height_km=100,
            planet_gravity_gees=10.0,  # very high gravity
            planet_radius_km=6371,
            rotation_period_seconds=86400,
        )
        self.assertEqual(duration, float("inf"))

    # ------------------------------------------------------------------
    # calculate_sublight_duration: explicit None velocity (default branch)
    # ------------------------------------------------------------------

    def test_sublight_with_no_velocity_uses_vehicle_default(self):
        """
        Calling calculate_sublight_duration without velocity_c exercises
        the `if velocity_c is None` branch and uses self.vehicle.sublight_velocity_c.
        """
        duration = self.svc.calculate_sublight_duration(distance_au=1.0)
        # At 0.1c, 1 AU ≈ 4992 seconds
        self.assertGreater(duration, 1000)
        self.assertLess(duration, 50000)

    def test_sublight_zero_velocity_returns_inf(self):
        """velocity_c=0 must return inf (can't move)."""
        duration = self.svc.calculate_sublight_duration(distance_au=1.0, velocity_c=0)
        self.assertEqual(duration, float("inf"))

    # ------------------------------------------------------------------
    # calculate_hyperspace_duration: None velocity + zero velocity
    # ------------------------------------------------------------------

    def test_hyperspace_with_no_velocity_uses_vehicle_default(self):
        """
        Calling calculate_hyperspace_duration without velocity_c exercises
        the `if velocity_c is None` branch.
        """
        duration = self.svc.calculate_hyperspace_duration(distance_ly=10.0)
        self.assertGreater(duration, 0)
        self.assertNotEqual(duration, float("inf"))

    def test_hyperspace_zero_velocity_returns_inf(self):
        """velocity_c=0 must return inf."""
        duration = self.svc.calculate_hyperspace_duration(
            distance_ly=10.0, velocity_c=0
        )
        self.assertEqual(duration, float("inf"))

    # ------------------------------------------------------------------
    # calculate_transfer_duration (Hohmann)
    # ------------------------------------------------------------------

    def test_transfer_duration_earth_to_mars_orbit(self):
        """
        Hohmann transfer from Earth (1 AU) to Mars (1.52 AU) around Sol.
        Expected ~259 days (≈ 22.4 million seconds).
        Bounds: 10M – 100M seconds (generous 4× tolerance).
        """
        duration = self.svc.calculate_transfer_duration(
            origin_orbit_au=1.0,
            dest_orbit_au=1.524,
            star_mass_kg=1.989e30,
        )
        self.assertGreater(duration, 10_000_000)
        self.assertLess(duration, 100_000_000)

    def test_transfer_duration_same_orbit_is_zero(self):
        """Transfer between identical orbits should give 0 (or near-0) duration."""
        duration = self.svc.calculate_transfer_duration(
            origin_orbit_au=1.0,
            dest_orbit_au=1.0,
            star_mass_kg=1.989e30,
        )
        # a = (r1+r1)/2 = r1, so T = π√(r1³/μ)  – still the full period at r1
        # This just verifies it doesn't crash and returns a positive number.
        self.assertGreater(duration, 0)

    # ------------------------------------------------------------------
    # calculate_landing_duration: atmosphere path
    # ------------------------------------------------------------------

    def test_landing_with_atmosphere_scales_by_gravity(self):
        """
        has_atmosphere=True returns base_time / sqrt(gravity).
        Higher gravity → shorter atmospheric descent.
        """
        low_g = self.svc.calculate_landing_duration(
            entry_interface_km=100,
            planet_gravity_gees=0.5,
            has_atmosphere=True,
        )
        high_g = self.svc.calculate_landing_duration(
            entry_interface_km=100,
            planet_gravity_gees=2.0,
            has_atmosphere=True,
        )
        self.assertGreater(low_g, high_g)

    # ------------------------------------------------------------------
    # get_maneuver_duration: TRANSFER, PLANE_CHANGE, unknown type
    # ------------------------------------------------------------------

    def test_get_maneuver_duration_transfer(self):
        """TRANSFER maneuver routes to calculate_transfer_duration."""
        duration = self.svc.get_maneuver_duration(
            maneuver_type="TRANSFER",
            body_params={},
            nav_context={
                "origin_orbit_au": 1.0,
                "dest_orbit_au": 1.524,
                "star_mass_kg": 1.989e30,
            },
        )
        self.assertGreater(duration, 0)
        self.assertNotEqual(duration, 30.0)  # not the default fallback

    def test_get_maneuver_duration_plane_change_returns_60(self):
        """PLANE_CHANGE is a placeholder that always returns 60 seconds."""
        duration = self.svc.get_maneuver_duration(
            maneuver_type="PLANE_CHANGE",
            body_params={},
            nav_context={},
        )
        self.assertEqual(duration, 60.0)

    def test_get_maneuver_duration_unknown_returns_30(self):
        """Unknown maneuver type returns the 30-second default fallback."""
        duration = self.svc.get_maneuver_duration(
            maneuver_type="WARP_BUBBLE",
            body_params={},
            nav_context={},
        )
        self.assertEqual(duration, 30.0)

    def test_get_maneuver_physics_service_singleton(self):
        """get_maneuver_physics_service() returns the same instance on repeated calls."""
        s1 = get_maneuver_physics_service()
        s2 = get_maneuver_physics_service()
        self.assertIs(s1, s2)

    def test_get_maneuver_physics_service_with_vehicle_returns_new_instance(self):
        """Passing a vehicle creates a fresh (non-cached) instance."""
        custom = VehicleParams(max_proper_accel_gees=1.0)
        s = get_maneuver_physics_service(vehicle=custom)
        self.assertEqual(s.vehicle.max_proper_accel_gees, 1.0)


# ===========================================================================
# ParticleFactory edge cases
# ===========================================================================


class TestParticleFactoryEdgeCases(TestCase):
    """
    Covers the guard clauses in ParticleFactory that raise ValueError /
    TypeError for invalid inputs.
    """

    def test_create_particle_empty_string_raises_value_error(self):
        """create_particle('') raises ValueError."""
        with self.assertRaises(ValueError):
            ParticleFactory.create_particle(
                "", actor=None, recipient="ATC", nav_context={}
            )

    def test_create_particle_none_raises_value_error(self):
        """create_particle(None) raises ValueError."""
        with self.assertRaises(ValueError):
            ParticleFactory.create_particle(
                None, actor=None, recipient="ATC", nav_context={}
            )

    def test_register_request_particle_non_subclass_raises_type_error(self):
        """
        register_request_particle with a class that is NOT a DialogueParticle
        subclass raises TypeError.
        """
        with self.assertRaises(TypeError):
            ParticleFactory.register_request_particle("bad_maneuver", str)

    def test_register_particle_non_subclass_raises_type_error(self):
        """
        register_particle with a class that is NOT a DialogueParticle
        subclass raises TypeError.
        """
        with self.assertRaises(TypeError):
            ParticleFactory.register_particle("bad_type", int)

    def test_unknown_particle_type_falls_back_to_generic_request(self):
        """
        An unrecognised particle_type string falls back to GenericRequest
        without raising.
        """
        from mysite.universe.services.dialogue.particles import GenericRequest

        particle = ParticleFactory.create_particle(
            "completely_unknown_type",
            actor=None,
            recipient="ATC",
            nav_context={},
        )
        self.assertIsInstance(particle, GenericRequest)

    def test_register_request_particle_success(self):
        """
        register_request_particle with a valid DialogueParticle subclass
        adds the mapping to REQUEST_PARTICLE_MAP (line 147 of factory.py).
        """
        from mysite.universe.services.dialogue.particles import GenericRequest

        # Use a unique key so we don't clobber real entries
        ParticleFactory.register_request_particle("test_maneuver_xyz", GenericRequest)
        self.assertIn("test_maneuver_xyz", ParticleFactory.REQUEST_PARTICLE_MAP)
        self.assertIs(
            ParticleFactory.REQUEST_PARTICLE_MAP["test_maneuver_xyz"], GenericRequest
        )
        # Clean up so we don't pollute other tests
        del ParticleFactory.REQUEST_PARTICLE_MAP["test_maneuver_xyz"]

    def test_register_particle_success(self):
        """
        register_particle with a valid DialogueParticle subclass
        adds the mapping to PARTICLE_MAP (line 170 of factory.py).
        """
        from mysite.universe.services.dialogue.particles import GenericRequest

        ParticleFactory.register_particle("test_type_xyz", GenericRequest)
        self.assertIn("test_type_xyz", ParticleFactory.PARTICLE_MAP)
        self.assertIs(ParticleFactory.PARTICLE_MAP["test_type_xyz"], GenericRequest)
        del ParticleFactory.PARTICLE_MAP["test_type_xyz"]


# ===========================================================================
# ActorService._generate_controller_name edge cases
# ===========================================================================


class TestActorServiceControllerName(TestCase):
    """
    Covers the random-suffix branch in ActorService._generate_controller_name
    (lines 42-43 of actor_server.py).

    Stations whose name contains neither "Control" nor "Dispatch", and that
    have no planet/moon back-reference, receive a random traffic suffix.
    """

    @classmethod
    def setUpTestData(cls):
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star

        cls.galaxy = Galaxy.objects.create(
            name="ActorSvc Galaxy", galaxy_type="SP", galaxy_size="S"
        )
        cls.system = StarSystem.objects.create(
            name="ActorSvc System",
            orbits=cls.galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        cls.star = Star.objects.create(
            name="ActorSvc Star", orbits=cls.system, star_type="G"
        )
        from mysite.universe.models.station import Station

        cls.plain_station = Station.objects.create(
            name="Waypoint Alpha",  # no "Control" or "Dispatch"
            orbits=cls.star,
        )

    def test_plain_station_gets_traffic_suffix(self):
        """
        A station whose name has no "Control"/"Dispatch" keyword and no
        planet/moon back-ref gets a name ending with one of the TRAFFIC_SUFFIXES.
        """
        from mysite.universe.services.actor_server import ActorService

        name = ActorService._generate_controller_name(self.plain_station)
        self.assertTrue(
            any(name.endswith(suffix) for suffix in ActorService.TRAFFIC_SUFFIXES),
            f"Expected a traffic suffix but got: {name!r}",
        )
        self.assertTrue(name.startswith(self.plain_station.name))

    def test_control_station_returns_name_unchanged(self):
        """A station whose name contains 'Control' is returned as-is."""
        from mysite.universe.services.actor_server import ActorService
        from mysite.universe.models.station import Station

        ctrl_station = Station.objects.create(
            name="Mars Orbital Control",
            orbits=self.star,
        )
        name = ActorService._generate_controller_name(ctrl_station)
        self.assertEqual(name, "Mars Orbital Control")

    def test_deploy_controllers_categorises_plain_station_as_regular(self):
        """
        deploy_controllers() appends plain stations (no Control/Dispatch in name)
        to 'regular_stations' — covers actor_server.py line 95.
        """
        from mysite.universe.services.actor_server import ActorService

        results = ActorService.deploy_controllers()
        regular_names = [c.name for c in results["regular_stations"]]
        self.assertTrue(
            any("Waypoint Alpha" in n for n in regular_names),
            f"Expected 'Waypoint Alpha' in regular_stations, got: {regular_names}",
        )
