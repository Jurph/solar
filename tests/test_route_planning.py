import os
from django.conf import settings
from django.test import TestCase
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale 
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
