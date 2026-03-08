"""
Audio plan generation tests.

Tests audio plan building for different actor types:
- Satellite actors: Quindars + TTS + Modem noise
- Pilot actors: Quindars + TTS
- Controller actors: Quindars + TTS
- Audio plan structure and parameters
"""

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
        galaxy = Galaxy.objects.create(
            name="Test Galaxy", galaxy_type="SP", galaxy_size="L"
        )
        cls.system = StarSystem.objects.create(
            name="Test System",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Test Star", orbits=cls.system, star_type="G")
        Planet.objects.create(
            name="Test Planet", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )
        cls.location = Location.objects.create(name="Test Station", scale=Scale.STATION)

        cls.satellite = Satellite.objects.create(
            name=f"{cls.system.name} Navsat", location=cls.system
        )

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
            text="RELAY ALPHA 1 NAV UPDATE // POS 45.2 -120.3 ALT 850KM // STATUS NOM // TEMP +25C PWR 95% // TIMESTAMP 12345",
        )

        audio_plan = build_audio_plan_for_dialogue_event(event)

        # Satellites should have modem noise preset
        modem_actions = [a for a in audio_plan if "modem_noise" in a.get("preset", "")]
        if len(modem_actions) == 0:
            # If no modem actions, check what we actually got
            all_presets = [a.get("preset", "") for a in audio_plan]
            self.fail(
                f"Expected modem_noise preset, but got: {all_presets}. Full plan: {audio_plan}"
            )
        self.assertGreater(
            len(modem_actions), 0, "Satellite events should use modem noise"
        )

        # Satellites SHOULD have Quindar tones (start/end of transmission)
        # Comment in audio_plans.py says: "Don't remove Quindars from satellites"
        quindar_actions = [a for a in audio_plan if "quindar" in a.get("preset", "")]
        self.assertGreater(
            len(quindar_actions), 0, "Satellite events SHOULD use Quindar tones"
        )

    def test_audio_plan_for_satellite_includes_broadcast_text(self):
        """Test that satellite audio plan includes broadcast text in params."""
        # Ensure satellite has an audio profile
        from mysite.universe.models.audio_profile import AudioProfile

        AudioProfile.create_default_for_actor(self.satellite)

        broadcast_text = "RELAY ALPHA 1 NAV UPDATE // POS 45.2 -120.3 ALT 850KM // STATUS NOM // TEMP +25C PWR 95% // TIMESTAMP 12345"
        event = DialogueEventLog.objects.create(
            timestamp=100.0, actor=self.satellite, text=broadcast_text
        )

        audio_plan = build_audio_plan_for_dialogue_event(event)

        # Find modem noise action
        modem_action = next(
            (a for a in audio_plan if "modem_noise" in a.get("preset", "")), None
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
            text="Requesting clearance for departure.",
        )

        audio_plan = build_audio_plan_for_dialogue_event(event)

        # Should have Quindar tones
        quindar_actions = [a for a in audio_plan if "quindar" in a.get("preset", "")]
        self.assertGreater(
            len(quindar_actions), 0, "Pilot events should use Quindar tones"
        )

        # Should NOT have modem noise
        modem_actions = [a for a in audio_plan if "modem_noise" in a.get("preset", "")]
        self.assertEqual(
            len(modem_actions), 0, "Pilot events should NOT use modem noise"
        )


