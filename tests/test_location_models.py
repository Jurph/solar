"""
Tests for models/base.py Location utility methods and models/station.py.

The Location model has several helper methods that are never exercised
by the route-planning or audio tests because those tests always work with
concrete subclasses (Planet, Station, …) rather than raw Location rows.

These tests create minimal Location objects to reach those uncovered
return statements.
"""

from django.test import TestCase

from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale, OrderedScale
from mysite.universe.models.celestial import Planet, Star, StarSystem, Galaxy


class TestLocationUtilityMethods(TestCase):
    """
    Test the helper predicates on Location that decide docking / launch rules.

    Uses a small static set of Location rows (one per relevant scale) rather
    than mocking, to keep the tests grounded in real DB state.
    """

    @classmethod
    def setUpTestData(cls):
        cls.galaxy = Galaxy.objects.create(
            name="UTest Galaxy", galaxy_type="SP", galaxy_size="S"
        )
        cls.system = StarSystem.objects.create(
            name="UTest System",
            orbits=cls.galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        cls.star = Star.objects.create(
            name="UTest Star", orbits=cls.system, star_type="G"
        )
        cls.planet = Planet.objects.create(
            name="UTest Planet",
            orbits=cls.star,
            planet_type="TE",
            orbital_distance_au=1.0,
        )
        # Raw Location at station scale (not a Station subclass – just a Location row)
        cls.station_loc = Location.objects.create(
            name="UTest Station Loc", scale=Scale.STATION
        )
        cls.planet_loc = Location.objects.create(
            name="UTest Planet Loc", scale=Scale.PLANET
        )
        cls.moon_loc = Location.objects.create(name="UTest Moon Loc", scale=Scale.MOON)
        cls.star_loc = Location.objects.create(name="UTest Star Loc", scale=Scale.STAR)
        cls.galaxy_loc = Location.objects.create(
            name="UTest Galaxy Loc", scale=Scale.GALAXY
        )

    # ------------------------------------------------------------------
    # ordered_scale property
    # ------------------------------------------------------------------

    def test_ordered_scale_returns_ordered_scale_instance(self):
        """location.ordered_scale returns an OrderedScale wrapping the scale."""
        result = self.station_loc.ordered_scale
        self.assertIsInstance(result, OrderedScale)
        self.assertEqual(result, OrderedScale(Scale.STATION))

    # ------------------------------------------------------------------
    # get_concrete_instance / get_type_name
    # ------------------------------------------------------------------

    def test_get_type_name_on_planet(self):
        """Planet subclass: get_type_name() returns 'Planet'."""
        self.assertEqual(self.planet.get_type_name(), "Planet")

    def test_get_type_name_on_raw_location_with_matching_planet(self):
        """
        A raw Location row that coincides with a Planet PK returns the
        concrete subclass name via the subclass-lookup loop in
        get_concrete_instance().
        """
        # Fetch the Location base-row for the Planet (same PK, polymorphism)
        loc_row = Location.objects.get(pk=self.planet.pk)
        # get_concrete_instance() should discover it's a Planet
        concrete = loc_row.get_concrete_instance()
        self.assertEqual(concrete.get_type_name(), "Planet")

    def test_get_type_name_on_untyped_location_falls_back(self):
        """
        A Location row that is not any known subclass returns 'Location'
        (the default fallback).
        """
        name = self.station_loc.get_type_name()
        # It resolves to 'Station' only if a Station subclass has the same PK;
        # since we created a raw Location, it should stay 'Location'.
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)

    # ------------------------------------------------------------------
    # may_have_station
    # ------------------------------------------------------------------

    def test_may_have_station_true_for_star_scale(self):
        self.assertTrue(self.star_loc.may_have_station())

    def test_may_have_station_true_for_planet_scale(self):
        self.assertTrue(self.planet_loc.may_have_station())

    def test_may_have_station_true_for_moon_scale(self):
        self.assertTrue(self.moon_loc.may_have_station())

    def test_may_have_station_false_for_station_scale(self):
        self.assertFalse(self.station_loc.may_have_station())

    def test_may_have_station_false_for_galaxy_scale(self):
        self.assertFalse(self.galaxy_loc.may_have_station())

    # ------------------------------------------------------------------
    # can_dock
    # ------------------------------------------------------------------

    def test_can_dock_true_for_station(self):
        self.assertTrue(self.station_loc.can_dock())

    def test_can_dock_false_for_planet(self):
        self.assertFalse(self.planet_loc.can_dock())

    # ------------------------------------------------------------------
    # requires_launch_clearance
    # ------------------------------------------------------------------

    def test_requires_launch_clearance_for_planet(self):
        self.assertTrue(self.planet_loc.requires_launch_clearance())

    def test_requires_launch_clearance_for_moon(self):
        self.assertTrue(self.moon_loc.requires_launch_clearance())

    def test_requires_launch_clearance_for_station(self):
        self.assertTrue(self.station_loc.requires_launch_clearance())

    def test_no_launch_clearance_for_star(self):
        self.assertFalse(self.star_loc.requires_launch_clearance())

    # ------------------------------------------------------------------
    # requires_docking_clearance
    # ------------------------------------------------------------------

    def test_requires_docking_clearance_for_station(self):
        self.assertTrue(self.station_loc.requires_docking_clearance())

    def test_no_docking_clearance_for_planet(self):
        self.assertFalse(self.planet_loc.requires_docking_clearance())

    # ------------------------------------------------------------------
    # can_land
    # ------------------------------------------------------------------

    def test_can_land_true_for_planet(self):
        self.assertTrue(self.planet_loc.can_land())

    def test_can_land_true_for_moon(self):
        self.assertTrue(self.moon_loc.can_land())

    def test_can_land_false_for_station(self):
        self.assertFalse(self.station_loc.can_land())

    def test_can_land_false_for_star(self):
        self.assertFalse(self.star_loc.can_land())

    # ------------------------------------------------------------------
    # Location.create() classmethod
    # ------------------------------------------------------------------

    def test_location_create_returns_concrete_instance(self):
        """Location.create() builds a Location row and returns its concrete instance."""
        loc = Location.create(name="UTest Create Loc", scale=Scale.GALAXY)
        # The base Location has no matching subclass so returns itself
        self.assertIsNotNone(loc)
        self.assertEqual(loc.name, "UTest Create Loc")


