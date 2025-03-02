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
        self.assertEqual(len(path), 4, f"Unexpected number of steps: {len(path)}")

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
        path = self.universe.get_path(self.earth_orbital_control, self.deimos)
        self.assertEqual(len(path), 5, f"Unexpected number of steps: {len(path)}")

    def test_distance_earth_orbital_control_to_deimos_control(self):
        path = self.universe.get_path(self.earth_orbital_control, self.deimos_control)
        self.assertEqual(len(path), 6, f"Unexpected number of steps: {len(path)}")

    def test_distance_beta_major_to_luna(self):
        path = self.universe.get_path(self.beta_major, self.luna)
        self.assertEqual(len(path), 8, f"Unexpected number of steps: {len(path)}")


class TestManeuverPlanning(TestCase):
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
        self.ceres = Location.objects.get(name="Ceres")
        self.beta_minor_moon = Location.objects.get(name="Beta Minor Moon")
        self.beta_major = Location.objects.get(name="Beta Major")
        self.beta_major_moon = Location.objects.get(name="Beta Moon 1")
        self.phobos_station = Location.objects.get(name="Phobos Control")
        # -- Set up a Route Service -- 
        self.route_service = RouteService()
        # IMPORTANT: store the universe instance for later tests.
        self.universe = UniverseGraph.get_instance()
        
    def test_direct_ascent_earth_to_moon(self):
        origin = self.earth
        destination = self.moon
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = ["LAUNCH", "DIRECT_ASCENT", "DEORBIT", "LANDING"]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_direct_ascent_moon_to_earth(self):
        origin = self.moon
        destination = self.earth
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = ["LAUNCH", "DIRECT_ASCENT", "DEORBIT", "LANDING"]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_direct_ascent_earth_control_to_earth(self):
        origin = self.earth_control
        destination = self.earth
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = ["UNDOCK", "DIRECT_ASCENT", "DEORBIT", "LANDING"]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_sublight_transfer_between_moons(self):
        origin = self.moon
        destination = self.luna
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",      # Depart Moon
            "INSERTION",   # Enter Earth orbit
            "CIRCULARIZE", # Stabilize Earth orbit
            "SUBLIGHT",    # Transfer to Luna
            "CIRCULARIZE", # Establish Luna orbit
            "DEORBIT",     # Begin landing sequence
            "LANDING"      # Land on Luna
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_transfer_earth_to_phobos_station(self):
        origin = self.earth
        destination = self.phobos_station
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",        # Depart Earth
            "INSERTION",     # Enter Earth orbit
            "CIRCULARIZE",   # Stabilize Earth orbit
            "PLANE_CHANGE",  # Align for Mars transfer
            "SUBLIGHT",      # Transfer to Mars
            "CIRCULARIZE",   # Establish Mars orbit
            "SUBLIGHT",      # Transfer to Phobos
            "CIRCULARIZE",   # Establish Phobos orbit
            "PLANE_CHANGE",  # Align for station approach
            "DOCK"           # Dock at Phobos Control
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_hyperdrive_travel_between_planets(self):
        origin = self.earth
        destination = self.beta_major
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",        # Depart Earth
            "INSERTION",     # Enter Earth orbit
            "CIRCULARIZE",   # Stabilize Earth orbit
            "SUBLIGHT",      # Execute sublight burn to depart local orbit
            "HYPERSPACE",    # Perform hyperspace jump
            "SUBLIGHT",      # Execute sublight burn into destination orbit
            "CIRCULARIZE",   # Stabilize Beta Major orbit
            "DEORBIT",       # Begin landing sequence
            "LANDING"        # Land on Beta Major
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_hyperdrive_travel_between_planet_and_moon(self):
        origin = self.beta_major
        destination = self.ceres
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",        # Depart Beta Major
            "INSERTION",     # Enter Beta Major orbit
            "CIRCULARIZE",   # Stabilize Beta Major orbit
            "SUBLIGHT",      # Execute sublight burn to depart local orbit
            "HYPERSPACE",    # Perform hyperspace jump
            "SUBLIGHT",      # Execute sublight burn into destination orbit
            "CIRCULARIZE",   # Stabilize Ceres orbit
            "DEORBIT",       # Begin landing sequence
            "LANDING"        # Land on Ceres
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)
        
    def test_dwarf_planet_departure(self):
        origin = self.ceres
        destination = self.earth_control
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",        # Depart Ceres
            "INSERTION",     # Enter Ceres orbit
            "CIRCULARIZE",   # Stabilize Ceres orbit
            "PLANE_CHANGE",  # Align for Earth transfer
            "SUBLIGHT",      # Execute sublight burn to depart local orbit
            "CIRCULARIZE",   # Stabilize Earth orbit    
            "PLANE_CHANGE",  # Align for station approach
            "DOCK"           # Dock at Earth Orbital Control
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)
    
