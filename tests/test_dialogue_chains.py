"""
Unit tests for dialogue chain generation from navigation events.

Tests that:
1. ParticleFactory creates correct request particles for each maneuver type
2. Each particle's get_next_particle_probabilities() produces valid chains
3. Complete chains can be walked through without LLM calls
"""
from django.test import TestCase
from mysite.universe.models.actor import Pilot, Controller
from mysite.universe.models.ship import Ship
from mysite.universe.models.navigation import ManeuverType
from mysite.universe.services.dialogue.factory import ParticleFactory
from mysite.universe.services.dialogue.particles import (
    LaunchRequest,
    CircularizationRequest,
    InsertionRequest,
    SublightRequest,
    DeorbitRequest,
    LandingRequest,
    GenericRequest,
    RadioResponse,
    RadioReadback,
    HoldResponse,
    Holding,
)


class DialogueChainTest(TestCase):
    """Base test class with common fixtures."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data shared across all tests."""
        from mysite.universe.models.base import Location
        from mysite.universe.models.scale import Scale
        
        cls.location = Location.objects.create(name="Test Station", scale=Scale.STATION)
        cls.ship = Ship.create(location=cls.location, name="TEST SHIP")
        cls.pilot = Pilot.create(ship=cls.ship)
        cls.pilot.name = "Test Pilot"
        cls.pilot.save()
        
        cls.controller = Controller.create()
        cls.controller.name = "Mars Control"
        cls.controller.save()
        
        cls.base_nav_context = {
            "current_location": "Mars",
            "destination": "Earth",
            "inclination_deg": "20",
            "altitude_km": "150",
            "azimuth": "55",
        }


