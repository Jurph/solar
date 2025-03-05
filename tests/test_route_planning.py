import os
from django.conf import settings
from django.test import TestCase
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale 
from mysite.universe.services.route_server import RouteService
from mysite.universe.models.navigation import UniverseGraph, print_tree, ManeuverType

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
    
class TestControllerAssignment(TestCase):
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
        self.earth = Location.objects.get(name="Earth")
        self.moon = Location.objects.get(name="Moon")
        self.earth_control = Location.objects.get(name="Earth Orbital Control")
        self.moon_control = Location.objects.get(name="Moon Control")
        self.alpha_prime = Location.objects.get(name="Alpha Prime")
        self.beta_major = Location.objects.get(name="Beta Major")
        self.ceres = Location.objects.get(name="Ceres")
        self.universe.rebuild_graph()

    def test_earth_control_is_controller_for_earth(self):
        """Test that Earth Orbital Control is the controller for Earth"""
        controller = self.route_service.effective_controller(self.earth)
        self.assertEqual(controller.name, "Earth Orbital Control")
        
    def test_moon_control_is_controller_for_moon(self):
        """Test that Moon Control is the controller for Moon"""
        controller = self.route_service.effective_controller(self.moon)
        self.assertEqual(controller.name, "Moon Control")
        
    def test_effective_controller_for_ceres(self):
        """Test that effective_controller returns Ceres Control for Ceres"""
        controller = self.route_service.effective_controller(self.ceres)
        self.assertEqual(controller.name, "Ceres Control")
        
    def test_effective_controller_fallback_to_self(self):
        """Test that effective_controller falls back to the location itself when no controller exists"""
        # Create a temporary location with no nearby control station
        isolated_location = Location.objects.create(name="Isolated Planet", scale=Scale.PLANET)
        try:
            controller = self.route_service.effective_controller(isolated_location)
            self.assertEqual(controller.name, "Isolated Planet")
        finally:
            isolated_location.delete()
    
    def test_effective_controller_debug(self):
        """Diagnostic test to debug effective_controller issues"""
        from mysite.universe.models.navigation import UniverseGraph
        
        # Setup debugging
        universe = UniverseGraph.get_instance()
        earth = self.earth
        earth_control = self.earth_control
        
        # Check the graph structure
        print("\n### Debugging Effective Controller ###")
        
        # 1. Check if Earth and Earth Orbital Control both exist in the graph
        print(f"Earth ID: {earth.id}, Earth Control ID: {earth_control.id}")
        earth_in_graph = earth.id in universe._graph
        control_in_graph = earth_control.id in universe._graph
        print(f"Earth in graph: {earth_in_graph}, Earth Control in graph: {control_in_graph}")
        
        # 2. Check direct neighbors
        earth_neighbors = universe.get_neighbors(earth)
        print(f"Direct neighbors of Earth ({len(earth_neighbors)}):")
        for n in earth_neighbors:
            print(f"  - {n.name} (Scale: {n.scale}, Type: {n.get_concrete_instance().get_type_name()})")
            
        # 3. Check local graph
        local_nodes = self.route_service.get_local_locations(earth, Scale.PLANET)
        print(f"\nLocal nodes around Earth ({len(local_nodes)}):")
        for n in local_nodes:
            print(f"  - {n.name} (Scale: {n.scale}, Type: {n.get_concrete_instance().get_type_name()})")
            
        # 4. Test our filtering logic
        control_stations = [n for n in local_nodes if 
                        n.get_concrete_instance().get_type_name().lower() == "station" and
                        ("control" in n.name.lower() or "dispatch" in n.name.lower())]
        print(f"\nFiltered control stations ({len(control_stations)}):")
        for n in control_stations:
            print(f"  - {n.name}")
            
        # Now run the actual controller function and check the result
        controller = self.route_service.effective_controller(earth)
        print(f"\nEffective controller for Earth: {controller.name} (Type: {controller.get_concrete_instance().get_type_name()})")
        
        # The test itself - will fail, but we need the diagnostic output
        self.assertEqual(controller.name, "Earth Orbital Control", "Controller should be Earth Orbital Control")
                
    def test_controller_assignment_direct_ascent(self):
        """Test that controllers are correctly assigned for direct ascent"""
        origin = self.earth
        destination = self.moon
        events = self.route_service.plan_route(origin, destination)
        print(events)
        
        self.assertEqual(events[0].controller.name, "Earth Orbital Control")
        self.assertEqual(events[1].controller.name, "Moon Control")

    def test_controller_assignment_hyperspace_journey(self):
        """Test that controllers are correctly assigned for hyperspace journey"""
        origin = self.earth
        destination = self.alpha_prime
        events = self.route_service.plan_route(origin, destination)
        
        # Define the critical control points we care about
        expected_control_points = {
            "departure": {
                "maneuver_types": [ManeuverType.LAUNCH, ManeuverType.INSERTION, ManeuverType.SUBLIGHT],
                "controllers": ["Earth", "Earth Orbital Control"]
            },
            "hyperspace": {
                "maneuver_types": [ManeuverType.HYPERSPACE],
                "controllers": ["Earth Orbital Control"]  # Departure controller handles hyperspace
            },
            "arrival": {
                "maneuver_types": [ManeuverType.SUBLIGHT, ManeuverType.CIRCULARIZE, ManeuverType.DEORBIT, ManeuverType.LANDING],
                "controllers": ["Alpha Prime Orbital Control", "Alpha Prime"]
            }
        }
        
        self.validate_critical_control_points(events, expected_control_points)
    
    def test_controller_assignment_planet_to_moon(self):
        """Test that controllers are correctly assigned for planet to moon journey"""
        origin = self.beta_major
        destination = self.ceres
        events = self.route_service.plan_route(origin, destination)
        
        # Define the critical control points we care about
        expected_control_points = {
            "departure": {
                "maneuver_types": [ManeuverType.LAUNCH, ManeuverType.INSERTION],
                "controllers": ["Beta Major", "Beta Major Orbital Control"]
            },
            "arrival": {
                "maneuver_types": [ManeuverType.SUBLIGHT, ManeuverType.CIRCULARIZE, ManeuverType.DEORBIT, ManeuverType.LANDING],
                "controllers": ["Ceres Control", "Ceres"]
            }
        }
        
        self.validate_critical_control_points(events, expected_control_points)
    
    def test_controller_assignment_docking(self):
        """Test that controllers are correctly assigned for docking operations"""
        origin = self.ceres
        destination = self.earth_control
        events = self.route_service.plan_route(origin, destination)
        
        # Define the critical control points we care about
        expected_control_points = {
            "departure": {
                "maneuver_types": [ManeuverType.LAUNCH, ManeuverType.INSERTION],
                "controllers": ["Ceres", "Ceres Control"]
            },
            "arrival": {
                "maneuver_types": [ManeuverType.PLANE_CHANGE, ManeuverType.DOCK],
                "controllers": ["Earth Orbital Control"]
            }
        }
        
        self.validate_critical_control_points(events, expected_control_points)
        
    def validate_critical_control_points(self, events, expected_control_points):
        """
        Helper method to validate only the critical control points in a journey,
        rather than every single step.
        
        Args:
            events: List of NavigationEvent objects from plan_route
            expected_control_points: Dictionary defining the expected controllers
                for different phases of the journey
        """
        # Print events for debugging
        print("\nActual journey events:")
        for i, event in enumerate(events):
            print(f"{i}: {event.maneuver.name} -> {event.target.name} (Controller: {event.controller.name})")
            
        # Check each critical control point
        for phase, expectations in expected_control_points.items():
            maneuver_types = expectations["maneuver_types"]
            allowed_controllers = expectations["controllers"]
            
            print(f"\nChecking {phase} control point:")
            
            # Find all events matching the maneuver types for this phase
            matching_events = [event for event in events if event.maneuver in maneuver_types]
            
            # Ensure we have at least one matching event
            self.assertTrue(
                len(matching_events) > 0,
                f"No events found matching {[m.name for m in maneuver_types]} for {phase} phase"
            )
            
            # Check that controllers for these events are in the allowed list
            for event in matching_events:
                print(f"  {event.maneuver.name} -> Controller: {event.controller.name}")
                self.assertIn(
                    event.controller.name,
                    allowed_controllers,
                    f"Controller '{event.controller.name}' for {event.maneuver.name} in {phase} phase not in allowed list: {allowed_controllers}"
                )
