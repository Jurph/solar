"""Unit tests for dialogue particle classes."""

from django.test import TestCase
from mysite.universe.models.actor import Pilot, Controller
from mysite.universe.models.ship import Ship
from mysite.universe.services.dialogue.particles import (
    LaunchRequest,
    InsertionRequest,
    SublightRequest,
    HyperspaceRequest,
    GenericRequest,
    RadioResponse,
    RadioReadback,
    HoldResponse,
    Holding,
    NavBroadcast,
    GratitudeParticle,
)


class DialogueParticleTest(TestCase):
    """Base test class for dialogue particles with common fixtures."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data shared across all particle tests."""
        # Create a test location first (required for Ship)
        from mysite.universe.models.base import Location
        from mysite.universe.models.scale import Scale

        cls.location = Location.objects.create(name="Test Station", scale=Scale.STATION)

        # Create test ship (using factory method with location)
        cls.ship = Ship.create(location=cls.location, name="TEST SHIP")

        # Create test pilot with ship
        cls.pilot = Pilot.create(ship=cls.ship)
        cls.pilot.name = "Test Pilot"
        cls.pilot.save()

        # Create test controller
        cls.controller = Controller.create()
        cls.controller.name = "Mars Control"
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
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        role_desc = particle.get_role_description()
        self.assertIn("Test Pilot", role_desc)
        self.assertIn("TEST SHIP", role_desc)

    def test_launch_request_situation_description(self):
        """Test LaunchRequest situation description includes ship and maneuver."""
        particle = LaunchRequest(
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        situation = particle.get_situation_description()
        self.assertIn("TEST SHIP", situation)
        self.assertIn("launch", situation.lower())
        self.assertIn("MARS CONTROL", situation)

    def test_launch_request_examples_integrate_context_values(self):
        """Test that examples incorporate nav_context values when provided."""
        self.nav_context["destination"] = "Saturn"
        self.nav_context["azimuth_deg"] = 90  # Use numeric value and correct key name
        particle = LaunchRequest(
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        examples = particle.get_examples()
        # At least some examples should reference the context values
        destination_found = any("Saturn" in ex for ex in examples)
        azimuth_found = any("90" in ex or "ninety" in ex.lower() for ex in examples)
        self.assertTrue(
            destination_found,
            "Examples should incorporate destination from nav_context",
        )
        self.assertTrue(
            azimuth_found, "Examples should incorporate azimuth_deg from nav_context"
        )

    def test_examples_are_diverse(self):
        """Test that examples are not all identical templates."""
        particle = LaunchRequest(
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 1)
        # Check examples are different from each other
        unique_examples = set(examples)
        # Should have at least 3 unique examples (we have 8 total)
        self.assertGreaterEqual(
            len(unique_examples),
            3,
            "Examples should be diverse, not identical templates",
        )

    def test_generic_request_fallback(self):
        """Test GenericRequest does not crash on unknown maneuver types."""
        self.nav_context["maneuver_type"] = "unknown_maneuver"
        particle = GenericRequest(
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)

    def test_sublight_request_uses_azimuth_language(self):
        self.nav_context["maneuver_type"] = "sublight"
        self.nav_context["destination"] = "Neptune"
        particle = SublightRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context,
        )
        examples = particle.get_examples()
        self.assertTrue(any("azimuth" in ex.lower() for ex in examples))
        self.assertTrue(any("burn" in ex.lower() for ex in examples))

    def test_hyperspace_request_mentions_jump_and_azimuth(self):
        self.nav_context["maneuver_type"] = "hyperspace"
        self.nav_context["destination"] = "Alpha Centauri"
        particle = HyperspaceRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context,
        )
        examples = particle.get_examples()
        self.assertTrue(any("hyperspace" in ex.lower() for ex in examples))
        self.assertTrue(any("azimuth" in ex.lower() for ex in examples))