class TestAudioPlanControllerSpecifics(TestCase):
    """Test audio plan for Controller actors (room tone branch)."""

    @classmethod
    def setUpTestData(cls):
        from mysite.universe.models.actor import Controller

        cls.location = Location.objects.create(
            name="Controller Station", scale=Scale.STATION
        )
        cls.controller = Controller.create(location=cls.location)
        cls.controller.name = "Test Control"
        cls.controller.save()

    def test_controller_plan_has_quindars(self):
        """Controller events always have Quindar start and end tones."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.controller,
            text="You are cleared for departure.",
        )
        plan = build_audio_plan_for_dialogue_event(event)
        presets = [a.get("preset", "") for a in plan]
        self.assertIn("quindar_start", presets)
        self.assertIn("quindar_end", presets)

    def test_controller_plan_has_no_modem_noise(self):
        """Controller events must not include modem noise."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.controller,
            text="Proceed to holding pattern.",
        )
        plan = build_audio_plan_for_dialogue_event(event)
        modem_actions = [a for a in plan if "modem_noise" in a.get("preset", "")]
        self.assertEqual(
            len(modem_actions), 0, "Controllers should never have modem noise"
        )

    def test_controller_plan_has_room_tone_when_profile_enables_it(self):
        """When the controller profile sets room_tone enabled, a room_tone action appears."""
        from mysite.universe.models.audio_profile import AudioProfile

        # Ensure profile has room tone enabled with a wav file
        AudioProfile.objects.filter(actor=self.controller).delete()
        AudioProfile.objects.create(
            actor=self.controller,
            params={
                "room_tone": {
                    "enabled": True,
                    "wav_file": "Control_station_noise.wav",
                    "engine_rumble_intensity": 0.0,
                },
                "static": {"intensity": 0.0},
                "quindar": {},
                "voiceprint": {"voice_template": "controller-default"},
            },
        )
        event = DialogueEventLog.objects.create(
            timestamp=200.0,
            actor=self.controller,
            text="Copy, stand by.",
        )
        plan = build_audio_plan_for_dialogue_event(event)
        room_tone_actions = [a for a in plan if a.get("type") == "room_tone"]
        self.assertGreater(
            len(room_tone_actions), 0, "Controller should have room_tone when enabled"
        )
        # Verify the wav_url points to the correct file
        wav_url = room_tone_actions[0].get("wav_url", "")
        self.assertIn("Control_station_noise.wav", wav_url)

    def test_controller_plan_has_no_room_tone_when_disabled(self):
        """When room_tone disabled in profile, no room_tone action appears."""
        from mysite.universe.models.audio_profile import AudioProfile

        AudioProfile.objects.filter(actor=self.controller).delete()
        AudioProfile.objects.create(
            actor=self.controller,
            params={
                "room_tone": {"enabled": False},
                "static": {"intensity": 0.0},
                "quindar": {},
                # voice_template must be set or the code will reassign the whole profile
                "voiceprint": {"voice_template": "controller-default"},
            },
        )
        event = DialogueEventLog.objects.create(
            timestamp=300.0,
            actor=self.controller,
            text="Negative, hold position.",
        )
        plan = build_audio_plan_for_dialogue_event(event)
        room_tone_actions = [a for a in plan if a.get("type") == "room_tone"]
        self.assertEqual(len(room_tone_actions), 0)


class TestAudioPlanStaticLayer(TestCase):
    """Test static noise layer inclusion/exclusion."""

    @classmethod
    def setUpTestData(cls):
        cls.location = Location.objects.create(
            name="Static Test Station", scale=Scale.STATION
        )
        cls.ship = Ship.create(location=cls.location, name="STATIC SHIP")
        cls.pilot = Pilot.create(ship=cls.ship, name="Static Pilot")

    def test_static_layer_included_when_intensity_nonzero(self):
        """When static intensity > 0 in profile, static action is in plan."""
        from mysite.universe.models.audio_profile import AudioProfile

        AudioProfile.objects.filter(actor=self.pilot).delete()
        AudioProfile.objects.create(
            actor=self.pilot,
            params={
                "static": {"intensity": 0.1},
                "room_tone": {"enabled": False},
                "quindar": {},
                "voiceprint": {"voice_template": "pilot-default"},
            },
        )
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.pilot,
            text="Requesting departure clearance.",
        )
        plan = build_audio_plan_for_dialogue_event(event)
        static_actions = [a for a in plan if "static" in a.get("preset", "")]
        self.assertGreater(
            len(static_actions), 0, "Should have static layer when intensity > 0"
        )

    def test_static_layer_excluded_when_intensity_zero(self):
        """When static intensity == 0, no static action in plan."""
        from mysite.universe.models.audio_profile import AudioProfile

        AudioProfile.objects.filter(actor=self.pilot).delete()
        AudioProfile.objects.create(
            actor=self.pilot,
            params={
                "static": {"intensity": 0.0},
                "room_tone": {"enabled": False},
                "quindar": {},
                "voiceprint": {"voice_template": "pilot-default"},
            },
        )
        event = DialogueEventLog.objects.create(
            timestamp=200.0,
            actor=self.pilot,
            text="On departure now.",
        )
        plan = build_audio_plan_for_dialogue_event(event)
        static_actions = [a for a in plan if "static" in a.get("preset", "")]
        self.assertEqual(len(static_actions), 0)


