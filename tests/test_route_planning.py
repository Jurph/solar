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
        """Test DIRECT_ASCENT maneuver between Earth and Luna"""
        events = self.route_service.plan_route(self.earth, self.luna)
        
        # For a direct neighbor route between planet and moon, we expect:
        # 1. DIRECT_ASCENT from Earth to Luna
        # 2. CIRCULARIZE at Luna
        # 3. DEORBIT at Luna
        # 4. LANDING at Luna
        
        self.assertEqual(len(events), 4, "Expected exactly 4 events for direct ascent")
        
        # Check the sequence of maneuvers
        expected_maneuvers = [
            ManeuverType.DIRECT_ASCENT,
            ManeuverType.CIRCULARIZE,
            ManeuverType.DEORBIT,
            ManeuverType.LANDING
        ]
        
        actual_maneuvers = [event.maneuver for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers, "Maneuvers are not in the expected order")

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
        self.mars = Location.objects.get(name="Mars")
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
        print(f"\nEffective controller for Earth: {controller.name}")
        
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

    def test_effective_controller_assignment(self):
        """Test that for various journeys, the departure event uses the origin's effective controller
        and the arrival event uses the destination's effective controller."""
        journeys = [
            (self.earth, self.alpha_prime),
            (self.beta_major, self.ceres),
            (self.earth_control, self.earth),
        ]

        for origin, destination in journeys:
            events = self.route_service.plan_route(origin, destination)
            self.assertTrue(events, f"No events for journey from {origin.name} to {destination.name}")

            departure_controller = self.route_service.effective_controller(origin).name
            arrival_controller = self.route_service.effective_controller(destination).name

            # Check that the first event's controller is the origin's effective controller
            self.assertEqual(
                events[0].controller.name, departure_controller,
                f"Departure controller for journey from {origin.name} to {destination.name} should be {departure_controller}"
            )

            # Check that the last event's controller is the destination's effective controller
            self.assertEqual(
                events[-1].controller.name, arrival_controller,
                f"Arrival controller for journey from {origin.name} to {destination.name} should be {arrival_controller}"
            )
    
    def test_script_service_controller_extraction_from_controller_actor(self):
        """
        Test that ScriptService._get_controller() returns the Controller actor 
        if nav_event.controller is a Controller.
        """
        from mysite.universe.services.script_server import ScriptService
        from mysite.universe.services.llm_service import LLMService
        from mysite.universe.models.navigation import NavigationEvent, ManeuverType
        from mysite.universe.models.actor import Controller
        
        llm = LLMService(quiet_mode=True)
        script_service = ScriptService(llm)
        
        # Get or create Earth controller
        earth_controller = Controller.objects.filter(name="Earth Orbital Control").first()
        if not earth_controller:
            earth_controller = Controller.create(name="Earth Orbital Control", location=self.earth_control)
        
        nav_event = NavigationEvent(
            maneuver=ManeuverType.DEORBIT,
            origin=self.mars,
            current=self.earth,
            next=self.earth,
            destination=self.earth,
            controller=earth_controller  # Controller actor
        )
        
        result = script_service._get_controller(nav_event)
        self.assertEqual(result, earth_controller)
        self.assertEqual(result.name, "Earth Orbital Control")
    
    def test_script_service_controller_extraction_from_location(self):
        """
        Test that ScriptService._get_controller() extracts controller name from Location 
        if nav_event.controller is a Location (station).
        """
        from mysite.universe.services.script_server import ScriptService
        from mysite.universe.services.llm_service import LLMService
        from mysite.universe.models.navigation import NavigationEvent, ManeuverType
        
        llm = LLMService(quiet_mode=True)
        script_service = ScriptService(llm)
        
        nav_event = NavigationEvent(
            maneuver=ManeuverType.DEORBIT,
            origin=self.mars,
            current=self.earth,
            next=self.earth,
            destination=self.earth,
            controller=self.earth_control  # Location (station)
        )
        
        result = script_service._get_controller(nav_event)
        self.assertEqual(result.name, "Earth Orbital Control")
        # Should find existing controller or create one
        from mysite.universe.models.actor import Controller
        self.assertIsInstance(result, Controller)
    
    def test_script_service_controller_fallback_for_arrival_maneuver(self):
        """
        Test that ScriptService._get_controller() correctly determines controller for arrival maneuvers
        when nav_event.controller is None.
        
        This is the critical test case: When RouteService assigns controller=None (bug scenario),
        ScriptService should determine controller based on maneuver type, not just destination.
        
        For DEORBIT (arrival maneuver), controller should be based on destination, not origin.
        """
        from mysite.universe.services.script_server import ScriptService
        from mysite.universe.services.llm_service import LLMService
        from mysite.universe.models.navigation import NavigationEvent, ManeuverType
        
        llm = LLMService(quiet_mode=True)
        script_service = ScriptService(llm)
        
        nav_event = NavigationEvent(
            maneuver=ManeuverType.DEORBIT,  # Arrival maneuver
            origin=self.mars,
            current=self.earth,
            next=self.earth,
            destination=self.earth,
            controller=None  # Simulating bug where RouteService didn't set controller
        )
        
        result = script_service._get_controller(nav_event)
        
        # Should get Earth Orbital Control (destination controller), NOT Mars Control (origin controller)
        self.assertEqual(result.name, "Earth Orbital Control")
        self.assertNotEqual(result.name, "Mars Control")
    
    def test_script_service_controller_fallback_for_departure_maneuver(self):
        """
        Test that ScriptService._get_controller() correctly determines controller for departure maneuvers
        when nav_event.controller is None.
        
        For LAUNCH (departure maneuver), controller should be based on origin, not destination.
        """
        from mysite.universe.services.script_server import ScriptService
        from mysite.universe.services.llm_service import LLMService
        from mysite.universe.models.navigation import NavigationEvent, ManeuverType
        
        llm = LLMService(quiet_mode=True)
        script_service = ScriptService(llm)
        
        # Get or create Mars controller
        from mysite.universe.models.actor import Controller
        mars_controller = Controller.objects.filter(name="Mars Control").first()
        if not mars_controller:
            # Find or create Mars control station
            mars_control_station = Location.objects.filter(name__icontains="Mars").filter(name__icontains="Control").first()
            if not mars_control_station:
                mars_control_station = Location.objects.create(name="Mars Control", scale=Scale.STATION)
            mars_controller = Controller.create(name="Mars Control", location=mars_control_station)
        
        nav_event = NavigationEvent(
            maneuver=ManeuverType.LAUNCH,  # Departure maneuver
            origin=self.mars,
            current=self.mars,
            next=self.earth,
            destination=self.earth,
            controller=None  # Simulating bug where RouteService didn't set controller
        )
        
        result = script_service._get_controller(nav_event)
        
        # Should get Mars Control (origin controller), NOT Earth Orbital Control (destination controller)
        self.assertEqual(result.name, "Mars Control")
        self.assertNotEqual(result.name, "Earth Orbital Control")
    
    def test_script_service_controller_fallback_for_transfer_maneuver(self):
        """
        Test that ScriptService._get_controller() correctly determines controller for transfer maneuvers
        when nav_event.controller is None.
        
        For SUBLIGHT (transfer maneuver), controller should be based on current location, not destination.
        """
        from mysite.universe.services.script_server import ScriptService
        from mysite.universe.services.llm_service import LLMService
        from mysite.universe.models.navigation import NavigationEvent, ManeuverType
        
        llm = LLMService(quiet_mode=True)
        script_service = ScriptService(llm)
        
        # Get or create Mars controller
        from mysite.universe.models.actor import Controller
        mars_controller = Controller.objects.filter(name="Mars Control").first()
        if not mars_controller:
            # Find or create Mars control station
            mars_control_station = Location.objects.filter(name__icontains="Mars").filter(name__icontains="Control").first()
            if not mars_control_station:
                mars_control_station = Location.objects.create(name="Mars Control", scale=Scale.STATION)
            mars_controller = Controller.create(name="Mars Control", location=mars_control_station)
        
        nav_event = NavigationEvent(
            maneuver=ManeuverType.SUBLIGHT,  # Transfer maneuver
            origin=self.mars,
            current=self.mars,  # Currently at Mars
            next=self.earth,
            destination=self.earth,
            controller=None  # Simulating bug where RouteService didn't set controller
        )
        
        result = script_service._get_controller(nav_event)
        
        # Should get Mars Control (current location controller), NOT Earth Orbital Control (destination controller)
        self.assertEqual(result.name, "Mars Control")
        self.assertNotEqual(result.name, "Earth Orbital Control")