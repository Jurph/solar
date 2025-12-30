"""
Audio plan generation tests.

Tests audio plan building for different actor types:
- Satellite actors: Quindars + TTS + Modem noise
- Pilot actors: Quindars + TTS
- Controller actors: Quindars + TTS
- Audio plan structure and parameters
"""
import pytest
from django.test import TestCase

from mysite.universe.models.actor import Pilot, Satellite
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale
from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet
from mysite.universe.models.ship import Ship
from mysite.universe.services.audio_plans import build_audio_plan_for_dialogue_event


class TestAudioPlanSatelliteSpecifics(TestCase):
    """Test audio plan detection for Satellite actors."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data shared across all tests."""
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
        cls.location = Location.objects.create(name="Test Station", scale=Scale.STATION)

        cls.satellite = Satellite.objects.create(name=f"{cls.system.name} Navsat", location=cls.system)
        
        # Create ship and pilot for comparison tests
        cls.ship = Ship.create(location=cls.location, name="TEST SHIP")
        cls.pilot = Pilot.create(ship=cls.ship)
        cls.pilot.name = "Test Pilot"
        cls.pilot.save()
    
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


class TestAudioPlanPilotSpecifics(TestCase):
    """Test audio plan for Pilot actors."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.location = Location.objects.create(name="Test Station", scale=Scale.STATION)
        cls.ship = Ship.create(location=cls.location, name="TEST SHIP")
        cls.pilot = Pilot.create(ship=cls.ship, name="Test Pilot")
    
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