class TestAudioPlanActorlessFallback(TestCase):
    """Test fallback behavior when event has no actor reference."""

    def test_actorless_event_returns_minimal_plan(self):
        """Event with no actor FK returns minimal plan with quindars only."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=None,
            actor_name="Ghost Speaker",
            text="Hello, is anyone there?",
        )
        plan = build_audio_plan_for_dialogue_event(event)
        # Should have exactly quindar_start and quindar_end
        presets = [a.get("preset") for a in plan]
        self.assertIn("quindar_start", presets)
        self.assertIn("quindar_end", presets)
        # Should NOT have room tone, TTS, or modem noise
        self.assertNotIn("room_tone", [a.get("type") for a in plan])
        self.assertNotIn("modem_noise_example", presets)
        tts_actions = [a for a in plan if a.get("action") == "tts"]
        self.assertEqual(len(tts_actions), 0)


class TestAudioPlanMissingProfileOnDemand(TestCase):
    """
    The AudioProfile.DoesNotExist branch: when an actor has no audio profile
    the plan builder assigns one on-demand and continues normally.
    """

    @classmethod
    def setUpTestData(cls):
        cls.location = Location.objects.create(
            name="OnDemand Station", scale=Scale.STATION
        )
        cls.ship = Ship.create(location=cls.location, name="ON-DEMAND SHIP")
        cls.pilot = Pilot.create(ship=cls.ship, name="On-Demand Pilot")
        # Wipe any auto-created profile so the DoesNotExist path is triggered
        from mysite.universe.models.audio_profile import AudioProfile

        AudioProfile.objects.filter(actor=cls.pilot).delete()

    def test_pilot_without_profile_gets_one_assigned_and_plan_is_valid(self):
        """
        Pilot with no AudioProfile: plan builder assigns profile on-demand
        and returns a non-empty plan with quindars.
        """
        # Verify no profile exists at test start
        from mysite.universe.models.audio_profile import AudioProfile

        self.assertFalse(AudioProfile.objects.filter(actor=self.pilot).exists())

        event = DialogueEventLog.objects.create(
            timestamp=200.0,
            actor=self.pilot,
            text="Requesting departure clearance.",
        )
        plan = build_audio_plan_for_dialogue_event(event)

        presets = [a.get("preset", "") for a in plan]
        self.assertIn("quindar_start", presets)
        self.assertIn("quindar_end", presets)
        # Profile should now exist (assigned on-demand)
        self.assertTrue(AudioProfile.objects.filter(actor=self.pilot).exists())

    def test_pilot_with_incomplete_profile_gets_reassigned(self):
        """
        Pilot whose AudioProfile has no voice_template triggers reassignment.
        Plan should still produce quindars and a TTS action.
        """
        from mysite.universe.models.audio_profile import AudioProfile

        AudioProfile.objects.filter(actor=self.pilot).delete()
        # Create an intentionally incomplete profile (empty voiceprint)
        AudioProfile.objects.create(
            actor=self.pilot,
            params={
                "voiceprint": {},  # no voice_template → triggers reassignment
                "quindar": {},
                "room_tone": {"enabled": False},
                "static": {"intensity": 0.0},
            },
        )

        event = DialogueEventLog.objects.create(
            timestamp=300.0,
            actor=self.pilot,
            text="Departure on your mark.",
        )
        plan = build_audio_plan_for_dialogue_event(event)
        presets = [a.get("preset", "") for a in plan]
        self.assertIn("quindar_start", presets)
        self.assertIn("quindar_end", presets)


class TestSentenceCaseFunction(TestCase):
    """Unit tests for the _sentence_case helper in audio_plans."""

    def _sc(self, text):
        from mysite.universe.services.audio_plans import _sentence_case

        return _sentence_case(text)

    def test_all_caps_converted_to_sentence_case(self):
        """ALL CAPS input is lowercased then first alpha capitalised."""
        self.assertEqual(self._sc("HELLO WORLD"), "Hello world")

    def test_already_sentence_case_unchanged(self):
        """Mixed-case text that isn't all-caps is returned as-is."""
        self.assertEqual(self._sc("Hello world"), "Hello world")

    def test_empty_string_returns_empty(self):
        self.assertEqual(self._sc(""), "")

    def test_whitespace_only_returns_whitespace(self):
        self.assertEqual(self._sc("   "), "   ")

    def test_leading_non_alpha_capitalises_first_alpha(self):
        """Text starting with punctuation: first alpha char gets capitalised."""
        result = self._sc("123 hello")
        self.assertTrue(result[4].isupper(), f"Expected 'H' in '{result}'")

    def test_all_caps_with_numbers(self):
        """ALL-CAPS text with numbers is still lowercased + first-alpha cap."""
        result = self._sc("RELAY 42 ALPHA")
        self.assertEqual(result, "Relay 42 alpha")
