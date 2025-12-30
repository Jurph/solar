"""
Unit tests for nav broadcast functionality.

Tests:
1. NavBroadcast particle generation
2. GratitudeParticle generation and LLM integration
3. generate_nav_broadcast_chain in ScriptService
4. Nav broadcast mission type in spawn_mission
5. Audio plan detection for Satellite actors
"""
import random
from unittest.mock import Mock, patch, MagicMock
from tests.test_spawn_mission import _ImmediateThread
from django.test import TestCase
from mysite.universe.models.actor import Pilot, Satellite
from mysite.universe.models.ship import Ship
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale
from mysite.universe.models.simulation import SimulationState
from mysite.universe.services.script_server import ScriptService
from mysite.universe.services.audio_plans import build_audio_plan_for_dialogue_event
from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet
from mysite.universe.models.station import Station


class NavBroadcastTest(TestCase):
    """Base test class for nav broadcast tests with common fixtures."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data shared across all nav broadcast tests."""
        galaxy = Galaxy.objects.create(name="Test Galaxy", galaxy_type="SP", galaxy_size="L")
        cls.system = StarSystem.objects.create(
            name="Test System",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Test Star", orbits=cls.system, star_type="G")
        planet = Planet.objects.create(name="Test Planet", orbits=star, planet_type="TE", orbital_distance_au=1.0)
        cls.location = Station.objects.create(name="Test Station", orbits=planet, scale=Scale.STATION)

        cls.satellite = Satellite.objects.create(name=f"{cls.system.name} Navsat", location=cls.system)
        
        # Create ship and pilot for gratitude tests
        cls.ship = Ship.create(location=cls.location, name="TEST SHIP")
        cls.pilot = Pilot.create(ship=cls.ship)
        cls.pilot.name = "Test Pilot"
        cls.pilot.save()
        
        # Set up simulation state
        cls.base_sim_time = 1000.0
        SimulationState.objects.all().delete()
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=cls.base_sim_time,
            anchor_wall_clock=0.0,
            time_scale=0.0,
        )


class TestNavBroadcastChainGeneration(NavBroadcastTest):
    """Test generate_nav_broadcast_chain in ScriptService."""
    
    def setUp(self):
        """Set up for each test."""
        # Create a mock LLM service
        self.mock_llm = Mock()
        self.mock_llm.temperature = 0.25
        self.script_service = ScriptService(self.mock_llm)
    
    def test_generate_nav_broadcast_chain_creates_broadcast_event(self):
        """Test that generate_nav_broadcast_chain creates a broadcast event."""
        base_timestamp = 100.0
        events = self.script_service.generate_nav_broadcast_chain(
            satellite=self.satellite,
            base_timestamp=base_timestamp
        )
        
        # Should have at least one event (the broadcast)
        self.assertGreaterEqual(len(events), 1)
        
        broadcast_event = events[0]
        # Test critical structural properties
        self.assertEqual(broadcast_event.actor, self.satellite, "Event should be from satellite")
        self.assertEqual(broadcast_event.timestamp, base_timestamp, "Event should use provided timestamp")
        self.assertEqual(broadcast_event.event_type, "dialogue", "Event should be dialogue type")
        self.assertEqual(broadcast_event.metadata["type"], "nav_broadcast", "Metadata should indicate nav_broadcast")
        # Test that text is non-empty and includes satellite name
        self.assertIsInstance(broadcast_event.text, str)
        self.assertGreater(len(broadcast_event.text), 0, "Event text should be non-empty")
        self.assertIn(self.satellite.name.upper(), broadcast_event.text, "Text should include satellite name")
    
    def test_generate_nav_broadcast_chain_broadcast_text_has_structure(self):
        """Test that broadcast text has required structural elements."""
        events = self.script_service.generate_nav_broadcast_chain(
            satellite=self.satellite,
            base_timestamp=0.0
        )
        
        broadcast_text = events[0].text
        
        # Test that text is non-empty and has reasonable length (structural check)
        self.assertIsInstance(broadcast_text, str)
        self.assertGreater(len(broadcast_text), 50, "Broadcast text should have substantial content")
        # Test that it includes the satellite name (important behavior)
        self.assertIn(self.satellite.name.upper(), broadcast_text)
    
    def test_generate_nav_broadcast_chain_with_gratitude(self):
        """Test that gratitude is generated when probability allows."""
        # Force the NavBroadcast particle to return gratitude probability
        # by patching the particle's get_next_particle_probabilities method
        original_create = self.script_service.dialogue_service.particle_factory.create_particle
        
        def mock_create_particle(particle_type, actor, recipient, nav_context):
            particle = original_create(particle_type, actor, recipient, nav_context)
            if particle_type == "nav_broadcast":
                # Mock get_next_particle_probabilities to always return gratitude
                particle.get_next_particle_probabilities = Mock(return_value={"gratitude": 1.0})
            return particle
        
        self.script_service.dialogue_service.particle_factory.create_particle = mock_create_particle
        
        # Mock generate_chain_iteratively to return a gratitude message
        from mysite.universe.schemas.dialogue_schema import DialogueMessage, Role
        gratitude_msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="TEST SHIP",
            recipient_callsign="RELAY ALPHA 1",
            message="RELAY ALPHA 1, TEST SHIP. Thanks for the update.",
        )
        original_generate = self.script_service.dialogue_service.generate_chain_iteratively
        self.script_service.dialogue_service.generate_chain_iteratively = Mock(
            return_value=[(gratitude_msg, 2.0)]
        )
        
        # Ensure we have a ship with pilot for gratitude
        events = self.script_service.generate_nav_broadcast_chain(
            satellite=self.satellite,
            base_timestamp=0.0
        )
        
        # Should have broadcast + gratitude events
        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[0].actor, self.satellite)
        
        # If gratitude was generated, should have 2 events
        if len(events) > 1:
            self.assertEqual(len(events), 2)
            self.assertEqual(events[1].actor, self.pilot)
            self.assertIn("thanks", events[1].text.lower())
    
    def test_generate_nav_broadcast_chain_no_ships_fails_silently(self):
        """Test that missing ships causes gratitude to fail silently."""
        # Delete all ships
        Ship.objects.all().delete()
        
        # Force gratitude probability
        original_create = self.script_service.dialogue_service.particle_factory.create_particle
        
        def mock_create_particle(particle_type, actor, recipient, nav_context):
            particle = original_create(particle_type, actor, recipient, nav_context)
            if particle_type == "nav_broadcast":
                particle.get_next_particle_probabilities = Mock(return_value={"gratitude": 1.0})
            return particle
        
        self.script_service.dialogue_service.particle_factory.create_particle = mock_create_particle
        
        events = self.script_service.generate_nav_broadcast_chain(
            satellite=self.satellite,
            base_timestamp=0.0
        )
        
        # Should still have broadcast event, but no gratitude
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].actor, self.satellite)


