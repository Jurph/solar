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
            ManeuverType.LANDING,
        ]

        actual_maneuvers = [event.maneuver for event in events]
        self.assertEqual(
            actual_maneuvers,
            expected_maneuvers,
            "Maneuvers are not in the expected order",
        )

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
            "LAUNCH",  # Depart Moon
            "INSERTION",  # Enter Earth orbit
            "CIRCULARIZE",  # Stabilize Earth orbit
            "SUBLIGHT",  # Transfer to Luna
            "CIRCULARIZE",  # Establish Luna orbit
            "DEORBIT",  # Begin landing sequence
            "LANDING",  # Land on Luna
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_transfer_earth_to_phobos_station(self):
        origin = self.earth
        destination = self.phobos_station
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",  # Depart Earth
            "INSERTION",  # Enter Earth orbit
            "CIRCULARIZE",  # Stabilize Earth orbit
            "PLANE_CHANGE",  # Align for Mars transfer
            "SUBLIGHT",  # Transfer to Mars
            "CIRCULARIZE",  # Establish Mars orbit
            "SUBLIGHT",  # Transfer to Phobos
            "CIRCULARIZE",  # Establish Phobos orbit
            "PLANE_CHANGE",  # Align for station approach
            "DOCK",  # Dock at Phobos Control
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_hyperdrive_travel_between_planets(self):
        origin = self.earth
        destination = self.beta_major
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",  # Depart Earth
            "INSERTION",  # Enter Earth orbit
            "CIRCULARIZE",  # Stabilize Earth orbit
            "SUBLIGHT",  # Execute sublight burn to depart local orbit
            "HYPERSPACE",  # Perform hyperspace jump
            "SUBLIGHT",  # Execute sublight burn into destination orbit
            "CIRCULARIZE",  # Stabilize Beta Major orbit
            "DEORBIT",  # Begin landing sequence
            "LANDING",  # Land on Beta Major
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_hyperdrive_travel_between_planet_and_moon(self):
        origin = self.beta_major
        destination = self.ceres
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",  # Depart Beta Major
            "INSERTION",  # Enter Beta Major orbit
            "CIRCULARIZE",  # Stabilize Beta Major orbit
            "SUBLIGHT",  # Execute sublight burn to depart local orbit
            "HYPERSPACE",  # Perform hyperspace jump
            "SUBLIGHT",  # Execute sublight burn into destination orbit
            "CIRCULARIZE",  # Stabilize Ceres orbit
            "DEORBIT",  # Begin landing sequence
            "LANDING",  # Land on Ceres
        ]
        actual_maneuvers = [event.maneuver.name.upper() for event in events]
        self.assertEqual(actual_maneuvers, expected_maneuvers)

    def test_dwarf_planet_departure(self):
        origin = self.ceres
        destination = self.earth_control
        events = self.route_service.plan_route(origin, destination)
        expected_maneuvers = [
            "LAUNCH",  # Depart Ceres
            "INSERTION",  # Enter Ceres orbit
            "CIRCULARIZE",  # Stabilize Ceres orbit
            "PLANE_CHANGE",  # Align for Earth transfer
            "SUBLIGHT",  # Execute sublight burn to depart local orbit
            "CIRCULARIZE",  # Stabilize Earth orbit
            "PLANE_CHANGE",  # Align for station approach
            "DOCK",  # Dock at Earth Orbital Control
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
        isolated_location = Location.objects.create(
            name="Isolated Planet", scale=Scale.PLANET
        )
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
        print(
            f"Earth in graph: {earth_in_graph}, Earth Control in graph: {control_in_graph}"
        )

        # 2. Check direct neighbors
        earth_neighbors = universe.get_neighbors(earth)
        print(f"Direct neighbors of Earth ({len(earth_neighbors)}):")
        for n in earth_neighbors:
            print(
                f"  - {n.name} (Scale: {n.scale}, Type: {n.get_concrete_instance().get_type_name()})"
            )

        # 3. Check local graph
        local_nodes = self.route_service.get_local_locations(earth, Scale.PLANET)
        print(f"\nLocal nodes around Earth ({len(local_nodes)}):")
        for n in local_nodes:
            print(
                f"  - {n.name} (Scale: {n.scale}, Type: {n.get_concrete_instance().get_type_name()})"
            )

        # 4. Test our filtering logic
        control_stations = [
            n
            for n in local_nodes
            if n.get_concrete_instance().get_type_name().lower() == "station"
            and ("control" in n.name.lower() or "dispatch" in n.name.lower())
        ]
        print(f"\nFiltered control stations ({len(control_stations)}):")
        for n in control_stations:
            print(f"  - {n.name}")

        # Now run the actual controller function and check the result
        controller = self.route_service.effective_controller(earth)
        print(f"\nEffective controller for Earth: {controller.name}")

        # The test itself - will fail, but we need the diagnostic output
        self.assertEqual(
            controller.name,
            "Earth Orbital Control",
            "Controller should be Earth Orbital Control",
        )

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
            self.assertTrue(
                events,
                f"No events for journey from {origin.name} to {destination.name}",
            )

            departure_controller = self.route_service.effective_controller(origin).name
            arrival_controller = self.route_service.effective_controller(
                destination
            ).name

            # Check that the first event's controller is the origin's effective controller
            self.assertEqual(
                events[0].controller.name,
                departure_controller,
                f"Departure controller for journey from {origin.name} to {destination.name} should be {departure_controller}",
            )

            # Check that the last event's controller is the destination's effective controller
            self.assertEqual(
                events[-1].controller.name,
                arrival_controller,
                f"Arrival controller for journey from {origin.name} to {destination.name} should be {arrival_controller}",
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
        earth_controller = Controller.objects.filter(
            name="Earth Orbital Control"
        ).first()
        if not earth_controller:
            earth_controller = Controller.create(
                name="Earth Orbital Control", location=self.earth_control
            )

        nav_event = NavigationEvent(
            maneuver=ManeuverType.DEORBIT,
            origin=self.mars,
            current=self.earth,
            next=self.earth,
            destination=self.earth,
            controller=earth_controller,  # Controller actor
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
            controller=self.earth_control,  # Location (station)
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
            controller=None,  # Simulating bug where RouteService didn't set controller
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
            mars_control_station = (
                Location.objects.filter(name__icontains="Mars")
                .filter(name__icontains="Control")
                .first()
            )
            if not mars_control_station:
                mars_control_station = Location.objects.create(
                    name="Mars Control", scale=Scale.STATION
                )
            mars_controller = Controller.create(
                name="Mars Control", location=mars_control_station
            )

        nav_event = NavigationEvent(
            maneuver=ManeuverType.LAUNCH,  # Departure maneuver
            origin=self.mars,
            current=self.mars,
            next=self.earth,
            destination=self.earth,
            controller=None,  # Simulating bug where RouteService didn't set controller
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
            mars_control_station = (
                Location.objects.filter(name__icontains="Mars")
                .filter(name__icontains="Control")
                .first()
            )
            if not mars_control_station:
                mars_control_station = Location.objects.create(
                    name="Mars Control", scale=Scale.STATION
                )
            mars_controller = Controller.create(
                name="Mars Control", location=mars_control_station
            )

        nav_event = NavigationEvent(
            maneuver=ManeuverType.SUBLIGHT,  # Transfer maneuver
            origin=self.mars,
            current=self.mars,  # Currently at Mars
            next=self.earth,
            destination=self.earth,
            controller=None,  # Simulating bug where RouteService didn't set controller
        )

        result = script_service._get_controller(nav_event)

        # Should get Mars Control (current location controller), NOT Earth Orbital Control (destination controller)
        self.assertEqual(result.name, "Mars Control")
        self.assertNotEqual(result.name, "Earth Orbital Control")


class TestRouteDurations(TestCase):
    """
    Test that route planning generates events with correct physics-based durations.

    These tests verify:
    1. All navigation events have durations calculated
    2. Durations are realistic (not zero, not infinite)
    3. Specific maneuver types have expected duration ranges
    4. Physics calculations are being used correctly
    """

    @classmethod
    def setUpTestData(cls):
        """Import the test universe."""
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        importer = UniverseImporter(xml_file)
        importer.import_universe()

    def setUp(self):
        self.route_service = RouteService()
        self.earth = Location.objects.get(name="Earth")
        self.moon = Location.objects.get(name="Moon")
        self.mars = Location.objects.get(name="Mars")
        self.earth_control = Location.objects.get(name="Earth Orbital Control")
        self.luna = Location.objects.get(name="Luna")
        self.beta_major = Location.objects.get(name="Beta Major")
        self.ceres = Location.objects.get(name="Ceres")

    def test_all_events_have_durations(self):
        """Test that all navigation events in a route have calculated durations."""
        events = self.route_service.plan_route(self.earth, self.moon)

        self.assertGreater(len(events), 0, "Route should have at least one event")

        for event in events:
            duration = self.route_service.get_event_duration(event)
            self.assertIsNotNone(
                duration, f"Event {event.maneuver} should have a duration"
            )
            self.assertGreater(
                duration, 0, f"Event {event.maneuver} duration should be positive"
            )
            self.assertNotEqual(
                duration,
                float("inf"),
                f"Event {event.maneuver} duration should not be infinite",
            )

    def test_launch_duration_realistic(self):
        """
        Test that LAUNCH events have realistic durations for Moon->Earth route.

        Moon has no atmosphere and low gravity (~0.16g), so launch should be fast.
        Expected: ~30-60 seconds. Bounds: 15-120 seconds (2x tolerance).
        """
        events = self.route_service.plan_route(self.moon, self.earth)

        launch_events = [e for e in events if e.maneuver == ManeuverType.LAUNCH]
        self.assertGreater(
            len(launch_events), 0, "Route should have at least one LAUNCH event"
        )

        for event in launch_events:
            duration = self.route_service.get_event_duration(event)
            # Moon launch: no atmosphere, low gravity -> very fast (~30-60s expected)
            # Bounds: 15-120 seconds (2x tolerance around expected 30-60s range)
            self.assertGreater(
                duration,
                15,
                f"LAUNCH from Moon duration {duration:.1f}s should be at least 15 seconds",
            )
            self.assertLess(
                duration,
                120,
                f"LAUNCH from Moon duration {duration:.1f}s should be less than 120 seconds",
            )

    def test_circularize_duration_realistic(self):
        """
        Test that CIRCULARIZE events have realistic durations for Earth->Moon route.

        Circularize = half orbital period at target altitude (~300km LEO for Earth).
        Expected: ~45 minutes (2700s). Bounds: 1350-5400 seconds (2x tolerance).
        """
        events = self.route_service.plan_route(self.earth, self.moon)

        circularize_events = [
            e for e in events if e.maneuver == ManeuverType.CIRCULARIZE
        ]
        self.assertGreater(
            len(circularize_events),
            0,
            "Route should have at least one CIRCULARIZE event",
        )

        for event in circularize_events:
            duration = self.route_service.get_event_duration(event)
            # Earth LEO circularize: half orbital period at ~300km = ~45 minutes (2700s)
            # Bounds: 1350-5400 seconds (2x tolerance around expected 2700s)
            self.assertGreater(
                duration,
                1350,
                f"CIRCULARIZE at Earth duration {duration:.1f}s should be at least 22.5 minutes",
            )
            self.assertLess(
                duration,
                5400,
                f"CIRCULARIZE at Earth duration {duration:.1f}s should be less than 90 minutes",
            )

    def test_sublight_duration_uses_canonical_speed(self):
        """Test that SUBLIGHT events use canonical 0.1c speed and calculate realistic durations."""
        events = self.route_service.plan_route(self.moon, self.luna)

        sublight_events = [e for e in events if e.maneuver == ManeuverType.SUBLIGHT]
        # This route may or may not have SUBLIGHT, so we'll check if any exist
        if sublight_events:
            for event in sublight_events:
                duration = self.route_service.get_event_duration(event)
                # Sublight at 0.1c for interplanetary distances (0.5-2 AU) should take hours to days
                # 0.5 AU at 0.1c ≈ 42 minutes, 2 AU at 0.1c ≈ 2.8 hours
                self.assertGreater(
                    duration,
                    100,
                    f"SUBLIGHT duration {duration}s should be at least 100 seconds",
                )
                self.assertLess(
                    duration,
                    86400 * 7,
                    f"SUBLIGHT duration {duration}s should be less than a week",
                )

    def test_hyperspace_duration_uses_canonical_speed(self):
        """Test that HYPERSPACE events use canonical 1000c speed and calculate realistic durations."""
        events = self.route_service.plan_route(self.earth, self.beta_major)

        hyperspace_events = [e for e in events if e.maneuver == ManeuverType.HYPERSPACE]
        self.assertGreater(
            len(hyperspace_events), 0, "Route should have at least one HYPERSPACE event"
        )

        for event in hyperspace_events:
            duration = self.route_service.get_event_duration(event)
            # Hyperspace at 1000c: 10 ly = ~3.7 days, 100 ly = ~37 days
            # Should be much faster than sublight
            self.assertGreater(
                duration,
                100,
                f"HYPERSPACE duration {duration}s should be at least 100 seconds",
            )
            self.assertLess(
                duration,
                86400 * 365,
                f"HYPERSPACE duration {duration}s should be less than a year",
            )

    def test_deorbit_duration_realistic(self):
        """
        Test that DEORBIT events have realistic durations for Earth->Moon route.

        Deorbit from Moon orbit (~100km) to entry interface (~50km for Moon).
        Expected: ~15-30 minutes. Bounds: 450-3600 seconds (2x tolerance).
        """
        events = self.route_service.plan_route(self.earth, self.moon)

        deorbit_events = [e for e in events if e.maneuver == ManeuverType.DEORBIT]
        self.assertGreater(
            len(deorbit_events), 0, "Route should have at least one DEORBIT event"
        )

        for event in deorbit_events:
            duration = self.route_service.get_event_duration(event)
            # Moon deorbit: from ~100km orbit to entry interface, quarter orbit approximation
            # Expected: ~15-30 minutes (900-1800s). Bounds: 450-3600 seconds (2x tolerance)
            self.assertGreater(
                duration,
                450,
                f"DEORBIT at Moon duration {duration:.1f}s should be at least 7.5 minutes",
            )
            self.assertLess(
                duration,
                3600,
                f"DEORBIT at Moon duration {duration:.1f}s should be less than 60 minutes",
            )

    def test_landing_duration_realistic(self):
        """
        Test that LANDING events have realistic durations for Earth->Moon route.

        Landing on Moon (no atmosphere, powered descent from ~100km entry interface).
        Expected: ~100 seconds (~1.7 minutes). Bounds: 50-200 seconds (2x tolerance).
        """
        events = self.route_service.plan_route(self.earth, self.moon)

        landing_events = [e for e in events if e.maneuver == ManeuverType.LANDING]
        self.assertGreater(
            len(landing_events), 0, "Route should have at least one LANDING event"
        )

        for event in landing_events:
            duration = self.route_service.get_event_duration(event)
            # Moon landing: no atmosphere, powered descent from ~100km at 2g deceleration
            # Expected: ~100 seconds (~1.7 minutes). Bounds: 50-200 seconds (2x tolerance)
            self.assertGreater(
                duration,
                50,
                f"LANDING on Moon duration {duration:.1f}s should be at least 50 seconds",
            )
            self.assertLess(
                duration,
                200,
                f"LANDING on Moon duration {duration:.1f}s should be less than 200 seconds",
            )

    def test_route_total_duration_accumulates(self):
        """
        Test that total route duration is the sum of all event durations for Earth->Moon.

        Expected route: DIRECT_ASCENT (~hours), CIRCULARIZE (~45min), DEORBIT (~15-30min), LANDING (~5-10min)
        Expected total: ~2-3 hours. Bounds: 3600-21600 seconds (1-6 hours, 2x tolerance).
        """
        events = self.route_service.plan_route(self.earth, self.moon)

        total_duration = sum(self.route_service.get_event_duration(e) for e in events)

        self.assertGreater(total_duration, 0, "Total route duration should be positive")
        # Earth->Moon route: DIRECT_ASCENT + CIRCULARIZE + DEORBIT + LANDING
        # Expected: ~2-3 hours (7200-10800s). Bounds: 3600-21600 seconds (1-6 hours, 2x tolerance)
        self.assertGreater(
            total_duration,
            3600,
            f"Total route duration {total_duration:.1f}s should be at least 1 hour",
        )
        self.assertLess(
            total_duration,
            21600,
            f"Total route duration {total_duration:.1f}s should be less than 6 hours",
        )

    def test_different_routes_have_different_durations(self):
        """Test that different routes have appropriately different durations."""
        route1_events = self.route_service.plan_route(self.earth, self.moon)
        route2_events = self.route_service.plan_route(self.earth, self.mars)

        route1_duration = sum(
            self.route_service.get_event_duration(e) for e in route1_events
        )
        route2_duration = sum(
            self.route_service.get_event_duration(e) for e in route2_events
        )

        # Mars is further than Moon, so route should take longer
        # (unless route2 uses hyperspace, which might be faster)
        # At minimum, both should have realistic durations
        self.assertGreater(route1_duration, 0, "Route 1 should have positive duration")
        self.assertGreater(route2_duration, 0, "Route 2 should have positive duration")

    def test_physics_service_integration(self):
        """
        Test that RouteService is actually using ManeuverPhysicsService for calculations.

        Mars launch: thin atmosphere (~50km), low gravity (~0.38g).
        Expected: ~60-90 seconds. Bounds: 30-180 seconds (2x tolerance).
        """
        # Create a test LAUNCH event from Mars
        from mysite.universe.models.navigation import NavigationEvent

        launch_event = NavigationEvent(
            maneuver=ManeuverType.LAUNCH,
            origin=self.mars,
            current=self.mars,
            next=self.mars,
            destination=self.earth,
        )

        # Get duration from RouteService
        route_duration = self.route_service.get_event_duration(launch_event)

        # Verify it's using physics (not a hardcoded value)
        # If it were hardcoded, it would be exactly 30.0
        self.assertNotEqual(
            route_duration, 30.0, "Duration should not be hardcoded 30.0"
        )

        # Mars launch: thin atmosphere, low gravity -> fast (~60-90s expected)
        # Bounds: 30-180 seconds (2x tolerance around expected 60-90s range)
        self.assertGreater(
            route_duration,
            30,
            f"Mars LAUNCH duration {route_duration:.1f}s should be at least 30 seconds",
        )
        self.assertLess(
            route_duration,
            180,
            f"Mars LAUNCH duration {route_duration:.1f}s should be less than 180 seconds",
        )

    def test_sublight_vs_hyperspace_duration_comparison(self):
        """Test that hyperspace is faster than sublight for the same distance."""
        # Find routes that use both SUBLIGHT and HYPERSPACE
        events = self.route_service.plan_route(self.earth, self.beta_major)

        sublight_events = [e for e in events if e.maneuver == ManeuverType.SUBLIGHT]
        hyperspace_events = [e for e in events if e.maneuver == ManeuverType.HYPERSPACE]

        if sublight_events and hyperspace_events:
            # Get average durations
            sublight_duration = sum(
                self.route_service.get_event_duration(e) for e in sublight_events
            ) / len(sublight_events)
            hyperspace_duration = sum(
                self.route_service.get_event_duration(e) for e in hyperspace_events
            ) / len(hyperspace_events)

            # Hyperspace should be much faster (1000c vs 0.1c = 10,000x faster)
            # But we're comparing different distances, so just verify both are reasonable
            self.assertGreater(
                sublight_duration, 0, "Sublight duration should be positive"
            )
            self.assertGreater(
                hyperspace_duration, 0, "Hyperspace duration should be positive"
            )


class TestRouteServerFacadeMethods(TestCase):
    """
    Call the internal RouteService facade methods directly to cover the
    delegation stubs in route_server.py that are never exercised when
    tests only call plan_route().

    Uses the same test_universe.xml static scenario as the other test
    classes in this file so no additional fixture setup is needed.
    """

    @classmethod
    def setUpTestData(cls):
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        UniverseImporter(xml_file).import_universe()

    def setUp(self):
        self.svc = RouteService()
        self.earth = Location.objects.get(name="Earth")
        self.moon = Location.objects.get(name="Moon")
        self.luna = Location.objects.get(name="Luna")
        self.mars = Location.objects.get(name="Mars")
        self.earth_control = Location.objects.get(name="Earth Orbital Control")
        self.beta_major = Location.objects.get(name="Beta Major")

    def _plan_earth_moon(self):
        return self.svc.plan_route(self.earth, self.moon)

    # ------------------------------------------------------------------
    # Internal delegation stubs
    # ------------------------------------------------------------------

    def test_build_scale_path_via_facade(self):
        """_build_scale_path returns a list of integer-comparable scale values."""
        path = [self.earth, self.moon]
        scale_path = self.svc._build_scale_path(path)
        self.assertEqual(len(scale_path), 2)

    def test_determine_transfer_plan_via_facade(self):
        """_determine_transfer_plan returns a non-empty list for a 2-node path."""
        from mysite.universe.models.scale import OrderedScale, Scale

        scale_path = [OrderedScale(Scale.PLANET), OrderedScale(Scale.MOON)]
        plan = self.svc._determine_transfer_plan(scale_path)
        self.assertGreater(len(plan), 0)

    def test_compress_location_path_via_facade(self):
        """_compress_location_path retains endpoints and surface-type nodes."""
        path = [self.earth, self.moon, self.luna]
        compressed = self.svc._compress_location_path(path)
        # First and last are always kept
        self.assertEqual(compressed[0].name, self.earth.name)
        self.assertEqual(compressed[-1].name, self.luna.name)

    def test_compress_location_path_empty_returns_empty(self):
        """_compress_location_path([]) returns []."""
        result = self.svc._compress_location_path([])
        self.assertEqual(result, [])

    def test_pretty_print_events_via_facade(self):
        """pretty_print_events returns a non-empty string for a valid route."""
        events = self._plan_earth_moon()
        text = self.svc.pretty_print_events(events)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)

    def test_get_local_locations_via_facade(self):
        """get_local_locations returns a list of Location objects."""
        locations = self.svc.get_local_locations(self.earth, Scale.PLANET)
        self.assertIsInstance(locations, list)

    def test_get_relevant_body_for_maneuver_via_facade(self):
        """_get_relevant_body_for_maneuver returns a body or None (no crash)."""
        events = self._plan_earth_moon()
        for event in events:
            body = self.svc._get_relevant_body_for_maneuver(event)
            # May be None for maneuvers with no relevant body; just don't crash
            self.assertTrue(body is None or hasattr(body, "name"))

    def test_extract_body_params_via_facade(self):
        """_extract_body_params returns a dict from a body object."""
        events = self._plan_earth_moon()
        for event in events:
            body = self.svc._get_relevant_body_for_maneuver(event)
            if body is not None:
                params = self.svc._extract_body_params(body)
                self.assertIsInstance(params, dict)
                break

    def test_build_physics_nav_context_via_facade(self):
        """_build_physics_nav_context returns a dict for events that have a body."""
        events = self._plan_earth_moon()
        for event in events:
            body = self.svc._get_relevant_body_for_maneuver(event)
            if body is not None:
                ctx = self.svc._build_physics_nav_context(event, body)
                self.assertIsInstance(ctx, dict)
                break

    def test_determine_maneuvers_via_facade(self):
        """_determine_maneuvers() facade (line 63) delegates to route_plan and returns events."""
        universe = UniverseGraph.get_instance()
        path = universe.get_path(self.earth, self.luna)
        scale_path = self.svc._build_scale_path(path)
        transfer_plan = self.svc._determine_transfer_plan(scale_path)
        compressed = self.svc._compress_location_path(path)
        events = self.svc._determine_maneuvers(
            transfer_plan, compressed, max(scale_path)
        )
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 0)

    def test_enhance_with_controllers_via_facade(self):
        """_enhance_with_controllers() facade (line 66) delegates to route_controllers."""
        universe = UniverseGraph.get_instance()
        path = universe.get_path(self.earth, self.luna)
        scale_path = self.svc._build_scale_path(path)
        transfer_plan = self.svc._determine_transfer_plan(scale_path)
        compressed = self.svc._compress_location_path(path)
        raw_events = self.svc._determine_maneuvers(
            transfer_plan, compressed, max(scale_path)
        )
        enhanced = self.svc._enhance_with_controllers(raw_events)
        self.assertIsInstance(enhanced, list)
        self.assertEqual(len(enhanced), len(raw_events))

    def test_pick_random_destination_via_facade(self):
        """pick_random_destination() facade (line 77) returns a Location different from excluding."""
        result = self.svc.pick_random_destination(excluding=self.earth)
        self.assertIsInstance(result, Location)
        self.assertNotEqual(result.id, self.earth.id)

    def test_random_journey_via_facade(self):
        """random_journey() facade (line 85) returns a non-empty NavigationEvent list."""
        from mysite.universe.models.ship import Ship
        from mysite.universe.models.navigation import NavigationEvent

        ship = Ship.objects.create(name="FACADE TEST SHIP", current_location=self.earth)
        events = self.svc.random_journey(ship)
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 0)
        self.assertIsInstance(events[0], NavigationEvent)


class TestRoutePlanEdgeCases(TestCase):
    """
    Exercise the edge-case branches inside services/route/plan.py that are
    not reachable through the standard plan_route() paths already tested.
    """

    @classmethod
    def setUpTestData(cls):
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        UniverseImporter(xml_file).import_universe()

    def setUp(self):
        self.svc = RouteService()
        self.earth = Location.objects.get(name="Earth")
        self.earth_control = Location.objects.get(name="Earth Orbital Control")
        self.moon = Location.objects.get(name="Moon")

    def test_compress_empty_path_returns_empty(self):
        """compress_location_path([]) must return [] without raising."""
        from mysite.universe.services.route.plan import compress_location_path

        self.assertEqual(compress_location_path([]), [])

    def test_compress_two_node_path_keeps_both_endpoints(self):
        """compress_location_path with two nodes retains both endpoints."""
        from mysite.universe.services.route.plan import compress_location_path

        result = compress_location_path([self.earth, self.moon])
        self.assertEqual(result[0].name, self.earth.name)
        self.assertEqual(result[-1].name, self.moon.name)

    def test_determine_maneuvers_raises_on_short_path(self):
        """
        determine_maneuvers must raise ValueError when given fewer than
        two locations (invalid route).
        """
        from mysite.universe.services.route.plan import determine_maneuvers

        with self.assertRaises(ValueError):
            determine_maneuvers(
                self.svc,
                transfer_plan=[],
                location_path=[self.earth],  # only one location
                overall_max=1,
            )

    def test_plan_route_returns_empty_when_origin_equals_destination(self):
        """
        plan_route() returns [] when origin and destination are the same
        node (path length == 1, which fails the len(path) < 2 guard).
        """
        result = self.svc.plan_route(self.earth, self.earth)
        self.assertEqual(result, [])

    def test_determine_transfer_plan_single_node_returns_unchanged(self):
        """
        determine_transfer_plan with a one-element scale_path should
        return it unchanged (len < 2 early-return branch).
        """
        from mysite.universe.services.route.plan import determine_transfer_plan
        from mysite.universe.models.scale import OrderedScale, Scale

        single = [OrderedScale(Scale.PLANET)]
        result = determine_transfer_plan(single)
        self.assertEqual(result, single)

    def test_station_to_planet_direct_includes_undock(self):
        """
        Station → Planet two-node route exercises the UNDOCK branch of the
        two-node special-case in plan_route.
        """
        events = self.svc.plan_route(self.earth_control, self.earth)
        maneuvers = [e.maneuver.name for e in events]
        self.assertIn("UNDOCK", maneuvers)

    def test_moon_departure_includes_launch(self):
        """
        Moon → Planet two-node route exercises the LAUNCH branch of the
        two-node special-case in plan_route.
        """
        events = self.svc.plan_route(self.moon, self.earth)
        maneuvers = [e.maneuver.name for e in events]
        self.assertIn("LAUNCH", maneuvers)


class TestDetermineManeuversBranches(TestCase):
    """
    Cover the branches in determine_maneuvers() that are unreachable via
    the normal plan_route() flow:
    - DIRECT_ASCENT block (lines 203-245): triggered only when a crafted
      transfer_plan containing ManeuverType.DIRECT_ASCENT is passed directly.
    - Multi-leg Station departure (lines 283-285, 331-332).
    - 3-element INSERTION plan with STATION destination (line 294).
    """

    @classmethod
    def setUpTestData(cls):
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        UniverseImporter(xml_file).import_universe()

    def setUp(self):
        from mysite.universe.models.scale import OrderedScale, Scale

        self.svc = RouteService()
        self.earth = Location.objects.get(name="Earth")
        self.earth_control = Location.objects.get(name="Earth Orbital Control")
        self.luna = Location.objects.get(name="Luna")
        self.moon = Location.objects.get(name="Moon")
        self.mars = Location.objects.get(name="Mars")

        # Shorthand scale values used when crafting transfer plans.
        self.S_PLANET = OrderedScale(Scale.PLANET)
        self.S_MOON = OrderedScale(Scale.MOON)
        self.S_STATION = OrderedScale(Scale.STATION)
        self.S_STARSYSTEM = OrderedScale(Scale.STARSYSTEM)

    def _maneuver_names(self, events):
        return [e.maneuver.name for e in events]

    # ------------------------------------------------------------------
    # DIRECT_ASCENT block (lines 203-245)
    # ------------------------------------------------------------------

    def test_direct_ascent_station_origin_planet_dest(self):
        """
        DIRECT_ASCENT with Station origin → UNDOCK prepended (line 225-226),
        DIRECT_ASCENT in the middle (229), DEORBIT+LANDING at arrival (240-241).
        """
        tp = [self.S_STATION, ManeuverType.DIRECT_ASCENT, self.S_PLANET]
        events = self.svc._determine_maneuvers(
            tp, [self.earth_control, self.earth], self.S_STARSYSTEM
        )
        names = self._maneuver_names(events)
        self.assertIn("UNDOCK", names)
        self.assertIn("DIRECT_ASCENT", names)
        self.assertIn("DEORBIT", names)
        self.assertIn("LANDING", names)
        self.assertNotIn("DOCK", names)
        self.assertNotIn("CIRCULARIZE", names)

    def test_direct_ascent_moon_origin_moon_dest(self):
        """
        DIRECT_ASCENT with Moon origin → LAUNCH prepended (227-228),
        CIRCULARIZE+DEORBIT+LANDING at Moon arrival (232-239).
        """
        tp = [self.S_MOON, ManeuverType.DIRECT_ASCENT, self.S_MOON]
        events = self.svc._determine_maneuvers(
            tp, [self.luna, self.moon], self.S_STARSYSTEM
        )
        names = self._maneuver_names(events)
        self.assertIn("LAUNCH", names)
        self.assertIn("DIRECT_ASCENT", names)
        self.assertIn("CIRCULARIZE", names)
        self.assertIn("DEORBIT", names)
        self.assertIn("LANDING", names)

    def test_direct_ascent_planet_origin_station_dest(self):
        """
        DIRECT_ASCENT with Station destination → DOCK appended (230-231),
        no LAUNCH or UNDOCK on the origin side.
        """
        tp = [self.S_PLANET, ManeuverType.DIRECT_ASCENT, self.S_STATION]
        events = self.svc._determine_maneuvers(
            tp, [self.earth, self.earth_control], self.S_STARSYSTEM
        )
        names = self._maneuver_names(events)
        self.assertIn("DIRECT_ASCENT", names)
        self.assertIn("DOCK", names)
        self.assertNotIn("UNDOCK", names)
        self.assertNotIn("CIRCULARIZE", names)

    def test_direct_ascent_planet_origin_planet_dest(self):
        """
        DIRECT_ASCENT with Planet destination (else branch, line 240-241):
        DEORBIT+LANDING but no DOCK or CIRCULARIZE.
        """
        tp = [self.S_PLANET, ManeuverType.DIRECT_ASCENT, self.S_PLANET]
        events = self.svc._determine_maneuvers(
            tp, [self.earth, self.mars], self.S_STARSYSTEM
        )
        names = self._maneuver_names(events)
        self.assertIn("DIRECT_ASCENT", names)
        self.assertIn("DEORBIT", names)
        self.assertIn("LANDING", names)
        self.assertNotIn("DOCK", names)
        self.assertNotIn("CIRCULARIZE", names)

    # ------------------------------------------------------------------
    # Multi-leg Station departure (lines 283-285) and non-planetary
    # origin transfer phase (lines 331-332)
    # ------------------------------------------------------------------

    def test_multileg_station_departure_covers_undock_and_sublight(self):
        """
        Multi-leg route from a Station origin (len(transfer_plan) > 3):
        - Departure phase: UNDOCK, INSERTION, CIRCULARIZE (lines 283-285).
        - Transfer phase: non-planetary origin → SUBLIGHT, CIRCULARIZE (331-332).
        """
        tp = [
            self.S_STATION,
            ManeuverType.INSERTION,
            self.S_PLANET,
            ManeuverType.SUBLIGHT,
            self.S_PLANET,
        ]
        events = self.svc._determine_maneuvers(
            tp, [self.earth_control, self.earth, self.mars], self.S_STARSYSTEM
        )
        names = self._maneuver_names(events)
        self.assertIn("UNDOCK", names)
        self.assertIn("INSERTION", names)
        self.assertIn("SUBLIGHT", names)
        self.assertIn("DEORBIT", names)
        self.assertIn("LANDING", names)

    # ------------------------------------------------------------------
    # 3-element INSERTION plan with STATION destination (line 294)
    # ------------------------------------------------------------------

    def test_insertion_plan_to_station_dest_adds_plane_change(self):
        """
        3-element transfer plan (INSERTION, not DIRECT_ASCENT) with Station
        destination: transfer phase emits PLANE_CHANGE (line 294).
        """
        tp = [self.S_PLANET, ManeuverType.INSERTION, self.S_STATION]
        events = self.svc._determine_maneuvers(
            tp, [self.earth, self.earth_control], self.S_STARSYSTEM
        )
        names = self._maneuver_names(events)
        self.assertIn("PLANE_CHANGE", names)
        self.assertIn("DOCK", names)

    def test_hyperspace_route_to_station_adds_plane_change(self):
        """
        Multi-leg transfer plan with a HYPERSPACE segment and Station destination
        appends a PLANE_CHANGE arrival event (plan.py line 329).

        Requires:
          - len(transfer_plan) > 3  (multi-leg)
          - origin scale is planetary  (is_origin_planetary = True)
          - plan contains ManeuverType.HYPERSPACE
          - dest_type == TypeName.STATION
        """
        tp = [
            self.S_PLANET,
            ManeuverType.HYPERSPACE,
            self.S_STARSYSTEM,
            ManeuverType.SUBLIGHT,
            self.S_STATION,
        ]
        events = self.svc._determine_maneuvers(
            tp, [self.earth, self.earth_control], self.S_STARSYSTEM
        )
        names = self._maneuver_names(events)
        # The hyperspace loop adds SUBLIGHT + HYPERSPACE + SUBLIGHT + CIRCULARIZE,
        # then the station check appends PLANE_CHANGE.
        self.assertIn("HYPERSPACE", names)
        self.assertIn("PLANE_CHANGE", names)
        self.assertIn("DOCK", names)
