import os
from django.conf import settings
from django.test import TestCase
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale, OrderedScale
from mysite.universe.services.route_server import RouteService
from mysite.universe.models.navigation import UniverseGraph, print_tree

class RoutePlanningXMLTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Import the entire test universe from test_universe.xml.
        This creates our objects for our tests.
        """
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        importer = UniverseImporter(xml_file)
        importer.import_universe()
        
        universe = UniverseGraph.get_instance()
        galaxy_location = Location.objects.get(name="Galactus")
        print_tree(universe, root_id=galaxy_location.id)
        
    def setUp(self):
        """
        Retrieve requisite objects from the imported universe.
        """
        # In our test_universe.xml:
        # - "Luna" is a moon on Earth.
        # - "Luna Orbital Control" is a station associated with Luna.
        # - "Beta Minor Moon" is a moon in the Binary System.
        # - "Earth" is a planet.
        self.luna = Location.objects.get(name="Luna")
        self.luna_orbital_control = Location.objects.get(name="Luna Orbital Control")
        self.beta_minor_moon = Location.objects.get(name="Beta Minor Moon")
        self.earth = Location.objects.get(name="Earth")
        self.route_service = RouteService()
        # IMPORTANT: store the universe instance for later tests.
        self.universe = UniverseGraph.get_instance()
        print("Graph edges:", self.universe._graph.edges())
        print("Luna neighbors:", [n for n in self.universe.get_neighbors(self.luna)])
        print("Luna Orbital Control neighbors:", [n for n in self.universe.get_neighbors(self.luna_orbital_control)])

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
            "Local Planet-scale neighborhoods for Luna and Luna Orbital Control should be identical."
        )

    def test_generate_expected_events_001(self):
        """
        Verify that generating events for an intermediate segment from Beta Minor Moon (MOON)
        to Luna Orbital Control (STATION) produces the expected maneuvers:
            - Departure from a moon (LAUNCH, INSERTION, CIRCULARIZE),
            - Transit (short TRANSFER), then intermediate arrival (DOCK).
        Expected maneuvers (in order):
            ["LAUNCH", "INSERTION", "CIRCULARIZE", "TRANSFER", "DOCK"]
        """
        events = self.route_service.generate_segment_events(
            start=self.beta_minor_moon,
            end=self.luna_orbital_control,
            final=False,
        )
        expected_maneuvers = ["LAUNCH", "INSERTION", "CIRCULARIZE", "TRANSFER", "DOCK"]
        self.assertEqual(
            len(events),
            5,
            "Expected 5 navigation events for intermediate segment from Beta Minor Moon to Luna Orbital Control."
        )
        actual_maneuvers = [event.maneuver for event in events]
        self.assertEqual(
            actual_maneuvers,
            expected_maneuvers,
            "The maneuver sequence for Beta Minor Moon to Luna Orbital Control does not match expectations."
        )

    def test_generate_events_002(self):
        """
        Verify that generating events for a final segment from Beta Minor Moon (MOON)
        to Earth (PLANET) produces the expected maneuvers:
            - Departure from a moon (LAUNCH, INSERTION, CIRCULARIZE),
            - Transit (TRANSFER), then final arrival (DEORBIT, LANDING).
        Expected maneuvers (in order):
            ["LAUNCH", "INSERTION", "CIRCULARIZE", "TRANSFER", "DEORBIT", "LANDING"]
        """
        events = self.route_service.generate_segment_events(
            start=self.beta_minor_moon,
            end=self.earth,
            final=True,
        )
        expected_maneuvers = [
            "LAUNCH",
            "INSERTION",
            "CIRCULARIZE",
            "TRANSFER",
            "DEORBIT",
            "LANDING",
        ]
        self.assertEqual(
            len(events),
            6,
            "Expected 6 navigation events for final segment from Beta Minor Moon to Earth."
        )
        actual_maneuvers = [event.maneuver for event in events]
        self.assertEqual(
            actual_maneuvers,
            expected_maneuvers,
            "The maneuver sequence for Beta Minor Moon to Earth does not match expectations."
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
                f"Expected empty local area for star system at scale {scale}, got {[loc.name for loc in local_area]}"
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
            "Route distances should be symmetric for station -> planet and planet -> station."
        )       
