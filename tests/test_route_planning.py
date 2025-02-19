import os
from django.conf import settings
from django.test import TestCase
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale, OrderedScale
from mysite.universe.services.route_server import RouteService

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
        # Note: The importer is assumed to set up neighbor relationships as needed.

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

    def test_local_locations_equivalence(self):
        """
        Verify that retrieving the local locations (with maximum scale of PLANET)
        starting from Luna and from Luna Orbital Control yields the same set of objects.
        """
        local_luna = self.route_service.get_local_locations(self.luna, Scale.PLANET)
        local_control = self.route_service.get_local_locations(self.luna_orbital_control, Scale.PLANET)

        # Sort the lists by name to achieve a reproducible comparison.
        names_luna = sorted([loc.name for loc in local_luna])
        names_control = sorted([loc.name for loc in local_control])
        self.assertEqual(
            names_luna,
            names_control,
            "Local Planet-scale neighborhoods for Luna and Luna Orbital Control should be identical."
        )

    def test_generate_events_beta_minor_moon_to_luna_orbital_control(self):
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

    def test_generate_events_beta_minor_moon_to_earth_final(self):
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