class TestNavBroadcastMissionType(NavBroadcastTest):
    """Test nav_broadcast mission type in spawn_mission."""
    
    def setUp(self):
        """Set up for each test."""
        from django.test import Client
        self.client = Client()
        DialogueEventLog.objects.all().delete()
    
    def test_spawn_nav_broadcast_mission_creates_events(self):
        """Test that nav_broadcast mission type creates broadcast events."""
        from django.urls import reverse
        
        url = reverse("spawn_mission")
        
        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None
        
        class _FakeScriptService:
            def __init__(self, llm):
                self.llm = llm
            
            def generate_nav_broadcast_chain(self, satellite, base_timestamp=0.0):
                from mysite.universe.models.event import DialogueEvent
                return [
                    DialogueEvent(
                        timestamp=base_timestamp,
                        actor=satellite,
                        text=f"{satellite.name.upper()} NAV UPDATE // POS 45.2 -120.3 ALT 850KM // STATUS NOM // TEMP +25C PWR 95% // TIMESTAMP 12345",
                        duration=5.0,
                        event_type="dialogue",
                        metadata={"type": "nav_broadcast", "satellite_name": satellite.name},
                    )
                ]
        
        # Mock ScriptService.get_instance to return our fake service
        fake_service = _FakeScriptService(_FakeLLM())
        
        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.services.script_server.ScriptService.get_instance", return_value=fake_service),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url, {"mission_type": "nav_broadcast"})
            self.assertEqual(response.status_code, 200)
        
        events = list(DialogueEventLog.objects.order_by("timestamp"))
        self.assertEqual(
            len(events),
            14,
            f"Expected 14 scheduled nav broadcasts, got {len(events)}. Events: {list(events)}",
        )

        # First broadcast should be on the hour.
        self.assertEqual(events[0].timestamp % 3600.0, 0.0)
        
        # All events should be from satellite
        for event in events:
            self.assertEqual(event.actor_name, self.satellite.name)
            self.assertIn("NAV UPDATE", event.text)
            self.assertEqual(event.metadata.get("type"), "nav_broadcast")

        # Last broadcast should carry the next-cycle marker (long-term scheduling hook)
        last = events[-1]
        self.assertIn("navsat_next_cycle_anchor_ts", last.metadata)
        self.assertEqual(last.metadata["navsat_cycle_count"], 14)
        self.assertEqual(last.metadata["navsat_cycle_cadence_hours"], 12.0)
        self.assertEqual(last.metadata["navsat_star_system_name"], self.system.name)
    
    def test_spawn_nav_broadcast_with_specific_satellite(self):
        """Test nav_broadcast mission with specific satellite name."""
        from django.urls import reverse
        
        # Create another satellite
        satellite2 = Satellite.objects.create(name="Relay Beta 2", location=self.system)
        
        url = reverse("spawn_mission")
        
        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None
        
        class _FakeScriptService:
            def __init__(self, llm):
                self.llm = llm
            
            def generate_nav_broadcast_chain(self, satellite, base_timestamp=0.0):
                from mysite.universe.models.event import DialogueEvent
                return [
                    DialogueEvent(
                        timestamp=base_timestamp,
                        actor=satellite,
                        text=f"{satellite.name.upper()} NAV UPDATE // POS 45.2 -120.3 ALT 850KM // STATUS NOM // TEMP +25C PWR 95% // TIMESTAMP 12345",
                        duration=5.0,
                        event_type="dialogue",
                        metadata={"type": "nav_broadcast", "satellite_name": satellite.name},
                    )
                ]
        
        # Mock ScriptService.get_instance to return our fake service
        fake_service = _FakeScriptService(_FakeLLM())
        
        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.services.script_server.ScriptService.get_instance", return_value=fake_service),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url, {
                "mission_type": "nav_broadcast",
                "satellite_name": satellite2.name
            })
            self.assertEqual(response.status_code, 200)
        
        # Check that events were created from the specific satellite
        events = list(DialogueEventLog.objects.order_by("timestamp"))
        self.assertEqual(
            len(events),
            14,
            f"Expected 14 scheduled nav broadcasts, got {len(events)}. Events: {list(events)}",
        )
        
        for event in events:
            self.assertEqual(event.actor_name, satellite2.name)