class TestControllerResponseParticles(DialogueParticleTest):
    """Test controller response particle classes."""

    def test_radio_response_role_description(self):
        """Test RadioResponse returns correct controller role description."""
        particle = RadioResponse(
            actor=self.controller, recipient="TEST SHIP", nav_context=self.nav_context
        )
        role_desc = particle.get_role_description()
        self.assertIn("anonymous space traffic controller", role_desc.lower())
        self.assertIn("Mars Control", role_desc)

    def test_radio_response_situation_description(self):
        """Test RadioResponse situation description is correct."""
        particle = RadioResponse(
            actor=self.controller, recipient="TEST SHIP", nav_context=self.nav_context
        )
        situation = particle.get_situation_description()
        self.assertIn("TEST SHIP", situation)
        self.assertIn("requested clearance", situation.lower())
        self.assertIn("MARS CONTROL", situation)

    def test_radio_response_examples_are_context_aware(self):
        """Test RadioResponse generates context-aware examples based on maneuver type."""
        # Test launch examples
        self.nav_context["maneuver_type"] = "launch"
        particle = RadioResponse(
            actor=self.controller, recipient="TEST SHIP", nav_context=self.nav_context
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0)
        # Examples should reference launch
        launch_keywords = ["launch", "burn", "approved", "go"]
        found_keyword = any(
            keyword in example.lower()
            for example in examples
            for keyword in launch_keywords
        )
        self.assertTrue(found_keyword, "Launch examples should reference launch")

        # Test orbital examples
        self.nav_context["maneuver_type"] = "insertion"
        particle = RadioResponse(
            actor=self.controller, recipient="TEST SHIP", nav_context=self.nav_context
        )
        examples = particle.get_examples()
        orbit_keywords = ["insertion", "cleared", "orbit", "degrees", "kilometers"]
        found_keyword = any(
            keyword in example.lower()
            for example in examples
            for keyword in orbit_keywords
        )
        self.assertTrue(
            found_keyword, "Orbital examples should reference orbital parameters"
        )

        # Test departure examples with destination
        self.nav_context["maneuver_type"] = "sublight"
        self.nav_context["destination"] = "Neptune"
        particle = RadioResponse(
            actor=self.controller, recipient="TEST SHIP", nav_context=self.nav_context
        )
        examples = particle.get_examples()
        # Examples should use the actual destination from nav_context
        destination_found = any("Neptune" in ex for ex in examples)
        self.assertTrue(
            destination_found, "Examples should use nav_context destination dynamically"
        )

        # Hyperspace responses should use "jump" language and include an azimuth.
        self.nav_context["maneuver_type"] = "hyperspace"
        self.nav_context["destination"] = "Alpha Centauri"
        particle = RadioResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=self.nav_context,
        )
        examples = particle.get_examples()
        self.assertTrue(any("jump" in ex.lower() for ex in examples))
        self.assertTrue(any("azimuth" in ex.lower() for ex in examples))

    def test_hold_response_chain_leads_to_holding(self):
        """HoldResponse must always be followed by a holding acknowledgment."""
        particle = HoldResponse(
            actor=self.controller, recipient="TEST SHIP", nav_context=self.nav_context
        )
        self.assertEqual(particle.get_next_particle_probabilities(), {"holding": 1.0})

    def test_radio_readback_has_sufficient_examples(self):
        """RadioReadback must provide enough examples for the LLM to draw from."""
        particle = RadioReadback(
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        self.assertGreater(len(particle.get_examples()), 5)

    def test_holding_chain_leads_to_adjusted_response(self):
        """Holding acknowledgment must always be followed by an adjusted controller clearance."""
        particle = Holding(
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        self.assertEqual(
            particle.get_next_particle_probabilities(), {"adjusted_response": 1.0}
        )


class TestParticleSenderCallsign(DialogueParticleTest):
    """Test that get_sender_callsign works correctly for all particle types."""

    def test_pilot_request_sender_callsign(self):
        """Test pilot request uses ship name as sender."""
        particle = LaunchRequest(
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        sender = particle.get_sender_callsign()
        self.assertEqual(sender, "TEST SHIP")

    def test_controller_response_sender_callsign(self):
        """Test controller response uses controller name as sender."""
        particle = RadioResponse(
            actor=self.controller, recipient="TEST SHIP", nav_context=self.nav_context
        )
        sender = particle.get_sender_callsign()
        self.assertEqual(sender, "MARS CONTROL")


class TestParticlePromptBuilding(DialogueParticleTest):
    """Test that particles can build user prompt data correctly."""

    def test_launch_request_builds_prompt_data(self):
        """Test LaunchRequest routes callsigns correctly in prompt data."""
        particle = LaunchRequest(
            actor=self.pilot, recipient="MARS CONTROL", nav_context=self.nav_context
        )
        prompt_data = particle.build_user_prompt_data()
        self.assertEqual(prompt_data.sender, "TEST SHIP")
        self.assertEqual(prompt_data.recipient, "MARS CONTROL")

    def test_radio_response_builds_prompt_data(self):
        """Test RadioResponse routes callsigns correctly in prompt data."""
        particle = RadioResponse(
            actor=self.controller, recipient="TEST SHIP", nav_context=self.nav_context
        )
        prompt_data = particle.build_user_prompt_data()
        self.assertEqual(prompt_data.sender, "MARS CONTROL")
        self.assertEqual(prompt_data.recipient, "TEST SHIP")


class TestSatelliteParticles(DialogueParticleTest):
    """Test satellite-related dialogue particles (NavBroadcast, GratitudeParticle)."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for satellite particles."""
        super().setUpTestData()
        from mysite.universe.models.actor import Satellite

        cls.satellite = Satellite.create(name="Relay Alpha 1")

    def test_nav_broadcast_descriptions_include_satellite_name(self):
        """NavBroadcast role description must identify the satellite by name."""
        nav_context = {"satellite_name": "RELAY ALPHA 1"}
        particle = NavBroadcast(
            actor=self.satellite, recipient="ALL", nav_context=nav_context
        )
        role_desc = particle.get_role_description()
        self.assertIn(self.satellite.name, role_desc)

    def test_nav_broadcast_generate_text(self):
        """Test NavBroadcast generates non-empty text with satellite name."""
        nav_context = {"satellite_name": "RELAY ALPHA 1"}
        particle = NavBroadcast(
            actor=self.satellite, recipient="ALL", nav_context=nav_context
        )
        broadcast_text = particle.generate_nav_broadcast_text()

        # Test that text is generated and has reasonable structure
        self.assertIsInstance(broadcast_text, str)
        self.assertGreater(
            len(broadcast_text), 50, "Broadcast text should have substantial content"
        )
        # Important behavior: should include satellite name
        self.assertIn(
            self.satellite.name.upper(),
            broadcast_text,
            "Text should include satellite name",
        )

    def test_nav_broadcast_next_particle_probabilities(self):
        """Test NavBroadcast has 5% chance of generating gratitude."""
        nav_context = {"satellite_name": "RELAY ALPHA 1"}
        particle = NavBroadcast(
            actor=self.satellite, recipient="ALL", nav_context=nav_context
        )

        # Test multiple times to verify probability distribution
        gratitude_count = 0
        standalone_count = 0
        iterations = 1000

        for _ in range(iterations):
            probs = particle.get_next_particle_probabilities()
            if "gratitude" in probs:
                gratitude_count += 1
                self.assertEqual(probs["gratitude"], 1.0)
            else:
                standalone_count += 1
                self.assertEqual(probs, {})

        # Should be approximately 5% (allow 2-8% range for randomness)
        gratitude_rate = gratitude_count / iterations
        self.assertGreater(
            gratitude_rate, 0.02, "Should have at least 2% gratitude rate"
        )
        self.assertLess(gratitude_rate, 0.08, "Should have at most 8% gratitude rate")

    def test_gratitude_particle_role_identifies_pilot(self):
        """GratitudeParticle role description must identify the pilot, not the ship."""
        nav_context = {
            "satellite_name": "RELAY ALPHA 1",
            "previous_broadcast": "RELAY ALPHA 1 NAV UPDATE // ...",
        }
        particle = GratitudeParticle(
            actor=self.pilot, recipient="RELAY ALPHA 1", nav_context=nav_context
        )
        role_desc = particle.get_role_description()
        self.assertIn(self.pilot.name, role_desc)

    def test_gratitude_particle_examples_exist_and_have_no_callsigns(self):
        """Test GratitudeParticle examples exist and do not include callsigns."""
        nav_context = {
            "satellite_name": "RELAY ALPHA 1",
            "previous_broadcast": "RELAY ALPHA 1 NAV UPDATE // ...",
        }
        particle = GratitudeParticle(
            actor=self.pilot, recipient="RELAY ALPHA 1", nav_context=nav_context
        )
        examples = particle.get_examples()

        self.assertGreater(len(examples), 0, "Should have at least one example")
        # Important behavior: examples should NOT include callsigns
        for example in examples:
            self.assertIsInstance(example, str)
            self.assertGreater(len(example), 0, "Each example should be non-empty")
            self.assertNotIn(
                "TEST SHIP", example, "Examples should not include ship callsigns"
            )
            self.assertNotIn(
                "RELAY ALPHA 1",
                example,
                "Examples should not include recipient callsigns",
            )

    def test_gratitude_particle_ends_chain(self):
        """Test GratitudeParticle ends the chain (no follow-up particles)."""
        nav_context = {
            "satellite_name": "RELAY ALPHA 1",
            "previous_broadcast": "RELAY ALPHA 1 NAV UPDATE // ...",
        }
        particle = GratitudeParticle(
            actor=self.pilot, recipient="RELAY ALPHA 1", nav_context=nav_context
        )
        probs = particle.get_next_particle_probabilities()
        self.assertEqual(probs, {}, "Gratitude should end the chain")

    def test_gratitude_particle_builds_prompt_data(self):
        """Test GratitudeParticle can build UserPromptData."""
        nav_context = {
            "satellite_name": "RELAY ALPHA 1",
            "previous_broadcast": "RELAY ALPHA 1 NAV UPDATE // POS 45.2 -120.3 ALT 850KM // STATUS NOM // TEMP +25C PWR 95% // TIMESTAMP 12345",
        }
        particle = GratitudeParticle(
            actor=self.pilot, recipient="RELAY ALPHA 1", nav_context=nav_context
        )
        prompt_data = particle.build_user_prompt_data(
            previous_dialogue=nav_context["previous_broadcast"]
        )

        # Previous dialogue must be preserved so the LLM can reference it
        self.assertEqual(
            prompt_data.last_dialogue_line, nav_context["previous_broadcast"]
        )


class TestSemanticInvariants(DialogueParticleTest):
    """
    Semantic invariant tests for particle example quality.

    These tests check that examples are operationally correct, not just
    non-empty. The goal is to catch cases where examples invent irrelevant
    units, grant clearance from the wrong speaker, or otherwise produce
    plausible-but-wrong dialogue.
    """

    def test_departure_readback_never_invents_kilometers(self):
        """Readback for sublight/transfer maneuvers must not include 'kilometers'.

        Departure readbacks should echo azimuth only.  Inventing altitude values
        confuses the LLM into producing numerically nonsensical readbacks.
        """
        for maneuver in ("sublight", "transfer", "hyperspace"):
            self.nav_context["maneuver_type"] = maneuver
            particle = RadioReadback(
                actor=self.pilot,
                recipient="MARS CONTROL",
                nav_context=self.nav_context,
            )
            examples = particle.get_examples()
            for ex in examples:
                self.assertNotIn(
                    "kilometer",
                    ex.lower(),
                    f"{maneuver} readback should not invent km: {ex!r}",
                )

    def test_hyperspace_readback_uses_jump_not_burn(self):
        """Hyperspace readback must say 'jump', not 'burn'."""
        self.nav_context["maneuver_type"] = "hyperspace"
        particle = RadioReadback(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context,
        )
        examples = particle.get_examples()
        for ex in examples:
            self.assertNotIn(
                "burn", ex.lower(), f"Hyperspace readback should not say 'burn': {ex!r}"
            )
        self.assertTrue(any("jump" in ex.lower() for ex in examples))

    def test_sublight_readback_uses_burn_not_jump(self):
        """Sublight readback must say 'burn', not 'jump'."""
        self.nav_context["maneuver_type"] = "sublight"
        particle = RadioReadback(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context,
        )
        examples = particle.get_examples()
        for ex in examples:
            self.assertNotIn(
                "jump", ex.lower(), f"Sublight readback should not say 'jump': {ex!r}"
            )
        self.assertTrue(any("burn" in ex.lower() for ex in examples))

    def test_orbital_readback_echoes_instructed_km_when_given(self):
        """Readback for insertion uses the km value extracted from previous dialogue."""
        self.nav_context["maneuver_type"] = "insertion"
        particle = RadioReadback(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context,
        )
        # Simulate controller having said "Cleared for insertion to 350 kilometers"
        particle.previous_dialogue = (
            "Cleared for insertion to 350 kilometers, 28 degrees inclination."
        )
        examples = particle.get_examples()
        # At least some examples should echo back "350"
        self.assertTrue(
            any("350" in ex for ex in examples),
            f"Readback should echo 350 km from previous dialogue. Got: {examples}",
        )

    def test_pilot_request_examples_never_grant_own_clearance(self):
        """Pilot request examples must not use definitive clearance-granting language.

        Pilots ASK for permission; they do NOT grant it to themselves.
        These specific phrases indicate a pilot issuing a clearance (wrong role).
        """
        # Exact phrases that only controllers say, never pilots in request examples
        grant_phrases = [
            "clearance granted",
            "you are go",
            "cleared for launch",
            "cleared for insertion",
            "cleared for sublight",
            "launch is approved",
            "burn is approved",
        ]
        for maneuver in ("launch", "insertion", "sublight"):
            self.nav_context["maneuver_type"] = maneuver
            particle_cls = {
                "launch": LaunchRequest,
                "insertion": InsertionRequest,
                "sublight": SublightRequest,
            }[maneuver]
            particle = particle_cls(
                actor=self.pilot,
                recipient="MARS CONTROL",
                nav_context=self.nav_context,
            )
            examples = particle.get_examples()
            for ex in examples:
                for phrase in grant_phrases:
                    self.assertNotIn(
                        phrase,
                        ex.lower(),
                        f"{maneuver} request example grants own clearance with '{phrase}': {ex!r}",
                    )

    def test_orbital_readback_does_not_invent_azimuth(self):
        """Readback for orbital maneuvers (CIRCULARIZE, INSERTION) must not invent azimuth.

        Azimuth is a departure concept. Echoing it in an orbital readback would
        confuse the LLM into producing geometrically nonsensical confirmations.
        """
        for maneuver in ("circularize", "insertion"):
            self.nav_context["maneuver_type"] = maneuver
            particle = RadioReadback(
                actor=self.pilot,
                recipient="MARS CONTROL",
                nav_context=self.nav_context,
            )
            examples = particle.get_examples()
            for ex in examples:
                self.assertNotIn(
                    "azimuth",
                    ex.lower(),
                    f"{maneuver} readback should not invent azimuth: {ex!r}",
                )

    def test_transfer_readback_does_not_invent_altitude(self):
        """Readback for TRANSFER must not contain altitude km values.

        A Hohmann transfer is characterised by origin/destination orbits, not
        a specific altitude target. Inventing a km value in the readback
        would contradict the controller's actual clearance wording.
        """
        self.nav_context["maneuver_type"] = "transfer"
        particle = RadioReadback(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context,
        )
        examples = particle.get_examples()
        for ex in examples:
            self.assertNotIn(
                "kilometer",
                ex.lower(),
                f"TRANSFER readback should not invent altitude km: {ex!r}",
            )


class TestControllerResponseSemantics(TestCase):
    """
    Semantic correctness tests for RadioResponse.get_examples().

    When a controller has a valid celestial location, the physics service
    generates real orbital parameters.  These tests verify that the examples
    include concrete numbers (altitudes, azimuths, inclinations) rather than
    collapsing to generic filler like "proceed when ready."

    Tests also verify that maneuver-specific vocabulary is used correctly
    (jump vs. burn, azimuth for departures, km for orbital maneuvers).
    """

    @classmethod
    def setUpTestData(cls):
        from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet
        from mysite.universe.models.station import Station
        from mysite.universe.models.scale import Scale

        galaxy = Galaxy.objects.create(
            name="Semantic Test Galaxy", galaxy_type="SP", galaxy_size="M"
        )
        system = StarSystem.objects.create(
            name="Semantic Test System",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(
            name="Semantic Test Star", orbits=system, star_type="G"
        )
        cls.planet = Planet.objects.create(
            name="Semantic Test World",
            scale=Scale.PLANET,
            orbital_distance_au=1.0,
            orbital_period_days=365.25,
            mass_kg=5.972e24,
            radius_km=6371.0,
            axial_tilt_deg=23.4,
            orbital_inclination_deg=0.0,
            orbits=star,
            planet_type="TE",
        )
        cls.station = Station.objects.create(
            name="Semantic Test Station",
            scale=Scale.STATION,
            orbits=cls.planet,
            large_berths=2,
        )
        cls.controller = Controller.create(location=cls.station)
        cls.controller.name = "Semantic Control"
        cls.controller.save()

    def _make_response(self, maneuver_type, **extra_ctx):
        nav_context = {
            "maneuver_type": maneuver_type,
            "current_location": self.planet.name,
            "origin": self.planet.name,
            "destination": "Target World",
        }
        nav_context.update(extra_ctx)
        return RadioResponse(
            actor=self.controller,
            recipient="TEST SHIP",
            nav_context=nav_context,
        )

    def test_launch_examples_include_numeric_altitude(self):
        """LAUNCH with physics params must produce at least one example with a km altitude."""
        import re

        examples = self._make_response("LAUNCH").get_examples()
        has_numeric_km = any(
            re.search(r"\d+\s*kilometers?", ex, re.IGNORECASE) for ex in examples
        )
        self.assertTrue(
            has_numeric_km,
            "LAUNCH examples with physics should include a numeric km altitude.\n"
            + "\n".join(examples),
        )

    def test_launch_examples_include_azimuth(self):
        """LAUNCH with physics params must include at least one azimuth reference."""
        examples = self._make_response("LAUNCH").get_examples()
        self.assertTrue(
            any("azimuth" in ex.lower() for ex in examples),
            "LAUNCH examples with physics should include azimuth.\n"
            + "\n".join(examples),
        )

    def test_sublight_examples_all_include_numeric_azimuth(self):
        """Every SUBLIGHT example must include 'azimuth' followed by a number."""
        import re

        examples = self._make_response("sublight").get_examples()
        for ex in examples:
            self.assertIn(
                "azimuth",
                ex.lower(),
                f"Sublight example missing 'azimuth': {ex!r}",
            )
            self.assertIsNotNone(
                re.search(r"azimuth\s+\d+", ex.lower()),
                f"Sublight azimuth should be followed by a number: {ex!r}",
            )

    def test_hyperspace_clearance_uses_jump_not_burn(self):
        """HYPERSPACE clearance must say 'jump', not 'burn'."""
        examples = self._make_response("hyperspace").get_examples()
        for ex in examples:
            self.assertNotIn(
                "burn",
                ex.lower(),
                f"Hyperspace clearance should not say 'burn': {ex!r}",
            )
        self.assertTrue(
            any("jump" in ex.lower() for ex in examples),
            "Hyperspace clearance should contain 'jump'.\n" + "\n".join(examples),
        )

    def test_insertion_examples_include_altitude_and_inclination(self):
        """INSERTION examples with physics must include both altitude and inclination."""
        import re

        examples = self._make_response(
            "insertion", destination=self.planet.name
        ).get_examples()
        has_km = any(
            re.search(r"\d+\s*kilometers?", ex, re.IGNORECASE) for ex in examples
        )
        has_deg = any(
            re.search(r"\d+\s*degrees?", ex, re.IGNORECASE) for ex in examples
        )
        self.assertTrue(
            has_km,
            "INSERTION examples should include altitude.\n" + "\n".join(examples),
        )
        self.assertTrue(
            has_deg,
            "INSERTION examples should include inclination.\n" + "\n".join(examples),
        )

    def test_controller_without_actor_falls_back_gracefully(self):
        """RadioResponse with no actor returns non-empty examples without crashing."""
        particle = RadioResponse(
            actor=None,
            recipient="TEST SHIP",
            nav_context={"maneuver_type": "LAUNCH", "current_location": "Unknown"},
        )
        examples = particle.get_examples()
        self.assertGreater(len(examples), 0, "Fallback examples must not be empty")

    def test_sublight_examples_do_not_contain_kilometers(self):
        """
        Sublight clearances are azimuth-based departures; they must not invent
        altitude values.  Only orbital maneuvers give altitude instructions.
        """
        examples = self._make_response("sublight").get_examples()
        for ex in examples:
            self.assertNotIn(
                "kilometer",
                ex.lower(),
                f"Sublight clearance should not mention km altitude: {ex!r}",
            )


class TestParseInstructedValues(DialogueParticleTest):
    """
    Tests for DialogueParticle.parse_instructed_values().

    This method extracts km and degree values from the controller's
    previous dialogue line so readbacks can echo the exact values given.
    """

    def _make_particle(self):
        """Return a simple particle instance for calling parse_instructed_values."""
        return LaunchRequest(
            actor=self.pilot,
            recipient="MARS CONTROL",
            nav_context=self.nav_context,
        )

    def test_extracts_kilometers_from_text(self):
        particle = self._make_particle()
        result = particle.parse_instructed_values(
            "Cleared for launch to 350 kilometers apogee."
        )
        self.assertEqual(result["instructed_km"], 350)
        self.assertIsNone(result["instructed_deg"])

    def test_extracts_degrees_from_text(self):
        particle = self._make_particle()
        result = particle.parse_instructed_values(
            "Adjust your inclination to 28 degrees."
        )
        self.assertIsNone(result["instructed_km"])
        self.assertEqual(result["instructed_deg"], 28)

    def test_extracts_both_km_and_degrees(self):
        particle = self._make_particle()
        result = particle.parse_instructed_values(
            "Cleared for insertion to 250 kilometers, 30 degrees inclination."
        )
        self.assertEqual(result["instructed_km"], 250)
        self.assertEqual(result["instructed_deg"], 30)

    def test_handles_comma_separated_thousands(self):
        particle = self._make_particle()
        result = particle.parse_instructed_values("Target apogee 1,200 kilometers.")
        self.assertEqual(result["instructed_km"], 1200)

    def test_uses_previous_dialogue_when_no_text_arg(self):
        particle = self._make_particle()
        particle.previous_dialogue = "Go to 180 kilometers, 45 degrees."
        result = particle.parse_instructed_values()
        self.assertEqual(result["instructed_km"], 180)
        self.assertEqual(result["instructed_deg"], 45)

    def test_returns_none_when_no_match(self):
        particle = self._make_particle()
        result = particle.parse_instructed_values("Proceed when ready.")
        self.assertIsNone(result["instructed_km"])
        self.assertIsNone(result["instructed_deg"])

    def test_returns_none_for_none_input(self):
        particle = self._make_particle()
        result = particle.parse_instructed_values(None)
        self.assertIsNone(result["instructed_km"])
        self.assertIsNone(result["instructed_deg"])

    def test_km_abbreviation_also_works(self):
        particle = self._make_particle()
        result = particle.parse_instructed_values("Fly to 400km orbit.")
        self.assertEqual(result["instructed_km"], 400)
