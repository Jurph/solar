"""Unit tests for dialogue particle classes."""
from django.test import TestCase
from mysite.universe.models.actor import Actor, Pilot, Controller
from mysite.universe.models.ship import Ship
from mysite.universe.services.dialogue.particles import (
    LaunchRequest,
    CircularizationRequest,
    InsertionRequest,
    GenericRequest,
    RadioResponse,
    LaunchResponse,
    OrbitResponse,
    DepartureResponse,
    RadioAcknowledgment,
    RadioReadback,
    HoldResponse,
    Holding,
    AdjustedResponse,
)


class DialogueParticleTest(TestCase):
    """Base test class for dialogue particles with common fixtures."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data shared across all particle tests."""
        # Create a test location first (required for Ship)
        from mysite.universe.models.base import Location
        from mysite.universe.models.scale import Scale
        cls.location = Location.objects.create(
            name="Test Station",
            scale=Scale.STATION
        )
        
        # Create test ship (using factory method with location)
        cls.ship = Ship.create(location=cls.location, name="TEST SHIP")
        
        # Create test pilot with ship
        cls.pilot = Pilot.create(ship=cls.ship)
        cls.pilot.name = "Test Pilot"
        cls.pilot.role = Actor.Role.PILOT
        cls.pilot.save()
        
        # Create test controller
        cls.controller = Controller.create()
        cls.controller.name = "Mars Control"
        cls.controller.role = Actor.Role.CONTROLLER
        cls.controller.save()
        
        # Standard nav_context for testing
        cls.nav_context = {
            "maneuver_type": "launch",
            "current_location": "Mars",
            "destination": "Earth",
            "inclination_deg": "20",
            "altitude_km": "150",
        }
    
    def setUp(self):
        """Set up for each test."""
        # Reset nav_context to defaults
        self.nav_context = self.__class__.nav_context.copy()


class TestPilotRequestParticles(DialogueParticleTest):
    """Test pilot request particle classes."""
    
    def test_launch_request_role_description(self):
        """Test LaunchRequest returns correct role description."""
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        role_desc = particle.get_role_description()
        self.assertIn("Test Pilot", role_desc)
        self.assertIn("TEST SHIP", role_desc)
    
    def test_launch_request_situation_description(self):
        """Test LaunchRequest situation description includes ship and maneuver."""
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        situation = particle.get_situation_description()
        self.assertIn("TEST SHIP", situation)
        self.assertIn("launch", situation.lower())
        self.assertIn("MARS CONTROL", situation)
    
    def test_launch_request_examples_integrate_context_values(self):
        """Test that examples incorporate nav_context values when provided."""
        self.nav_context["destination"] = "Saturn"
        self.nav_context["azimuth"] = "ninety"
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        # At least some examples should reference the context values
        destination_found = any("Saturn" in ex for ex in examples)
        azimuth_found = any("ninety" in ex.lower() for ex in examples)
        self.assertTrue(destination_found, "Examples should incorporate destination from nav_context")
        self.assertTrue(azimuth_found, "Examples should incorporate azimuth from nav_context")
    
    def test_examples_are_diverse(self):
        """Test that examples are not all identical templates."""
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 1)
        # Check examples are different from each other
        unique_examples = set(examples)
        # Should have at least 3 unique examples (we have 8 total)
        self.assertGreaterEqual(len(unique_examples), 3, 
                               "Examples should be diverse, not identical templates")

    
    def test_circularization_request_examples_integrate_context(self):
        """Test that CircularizationRequest examples use nav_context values."""
        self.nav_context["maneuver_type"] = "circularize"
        self.nav_context["altitude_km"] = "200"
        self.nav_context["inclination_deg"] = "45"
        particle = CircularizationRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should reference orbital maneuvers (circularization, orbit, apogee, etc.)
        orbit_keywords = ["circulariz", "orbit", "apogee", "altitude", "inclination"]
        found_keyword = any(
            keyword in example.lower()
            for example in examples
            for keyword in orbit_keywords
        )
        self.assertTrue(found_keyword, "Examples should reference orbital maneuvers")
    
    def test_insertion_request_examples(self):
        """Test InsertionRequest examples are appropriate."""
        self.nav_context["maneuver_type"] = "insertion"
        particle = InsertionRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        for example in examples:
            self.assertIn("insertion", example.lower())
    
    def test_generic_request_fallback(self):
        """Test GenericRequest works for unknown maneuver types."""
        self.nav_context["maneuver_type"] = "unknown_maneuver"
        particle = GenericRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Should include the maneuver type in examples
        for example in examples:
            self.assertIn("unknown_maneuver", example.lower())