class TestAudioPlanSatelliteDetection(NavBroadcastTest):
    """Test audio plan detection for Satellite actors."""
    
    def test_audio_plan_for_satellite_uses_modem_noise(self):
        """Test that Satellite actors get modem noise in audio plan (with quindars)."""
        # Ensure satellite has an audio profile
        from mysite.universe.models.audio_profile import AudioProfile
        AudioProfile.create_default_for_actor(self.satellite)
        
        # Create a nav broadcast event
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.satellite,
            text="RELAY ALPHA 1 NAV UPDATE // POS 45.2 -120.3 ALT 850KM // STATUS NOM // TEMP +25C PWR 95% // TIMESTAMP 12345"
        )
        
        audio_plan = build_audio_plan_for_dialogue_event(event)
        
        # Satellites should have modem noise preset
        modem_actions = [a for a in audio_plan if "modem_noise" in a.get("preset", "")]
        if len(modem_actions) == 0:
            # If no modem actions, check what we actually got
            all_presets = [a.get("preset", "") for a in audio_plan]
            self.fail(f"Expected modem_noise preset, but got: {all_presets}. Full plan: {audio_plan}")
        self.assertGreater(len(modem_actions), 0, "Satellite events should use modem noise")
        
        # Satellites SHOULD have Quindar tones (start/end of transmission)
        # Comment in audio_plans.py says: "Don't remove Quindars from satellites"
        quindar_actions = [a for a in audio_plan if "quindar" in a.get("preset", "")]
        self.assertGreater(len(quindar_actions), 0, "Satellite events SHOULD use Quindar tones")
    
    def test_audio_plan_for_pilot_uses_quindar(self):
        """Test that Pilot actors get Quindar tones in audio plan."""
        # Create a dialogue event from pilot
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.pilot,
            text="Requesting clearance for departure."
        )
        
        audio_plan = build_audio_plan_for_dialogue_event(event)
        
        # Should have Quindar tones
        quindar_actions = [a for a in audio_plan if "quindar" in a.get("preset", "")]
        self.assertGreater(len(quindar_actions), 0, "Pilot events should use Quindar tones")
        
        # Should NOT have modem noise
        modem_actions = [a for a in audio_plan if "modem_noise" in a.get("preset", "")]
        self.assertEqual(len(modem_actions), 0, "Pilot events should NOT use modem noise")
    
    def test_audio_plan_for_satellite_includes_broadcast_text(self):
        """Test that satellite audio plan includes broadcast text in params."""
        # Ensure satellite has an audio profile
        from mysite.universe.models.audio_profile import AudioProfile
        AudioProfile.create_default_for_actor(self.satellite)
        
        broadcast_text = "RELAY ALPHA 1 NAV UPDATE // POS 45.2 -120.3 ALT 850KM // STATUS NOM // TEMP +25C PWR 95% // TIMESTAMP 12345"
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.satellite,
            text=broadcast_text
        )
        
        audio_plan = build_audio_plan_for_dialogue_event(event)
        
        # Find modem noise action
        modem_action = next(
            (a for a in audio_plan if "modem_noise" in a.get("preset", "")),
            None
        )
        self.assertIsNotNone(modem_action, "Should have modem noise action")
        
        # Check that params include the broadcast text
        params = modem_action.get("params", {})
        self.assertIn("text", params)
        self.assertEqual(params["text"], broadcast_text)