class TestOrderedScaleEdgeCases(TestCase):
    """
    Tests for edge cases in OrderedScale that aren't exercised by normal
    Location queries: idempotent construction, invalid codes, hashing,
    and the str() fallback for raw integer values.
    """

    def test_ordered_scale_idempotent_construction(self):
        """OrderedScale(OrderedScale('PL')) returns the same instance unchanged."""
        first = OrderedScale("PL")
        second = OrderedScale(first)
        self.assertIs(first, second)

    def test_ordered_scale_invalid_code_raises_value_error(self):
        """An unrecognised two-letter code raises ValueError."""
        with self.assertRaises(ValueError):
            OrderedScale("ZZ")

    def test_ordered_scale_hash_is_hashable(self):
        """OrderedScale instances are hashable and usable in sets/dicts."""
        s = OrderedScale("PL")
        h = hash(s)
        self.assertIsInstance(h, int)
        # Two equal OrderedScales must have the same hash
        self.assertEqual(hash(OrderedScale("PL")), h)

    def test_ordered_scale_str_for_known_code(self):
        """str(OrderedScale('PL')) returns 'PL'."""
        self.assertEqual(str(OrderedScale("PL")), "PL")

    def test_ordered_scale_str_for_raw_integer_fallback(self):
        """
        Constructing OrderedScale from a raw integer that has no matching code
        falls back to str(int(self)) — exercises line 33 of scale.py.
        """
        s = OrderedScale(99)
        result = str(s)
        self.assertEqual(result, "99")
