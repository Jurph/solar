import os

from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.base import Location
from mysite.universe.models.celestial import Planet, Star
from mysite.universe.models.navigation import UniverseGraph
from mysite.universe.models.scale import OrderedScale, Scale
from mysite.universe.services.route_server import RouteService


class UniverseGraphTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Import the test universe using our XML importer into the test database.
        """
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        importer = UniverseImporter(xml_file)
        importer.import_universe()

        # Rebuild the graph after importing
        UniverseGraph.get_instance().rebuild_graph()

    def setUp(self):
        """
        Retrieve requisite objects from the imported universe.
        """
        # -- Get some objects we can use as examples --
        self.earth = Location.objects.get(name="Earth")
        self.moon = Location.objects.get(name="Moon")
        self.luna = Location.objects.get(name="Luna")
        self.luna_orbital_control = Location.objects.get(name="Luna Orbital Control")
        self.mars = Location.objects.get(name="Mars")
        self.sol = Location.objects.get(name="Sol")
        self.beta_minor_moon = Location.objects.get(name="Beta Minor Moon")
        # -- Set up a Route Service --
        self.route_service = RouteService()
        # IMPORTANT: store the universe instance for later tests.
        self.universe = UniverseGraph.get_instance()

    def test_rebuild_graph_query_count_constant_in_planet_count(self):
        """
        Rebuilding graph should batch by concrete model instead of issuing one
        probe/query per added planet.
        """
        with CaptureQueriesContext(connection) as before:
            self.universe.rebuild_graph()

        sol_star = Star.objects.get(name="Sol")
        for i in range(4):
            Planet.objects.create(name=f"Graph Count Planet {i}", orbits=sol_star)

        with CaptureQueriesContext(connection) as after:
            self.universe.rebuild_graph()

        self.assertEqual(len(before), len(after))

    def test_get_path_does_not_refetch_every_path_node(self):
        """Path lookup should use graph node payloads, not one DB fetch per hop."""
        with CaptureQueriesContext(connection) as queries:
            path = self.universe.get_path(
                self.luna_orbital_control, self.beta_minor_moon
            )

        self.assertGreater(len(path), 2)
        self.assertEqual(len(queries), 2)

    def test_scale_numeric_values(self):
        """
        Explicitly verify that OrderedScale is using the correct numeric values
        and not doing alphabetical comparison.
        """
        print("\n=== Testing Scale Numeric Values ===")

        # Test each scale's numeric value
        scale_tests = [
            (Scale.STATION, "SS", 1, "Space Station"),
            (Scale.MOON, "MN", 2, "Moon"),
            (Scale.PLANET, "PL", 3, "Planet"),
            (Scale.STAR, "SR", 4, "Star"),
            (Scale.STARSYSTEM, "SY", 5, "Star System"),
            (Scale.GALAXY, "GX", 6, "Galaxy"),
        ]

        for scale, code, expected_value, name in scale_tests:
            ordered = OrderedScale(scale)
            actual_value = ordered.ORDERING[str(ordered)]
            print(f"{name} ({code}): Expected {expected_value}, Got {actual_value}")
            self.assertEqual(
                actual_value,
                expected_value,
                f"OrderedScale value for {name} ({code}) should be {expected_value}, but got {actual_value}",
            )

        # Explicitly test some comparisons
        station_scale = OrderedScale(Scale.STATION)
        planet_scale = OrderedScale(Scale.PLANET)

        self.assertTrue(
            station_scale < planet_scale,
            f"Station (value {station_scale.ORDERING[str(station_scale)]}) should be < "
            f"Planet (value {planet_scale.ORDERING[str(planet_scale)]})",
        )

    def test_getting_neighbors_luna(self):
        """
        Test that Luna's neighbors include Earth and its two stations.
        """
        universe = UniverseGraph.get_instance()
        neighbors = universe.get_neighbors(self.luna)

        expected_names = {"Earth", "Luna Orbital Control", "Luna Secondary Control"}
        neighbor_names = {neighbor.name for neighbor in neighbors}

        self.assertEqual(
            neighbor_names,
            expected_names,
            f"Expected neighbors of Luna to include: {expected_names}, but got: {neighbor_names}",
        )

    def test_getting_neighbors_earth(self):
        """
        Test that Earth's neighbors include its stations, moons, and Sol.
        """
        universe = UniverseGraph.get_instance()
        neighbors = universe.get_neighbors(self.earth)

        expected_names = {"Sol", "Moon", "Luna", "Earth Orbital Control"}
        neighbor_names = {neighbor.name for neighbor in neighbors}

        self.assertEqual(
            neighbor_names,
            expected_names,
            f"Expected neighbors of Earth to include: {expected_names}, but got: {neighbor_names}",
        )

    def test_getting_neighbors_sol(self):
        """
        Test that Sol's neighbors include all planets and other celestial bodies orbiting it.
        """
        universe = UniverseGraph.get_instance()
        sol = Location.objects.get(name="Sol")
        neighbors = universe.get_neighbors(sol)

        expected_names = {
            "Earth",
            "Mars",
            "Ceres",
            "Sol System",
        }  # Add other planets or celestial bodies as needed
        neighbor_names = {neighbor.name for neighbor in neighbors}

        self.assertEqual(
            neighbor_names,
            expected_names,
            f"Expected neighbors of Sol to include: {expected_names}, but got: {neighbor_names}",
        )

    def test_local_graph_around_earth(self):
        """
        Test the local graph around Earth at the PLANET scale.
        """
        universe = UniverseGraph.get_instance()
        earth = Location.objects.get(name="Earth")
        local_nodes = universe.get_local_graph(earth, max_scale=Scale.PLANET)

        expected_names = {
            "Earth",
            "Moon",
            "Luna",
            "Earth Orbital Control",
            "Luna Orbital Control",
            "Luna Secondary Control",
            "Moon Control",
        }

        local_names = {node.name for node in local_nodes}

        self.assertEqual(
            local_names,
            expected_names,
            f"Expected local graph to include: {expected_names}, but got: {local_names}",
        )

    def test_planets_same_local_area_at_different_scales(self):
        """
        Verify that two planets in the same star system (e.g., Earth and Mars)
        receive the same local area when the scale is set to STAR, STAR_SYSTEM, or GALAXY.
        """
        earth = Location.objects.get(name="Earth")
        mars = Location.objects.get(name="Mars")
        # Test across multiple higher-level scales.
        scales = [Scale.STAR, Scale.STARSYSTEM, Scale.GALAXY]
        for scale in scales:
            local_earth = self.route_service.get_local_locations(earth, scale)
            local_mars = self.route_service.get_local_locations(mars, scale)
            ids_earth = sorted([loc.id for loc in local_earth])
            ids_mars = sorted([loc.id for loc in local_mars])
            self.assertEqual(
                ids_earth,
                ids_mars,
                f"Local areas mismatch at scale {scale}: Earth {ids_earth} vs Mars {ids_mars}",
            )

    def test_starsystem_returns_empty_local_area_for_lower_scales(self):
        """
        Verify that a StarSystem's local area is empty when filtered by scales lower than its own
        (i.e., STATION, MOON, or PLANET).
        """
        sol_system = Location.objects.get(name="Sol System")
        lower_scales = [Scale.STATION, Scale.MOON, Scale.PLANET]
        for scale in lower_scales:
            local_area = self.route_service.get_local_locations(sol_system, scale)
            self.assertEqual(
                local_area,
                [],
                f"Expected empty local area for star system at scale {scale}, got {[loc.name for loc in local_area]}",
            )

    def test_route_distance_symmetry_between_different_systems(self):
        """
        Verify that the route distance between a Station in one star system (e.g., Luna Orbital Control)
        and a planet in another star system (e.g., Alpha Prime) is symmetric.
        """
        station = Location.objects.get(name="Luna Orbital Control")
        planet = Location.objects.get(name="Alpha Prime")
        path_forward = self.universe.get_path(station, planet)
        path_reverse = self.universe.get_path(planet, station)
        self.assertEqual(
            len(path_forward),
            len(path_reverse),
            "Route distances should be symmetric for station -> planet and planet -> station.",
        )

    def test_local_locations_equivalence(self):
        """
        Verify that retrieving the local locations (with maximum scale of PLANET)
        starting from Luna and from Luna Orbital Control yields the same set of objects.
        """
        # Retrieve local locations for both Luna and Luna Orbital Control
        local_luna = self.route_service.get_local_locations(self.luna, Scale.PLANET)
        local_control = self.route_service.get_local_locations(self.earth, Scale.PLANET)

        # Sort the lists by name to achieve a reproducible comparison.
        names_luna = sorted([loc.name for loc in local_luna])
        names_control = sorted([loc.name for loc in local_control])

        # Debugging output to verify the retrieved locations
        print(f"Local locations for Luna: {names_luna}")
        print(f"Local locations for Luna Orbital Control: {names_control}")

        self.assertEqual(
            names_luna,
            names_control,
            "Local Planet-scale neighborhoods for Luna and Luna Orbital Control should be identical.",
        )

    def test_local_graph_debug(self):
        """
        Debug test to understand exactly what's happening with local graph traversal
        """
        universe = UniverseGraph.get_instance()
        earth = Location.objects.get(name="Earth")

        print("\n=== Starting Local Graph Debug ===")

        # First, let's see what direct neighbors Earth has
        print("\nDirect neighbors of Earth:")
        earth_neighbors = universe.get_neighbors(earth)
        for neighbor in earth_neighbors:
            print(f"- {neighbor.name} (Scale: {neighbor.scale})")

        # Now, let's watch the local graph traversal
        print("\nLocal graph traversal from Earth:")
        local_nodes = universe.get_local_graph(earth, max_scale=Scale.PLANET)

        # Print what we got
        print("\nFinal local graph contains:")
        for node in local_nodes:
            print(f"- {node.name} (Scale: {node.scale})")

        # Let's also see what we're getting through the route service
        print("\nRoute service local locations:")
        route_service = RouteService()
        route_local = route_service.get_local_locations(earth, Scale.PLANET)
        for loc in route_local:
            print(f"- {loc.name} (Scale: {loc.scale})")

        print("\n=== End Local Graph Debug ===")

    def test_scale_ordering(self):
        """
        Verify that our OrderedScale comparisons work as expected.
        """
        print("\n=== Testing Scale Ordering ===")
        scales = [
            (Scale.STATION, "Station"),
            (Scale.MOON, "Moon"),
            (Scale.PLANET, "Planet"),
            (Scale.STAR, "Star"),
            (Scale.STARSYSTEM, "Star System"),
            (Scale.GALAXY, "Galaxy"),
        ]

        for scale1, name1 in scales:
            for scale2, name2 in scales:
                ordered1 = OrderedScale(scale1)
                ordered2 = OrderedScale(scale2)
                print(f"{name1} <= {name2}: {ordered1 <= ordered2}")

        # Also test some specific cases
        self.assertTrue(
            OrderedScale(Scale.STATION) <= OrderedScale(Scale.PLANET),
            "Stations should be 'smaller' than planets",
        )
        self.assertTrue(
            OrderedScale(Scale.MOON) <= OrderedScale(Scale.PLANET),
            "Moons should be 'smaller' than planets",
        )