class TestParticleFactoryManeuverMapping(DialogueChainTest):
    """Test that ParticleFactory creates correct particles for each ManeuverType."""
    
    def test_launch_creates_launch_request(self):
        """LAUNCH maneuver creates LaunchRequest particle."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        particle = ParticleFactory.create_particle(
            particle_type="launch",
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, LaunchRequest)
    
    def test_circularize_creates_circularization_request(self):
        """CIRCULARIZE maneuver creates CircularizationRequest particle."""
        nav_context = {**self.base_nav_context, "maneuver_type": "circularize"}
        particle = ParticleFactory.create_particle(
            particle_type="circularize",
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, CircularizationRequest)
    
    def test_insertion_creates_insertion_request(self):
        """INSERTION maneuver creates InsertionRequest particle."""
        nav_context = {**self.base_nav_context, "maneuver_type": "insertion"}
        particle = ParticleFactory.create_particle(
            particle_type="insertion",
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, InsertionRequest)
    
    def test_sublight_creates_sublight_request(self):
        """SUBLIGHT maneuver creates SublightRequest particle."""
        nav_context = {**self.base_nav_context, "maneuver_type": "sublight"}
        particle = ParticleFactory.create_particle(
            particle_type="sublight",
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, SublightRequest)
    
    def test_deorbit_creates_deorbit_request(self):
        """DEORBIT maneuver creates DeorbitRequest particle."""
        nav_context = {**self.base_nav_context, "maneuver_type": "deorbit"}
        particle = ParticleFactory.create_particle(
            particle_type="deorbit",
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, DeorbitRequest)
    
    def test_landing_creates_landing_request(self):
        """LANDING maneuver creates LandingRequest particle."""
        nav_context = {**self.base_nav_context, "maneuver_type": "landing"}
        particle = ParticleFactory.create_particle(
            particle_type="landing",
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, LandingRequest)
    
    def test_unknown_maneuver_creates_generic_request(self):
        """Unknown maneuver types fall back to GenericRequest."""
        nav_context = {**self.base_nav_context, "maneuver_type": "hyperspace"}
        particle = ParticleFactory.create_particle(
            particle_type="hyperspace",  # Not in REQUEST_PARTICLE_MAP
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, GenericRequest)


class TestParticleFactoryResponseMapping(DialogueChainTest):
    """Test that ParticleFactory creates RadioResponse for all maneuver types."""
    
    def test_response_for_launch_maneuver(self):
        """LAUNCH maneuver gets RadioResponse particle with launch-specific examples."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        particle = ParticleFactory.create_particle(
            particle_type="response",
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, RadioResponse)
        examples = particle.get_examples()
        # Examples should be launch-specific
        self.assertTrue(any("launch" in ex.lower() or "burn" in ex.lower() for ex in examples))
    
    def test_response_for_circularize_maneuver(self):
        """CIRCULARIZE maneuver gets RadioResponse with orbital examples."""
        nav_context = {**self.base_nav_context, "maneuver_type": "circularize"}
        particle = ParticleFactory.create_particle(
            particle_type="response",
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, RadioResponse)
        examples = particle.get_examples()
        # Examples should be orbital-specific
        self.assertTrue(any("circularize" in ex.lower() or "orbit" in ex.lower() for ex in examples))
    
    def test_response_for_insertion_maneuver(self):
        """INSERTION maneuver gets RadioResponse with orbital examples."""
        nav_context = {**self.base_nav_context, "maneuver_type": "insertion"}
        particle = ParticleFactory.create_particle(
            particle_type="response",
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, RadioResponse)
        examples = particle.get_examples()
        # Examples should be insertion-specific
        self.assertTrue(any("insertion" in ex.lower() or "orbit" in ex.lower() for ex in examples))
    
    def test_response_for_sublight_maneuver(self):
        """SUBLIGHT maneuver gets RadioResponse with departure examples."""
        nav_context = {**self.base_nav_context, "maneuver_type": "sublight", "destination": "Mars"}
        particle = ParticleFactory.create_particle(
            particle_type="response",
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, RadioResponse)
        examples = particle.get_examples()
        # Examples should be departure-specific
        self.assertTrue(any("sublight" in ex.lower() or "burn" in ex.lower() or "Mars" in ex for ex in examples))
    
    def test_response_for_hyperspace_maneuver(self):
        """HYPERSPACE maneuver gets RadioResponse with departure examples."""
        nav_context = {**self.base_nav_context, "maneuver_type": "hyperspace", "destination": "Jupiter"}
        particle = ParticleFactory.create_particle(
            particle_type="response",
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, RadioResponse)
        examples = particle.get_examples()
        # Examples should be departure-specific
        self.assertTrue(any("hyperspace" in ex.lower() or "jump" in ex.lower() or "Jupiter" in ex for ex in examples))
    
    def test_response_for_unknown_maneuver(self):
        """Unknown maneuver types get RadioResponse with generic examples."""
        nav_context = {**self.base_nav_context, "maneuver_type": "dock"}
        particle = ParticleFactory.create_particle(
            particle_type="response",
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        self.assertIsInstance(particle, RadioResponse)


class TestChainStructure(DialogueChainTest):
    """Test that particle chains flow correctly via get_next_particle_probabilities()."""
    
    def test_request_leads_to_response_or_hold(self):
        """All request particles lead to response or hold_response."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        request = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        probs = request.get_next_particle_probabilities()
        
        # Request should lead to response or hold_response
        self.assertTrue(
            "response" in probs or "hold_response" in probs,
            f"Request should lead to response or hold_response, got: {probs}"
        )
        # Probabilities should sum to ~1.0
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=2)
    
    def test_response_leads_to_readback(self):
        """Response particles lead to readback (approval requires confirmation)."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        response = RadioResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        probs = response.get_next_particle_probabilities()
        
        # Response should lead to readback
        self.assertIn("readback", probs)
        self.assertEqual(probs["readback"], 1.0)
    
    def test_readback_ends_chain(self):
        """Readback particles end the chain (empty probabilities)."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        readback = RadioReadback(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        probs = readback.get_next_particle_probabilities()
        
        # Readback should end chain
        self.assertEqual(probs, {})
    
    def test_hold_response_leads_to_holding(self):
        """HoldResponse leads to Holding acknowledgment."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        hold = HoldResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        probs = hold.get_next_particle_probabilities()
        
        self.assertIn("holding", probs)
        self.assertEqual(probs["holding"], 1.0)
    
    def test_holding_leads_to_adjusted_response(self):
        """Holding acknowledgment leads to adjusted response."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        holding = Holding(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        probs = holding.get_next_particle_probabilities()
        
        self.assertIn("adjusted_response", probs)
        self.assertEqual(probs["adjusted_response"], 1.0)
    
    def test_adjusted_response_leads_to_readback(self):
        """Adjusted response (after hold) leads to readback (same as regular approval)."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        adjusted = RadioResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        probs = adjusted.get_next_particle_probabilities()
        
        self.assertIn("readback", probs)
        self.assertEqual(probs["readback"], 1.0)


class TestCompleteChainWalk(DialogueChainTest):
    """Test that we can walk through complete chains without LLM calls."""
    
    def _walk_chain(self, initial_particle, max_steps=10):
        """
        Walk through a chain using get_next_particle_probabilities().
        Returns list of particle classes encountered.
        """
        chain = [type(initial_particle).__name__]
        current = initial_particle
        
        for _ in range(max_steps):
            probs = current.get_next_particle_probabilities()
            if not probs:
                break  # Chain ends
            
            # Pick first available next particle type (deterministic for testing)
            next_type = list(probs.keys())[0]
            
            # Determine actor for next particle
            if next_type in ["response", "hold_response", "adjusted_response"]:
                actor = self.controller
                recipient = "TEST SHIP"
            else:
                actor = self.pilot
                recipient = "MARS CONTROL"
            
            current = ParticleFactory.create_particle(
                particle_type=next_type,
                actor=actor,
                recipient=recipient,
                nav_context=current.nav_context
            )
            chain.append(type(current).__name__)
        
        return chain
    
    def test_standard_launch_chain(self):
        """Standard launch chain: LaunchRequest → RadioResponse → RadioReadback."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        request = LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        
        chain = self._walk_chain(request)
        
        # Should have 3 steps: request, response, readback
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0], "LaunchRequest")
        self.assertEqual(chain[1], "RadioResponse")
        self.assertEqual(chain[2], "RadioReadback")
    
    def test_standard_circularize_chain(self):
        """Standard circularize chain: CircularizationRequest → RadioResponse → RadioReadback."""
        nav_context = {**self.base_nav_context, "maneuver_type": "circularize"}
        request = CircularizationRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        
        chain = self._walk_chain(request)
        
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0], "CircularizationRequest")
        self.assertEqual(chain[1], "RadioResponse")
        self.assertEqual(chain[2], "RadioReadback")
    
    def test_standard_sublight_chain(self):
        """Standard sublight chain: SublightRequest → DepartureResponse → RadioReadback."""
        nav_context = {**self.base_nav_context, "maneuver_type": "sublight"}
        request = SublightRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=nav_context
        )
        
        chain = self._walk_chain(request)
        
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0], "SublightRequest")
        self.assertEqual(chain[1], "RadioResponse")
        self.assertEqual(chain[2], "RadioReadback")
    
    def test_hold_chain_structure(self):
        """Hold chain: Request → HoldResponse → Holding → AdjustedResponse → RadioReadback."""
        nav_context = {**self.base_nav_context, "maneuver_type": "launch"}
        
        # Start with HoldResponse (simulating controller deciding to hold)
        hold = HoldResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context
        )
        
        chain = self._walk_chain(hold)
        
        # Should have 4 steps from HoldResponse
        self.assertEqual(len(chain), 4)
        self.assertEqual(chain[0], "HoldResponse")
        self.assertEqual(chain[1], "Holding")
        self.assertEqual(chain[2], "RadioResponse")
        self.assertEqual(chain[3], "RadioReadback")


class TestAllManeuverTypesGenerateChains(DialogueChainTest):
    """Test that every ManeuverType can generate a valid dialogue chain."""
    
    def test_all_maneuver_types_produce_valid_chains(self):
        """Every ManeuverType enum value produces a valid chain structure."""
        for maneuver_type in ManeuverType:
            maneuver_str = maneuver_type.value.replace(" ", "_").lower()
            nav_context = {**self.base_nav_context, "maneuver_type": maneuver_str}
            
            with self.subTest(maneuver=maneuver_type.name):
                # Create initial request particle
                particle = ParticleFactory.create_particle(
                    particle_type=maneuver_str,
                    actor=self.pilot,
                    recipient="MARS CONTROL",
                    nav_context=nav_context
                )
                
                # Particle should be some kind of request
                self.assertTrue(
                    hasattr(particle, 'get_next_particle_probabilities'),
                    f"Particle for {maneuver_type} should have get_next_particle_probabilities()"
                )
                
                # Should have valid probabilities
                probs = particle.get_next_particle_probabilities()
                self.assertIsInstance(probs, dict)
                
                # If probabilities exist, they should sum to ~1.0
                if probs:
                    self.assertAlmostEqual(
                        sum(probs.values()), 1.0, places=2,
                        msg=f"Probabilities for {maneuver_type} should sum to 1.0"
                    )
