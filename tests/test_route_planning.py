import os
from django.conf import settings
from django.test import TestCase
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale 
from mysite.universe.services.route_server import RouteService
from mysite.universe.models.navigation import UniverseGraph, print_tree

class TestRoutePlanning(TestCase):
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
        self.route_service = RouteService()
        self.universe = UniverseGraph.get_instance()
        # Mock locations for testing
        self.luna = Location.objects.get(name="Luna")
        self.moon = Location.objects.get(name="Moon")
        self.phobos_control = Location.objects.get(name="Phobos Control")
        self.earth_orbital_control = Location.objects.get(name="Earth Orbital Control")
        self.ceres = Location.objects.get(name="Ceres")
        self.deimos = Location.objects.get(name="Deimos")
        self.deimos_control = Location.objects.get(name="Deimos Control")
        self.alpha_moon_1 = Location.objects.get(name="Alpha Moon 1")
        self.beta_moon_2 = Location.objects.get(name="Beta Moon 2")
        self.earth = Location.objects.get(name="Earth")
        self.mars = Location.objects.get(name="Mars")
        self.beta_major = Location.objects.get(name="Beta Major")
        
    def test_distance_luna_to_moon(self):
        path = self.universe.get_path(self.luna, self.moon)
        self.assertEqual(len(path), 3, f"Unexpected number of steps: {len(path)}")
        
    def test_distance_phobos_control_to_deimos_control(self):
        path = self.universe.get_path(self.phobos_control, self.deimos_control)
        self.assertEqual(len(path), 5, f"Unexpected number of steps: {len(path)}")

    def test_distance_earth_orbital_control_to_ceres(self):
        path = self.universe.get_path(self.earth_orbital_control, self.ceres)
        self.assertEqual(len(path), 8, f"Unexpected number of steps: {len(path)}")

    def test_distance_alpha_moon_1_to_beta_moon_2(self):
        path = self.universe.get_path(self.alpha_moon_1, self.beta_moon_2)
        self.assertEqual(len(path), 7, f"Unexpected number of steps: {len(path)}")

    def test_distance_earth_to_mars(self):
        path = self.universe.get_path(self.earth, self.mars)
        self.assertEqual(len(path), 3, f"Unexpected number of steps: {len(path)}")
        
    def test_distance_earth_orbital_control_to_mars(self):
        path = self.universe.get_path(self.earth_orbital_control, self.mars)
        self.assertEqual(len(path), 4, f"Unexpected number of steps: {len(path)}")

    def test_distance_earth_orbital_control_to_deimos(self):
        path = self.universe.get_path(self.earth_orbital_control, self.deimos_control)
        self.assertEqual(len(path), 5, f"Unexpected number of steps: {len(path)}")

    def test_distance_earth_orbital_control_to_deimos_control(self):
        path = self.universe.get_path(self.earth_orbital_control, self.deimos_control)
        self.assertEqual(len(path), 6, f"Unexpected number of steps: {len(path)}")

    def test_distance_beta_major_to_luna(self):
        path = self.universe.get_path(self.beta_major, self.luna)
        self.assertEqual(len(path), 8, f"Unexpected number of steps: {len(path)}")


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
        # -- Get some objects we can use as examples -- 
        self.earth = Location.objects.get(name="Earth")
        self.earth_control = Location.objects.get(name="Earth Orbital Control")
        self.moon = Location.objects.get(name="Moon")
        self.luna = Location.objects.get(name="Luna")
        self.luna_orbital_control = Location.objects.get(name="Luna Orbital Control")
        self.mars = Location.objects.get(name="Mars")
        self.sol = Location.objects.get(name="Sol")
        self.beta_minor_moon = Location.objects.get(name="Beta Minor Moon")
        self.phobos_station = Location.objects.get(name="Phobos Control")
        # -- Set up a Route Service -- 
        self.route_service = RouteService()
        # IMPORTANT: store the universe instance for later tests.
        self.universe = UniverseGraph.get_instance()

    def test_direct_ascent_earth_to_moon(self):
        origin = self.earth
        destination = self.moon
        path = self.universe.get_path(origin, destination)
        events = self.route_service.generate_segment_events(origin, destination, path, final=True)
        expected_maneuvers = ["DIRECT_ASCENT", "SUBLIGHT", "DEORBIT", "LANDING"]
        actual_maneuvers = [event.maneuver for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_direct_ascent_earth_control_to_earth(self):
        origin = self.earth_control
        destination = self.earth
        path = self.universe.get_path(origin, destination)
        events = self.route_service.generate_segment_events(origin, destination, path, final=True)
        expected_maneuvers = ["UNDOCK", "DIRECT_ASCENT", "DEORBIT", "LANDING"]
        actual_maneuvers = [event.maneuver for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_sublight_transfer_between_moons(self):
        origin = self.moon
        destination = self.luna
        path = self.universe.get_path(origin, destination)
        events = self.route_service.generate_segment_events(origin, destination, path, final=True)
        expected_maneuvers = ["LAUNCH", "INSERTION", "CIRCULARIZE", "SUBLIGHT", "DEORBIT", "LANDING"]
        actual_maneuvers = [event.maneuver for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_transfer_earth_to_phobos_station(self):
        origin = self.earth
        destination = self.phobos_station
        path = self.universe.get_path(origin, destination)
        events = self.route_service.generate_segment_events(origin, destination, path, final=True)
        expected_maneuvers = ["LAUNCH", "INSERTION", "CIRCULARIZE", "SUBLIGHT", "DOCK"]
        actual_maneuvers = [event.maneuver for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_generate_expected_events_001(self):
        """
        Verify that generating events for an intermediate segment from Beta Minor Moon (MOON)
        to Luna Orbital Control (STATION) produces the expected maneuvers:
            - Departure from a moon (LAUNCH, INSERTION, CIRCULARIZE),
            - Transfers to Beta Minor (SUBLIGHT, CIRCULARIZE)
            - Transfer to solar orbit and jump to earth (PLANE CHANGE, SUBLIGHT, HYPERDRIVE)
            - Capture into Earth's orbit (INSERTION, CIRCULARIZE)
            - Transfer to Lunar orbit (PLANE CHANGE, SUBLIGHT)
            - Arrival (DOCK).
        Expected maneuvers (in order):
            ["LAUNCH", "INSERTION", "CIRCULARIZE", "SUBLIGHT", "CIRCULARIZE", "PLANE CHANGE", "SUBLIGHT", "HYPERDRIVE", 
            "INSERTION", "CIRCULARIZE", "PLANE CHANGE", "SUBLIGHT", "DOCK"]
        """
        src = self.beta_minor_moon
        dst = self.luna_orbital_control
        path = self.universe.get_path(origin=src, destination=dst)
        events = self.route_service.generate_segment_events(
            start=src,
            end=dst,
            path=path,
            final=False,
        )
        expected_maneuvers = ["LAUNCH", "INSERTION", "CIRCULARIZE", "SUBLIGHT", "CIRCULARIZE", "PLANE CHANGE", "SUBLIGHT", "HYPERDRIVE", 
            "INSERTION", "CIRCULARIZE", "PLANE CHANGE", "SUBLIGHT", "DOCK"]
        self.assertEqual(
            len(events),
            13,
            f"Expected 13 navigation events for intermediate segment from Beta Minor Moon to Luna Orbital Control; instead got {events}"
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
        to Earth (PLANET) produces the expected maneuvers
        """
        src = self.beta_minor_moon
        dst = self.earth
        path = self.universe.get_path(origin=src, destination=dst)
        events = self.route_service.generate_segment_events(
            start=self.beta_minor_moon,
            end=self.earth,
            path=path,
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