class TestControllerResponseParticles(DialogueParticleTest):
    """Test controller response particle classes."""
    
    def test_radio_response_role_description(self):
        """Test RadioResponse returns correct controller role description."""
        particle = RadioResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        role_desc = particle.get_role_description()
        self.assertIn("anonymous space traffic controller", role_desc.lower())
        self.assertIn("Mars Control", role_desc)
    
    def test_radio_response_situation_description(self):
        """Test RadioResponse situation description is correct."""
        particle = RadioResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        situation = particle.get_situation_description()
        self.assertIn("TEST SHIP", situation)
        self.assertIn("requested clearance", situation.lower())
        self.assertIn("MARS CONTROL", situation)
    
    def test_launch_response_examples(self):
        """Test LaunchResponse examples are launch-specific."""
        particle = LaunchResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should reference launch
        launch_keywords = ["launch", "takeoff", "departure", "go"]
        found_keyword = any(
            keyword in example.lower() 
            for example in examples 
            for keyword in launch_keywords
        )
        self.assertTrue(found_keyword, "Examples should reference launch")
    
    def test_orbit_response_examples(self):
        """Test OrbitResponse examples include orbital keywords."""
        self.nav_context["maneuver_type"] = "insertion"
        particle = OrbitResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should reference orbital keywords
        orbit_keywords = ["orbit", "insertion", "cleared", "degrees", "kilometers"]
        found_keyword = any(
            keyword in example.lower()
            for example in examples
            for keyword in orbit_keywords
        )
        self.assertTrue(found_keyword, "Examples should reference orbital parameters")
    
    def test_departure_response_examples_use_dynamic_destination(self):
        """Test that DepartureResponse examples use nav_context destination, not hardcoded."""
        self.nav_context["maneuver_type"] = "sublight"
        self.nav_context["destination"] = "Neptune"
        particle = DepartureResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should use the actual destination from nav_context
        destination_found = any("Neptune" in ex for ex in examples)
        self.assertTrue(destination_found, "Examples should use nav_context destination dynamically")
    
    def test_hold_response_examples(self):
        """Test HoldResponse examples indicate holding."""
        particle = HoldResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should reference holding
        hold_keywords = ["hold", "negative", "stand by", "wait"]
        found_keyword = any(
            keyword in example.lower() 
            for example in examples 
            for keyword in hold_keywords
        )
        self.assertTrue(found_keyword, "Examples should reference holding")
    
    def test_adjusted_response_examples(self):
        """Test AdjustedResponse examples indicate adjustment."""
        particle = AdjustedResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should reference adjustment or clearing
        adjust_keywords = ["adjust", "cleared", "okay", "sorry"]
        found_keyword = any(
            keyword in example.lower() 
            for example in examples 
            for keyword in adjust_keywords
        )
        self.assertTrue(found_keyword, "Examples should reference adjustment")


class TestPilotAcknowledgmentParticles(DialogueParticleTest):
    """Test pilot acknowledgment particle classes."""
    
    def test_radio_acknowledgment_role_description(self):
        """Test RadioAcknowledgment returns pilot role description."""
        particle = RadioAcknowledgment(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        role_desc = particle.get_role_description()
        self.assertIn("Test Pilot", role_desc)
        self.assertIn("TEST SHIP", role_desc)
    
    def test_select_examples_returns_different_selections(self):
        """Test that select_examples() returns different examples when called multiple times."""
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        # Call select_examples multiple times
        selections = [particle.select_examples(3) for _ in range(10)]
        # Should get different combinations (not all identical)
        unique_selections = set(tuple(sel) for sel in selections)
        # With 8 examples and selecting 3, we should get some variety
        self.assertGreater(len(unique_selections), 1, 
                          "select_examples() should return different selections")
    
    def test_radio_readback_examples(self):
        """Test RadioReadback examples include readback phrases."""
        particle = RadioReadback(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should include readback indicators
        readback_keywords = ["understood", "copy", "maintaining", "cleared"]
        found_keyword = any(
            keyword in example.lower() 
            for example in examples 
            for keyword in readback_keywords
        )
        self.assertTrue(found_keyword, "Examples should include readback phrases")
    
    def test_holding_examples(self):
        """Test Holding examples indicate holding position."""
        particle = Holding(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should reference holding
        hold_keywords = ["holding", "roger", "copy"]
        found_keyword = any(
            keyword in example.lower() 
            for example in examples 
            for keyword in hold_keywords
        )
        self.assertTrue(found_keyword, "Examples should reference holding")


class TestParticleSenderCallsign(DialogueParticleTest):
    """Test that get_sender_callsign works correctly for all particle types."""
    
    def test_pilot_request_sender_callsign(self):
        """Test pilot request uses ship name as sender."""
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        sender = particle.get_sender_callsign()
        self.assertEqual(sender, "TEST SHIP")
    
    def test_controller_response_sender_callsign(self):
        """Test controller response uses controller name as sender."""
        particle = RadioResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        sender = particle.get_sender_callsign()
        self.assertEqual(sender, "MARS CONTROL")
    
    def test_pilot_acknowledgment_sender_callsign(self):
        """Test pilot acknowledgment uses ship name as sender."""
        particle = RadioAcknowledgment(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        sender = particle.get_sender_callsign()
        self.assertEqual(sender, "TEST SHIP")


class TestParticlePromptBuilding(DialogueParticleTest):
    """Test that particles can build user prompt data correctly."""
    
    def test_launch_request_builds_prompt_data(self):
        """Test LaunchRequest can build UserPromptData."""
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context
        )
        prompt_data = particle.build_user_prompt_data()
        
        # Verify all required fields are present
        self.assertIsNotNone(prompt_data.role)
        self.assertIsNotNone(prompt_data.situation)
        self.assertEqual(prompt_data.sender, "TEST SHIP")
        self.assertEqual(prompt_data.recipient, "MARS CONTROL")
        self.assertGreater(len(prompt_data.example1), 0)
        self.assertGreater(len(prompt_data.example2), 0)
        self.assertGreater(len(prompt_data.example3), 0)
        self.assertGreater(len(prompt_data.counterexample), 0)
    
    def test_radio_response_builds_prompt_data(self):
        """Test RadioResponse can build UserPromptData."""
        particle = RadioResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context
        )
        prompt_data = particle.build_user_prompt_data()
        
        # Verify all required fields are present
        self.assertIsNotNone(prompt_data.role)
        self.assertIsNotNone(prompt_data.situation)
        self.assertEqual(prompt_data.sender, "MARS CONTROL")
        self.assertEqual(prompt_data.recipient, "TEST SHIP")
        self.assertGreater(len(prompt_data.example1), 0)
        self.assertGreater(len(prompt_data.example2), 0)
        self.assertGreater(len(prompt_data.example3), 0)
        self.assertGreater(len(prompt_data.counterexample), 0)

