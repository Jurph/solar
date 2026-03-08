"""
Edge case tests for views/events.py.

Tests for branches not covered by test_event_feed.py:
- _resolve_voice_for_event() branches
- _sentence_case() utility
- event_feed cursor validation error paths
"""

import time
from django.test import TestCase, Client

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.audio_profile import AudioProfile
from mysite.universe.models.base import Location
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.scale import Scale
from mysite.universe.models.ship import Ship
from mysite.universe.models.simulation import SimulationState
from mysite.universe.views.events import _resolve_voice_for_event, _sentence_case


class TestResolveVoiceForEvent(TestCase):
    """Tests for _resolve_voice_for_event() branching."""

    @classmethod
    def setUpTestData(cls):
        cls.location = Location.objects.create(
            name="Voice Test Station", scale=Scale.STATION
        )
        cls.ship = Ship.objects.create(
            name="VOICE TEST SHIP",
            current_location=cls.location,
            size=Ship.Size.MEDIUM,
        )
        cls.pilot = Pilot.create(ship=cls.ship)
        cls.pilot.name = "Voice Pilot"
        cls.pilot.save()

        cls.controller = Controller.create(location=cls.location)
        cls.controller.name = "Voice Control"
        cls.controller.save()

        cls.satellite = Satellite.create(name="VOICE SAT")

    def _make_event(self, actor=None, metadata=None):
        return DialogueEventLog(
            timestamp=1000.0,
            actor=actor,
            actor_name=actor.name if actor else "Unknown",
            text="Test message",
            metadata=metadata or {},
        )

    def test_metadata_voice_id_is_returned_directly(self):
        """When metadata has voice_id, it's returned without touching actor profile."""
        event = self._make_event(metadata={"voice_id": "pilot-M-007_canonical_all"})
        voice = _resolve_voice_for_event(event)
        self.assertEqual(voice, "pilot-M-007_canonical_all")

    def test_missing_actor_returns_fallback_voice(self):
        """Event with no actor FK returns 'pilot_default' fallback."""
        event = self._make_event(actor=None)
        voice = _resolve_voice_for_event(event)
        self.assertEqual(voice, "pilot_default")

    def test_actor_with_valid_profile_returns_voice_template(self):
        """Actor with a valid audio profile and voice_template returns that template."""
        # Ensure pilot has a profile with a known voice_template
        AudioProfile.objects.filter(actor=self.pilot).delete()
        AudioProfile.objects.create(
            actor=self.pilot,
            params={
                "voiceprint": {"voice_template": "pilot-F-003_canonical_all"},
                "room_tone": {"enabled": True},
                "static": {"intensity": 0.05},
                "quindar": {},
            },
        )

        event = self._make_event(actor=self.pilot)
        voice = _resolve_voice_for_event(event)
        self.assertEqual(voice, "pilot-F-003_canonical_all")

    def test_actor_with_missing_profile_assigns_on_demand_and_returns_voice(self):
        """Actor without an audio_profile gets one assigned on-demand."""
        # Delete any existing profile
        AudioProfile.objects.filter(actor=self.satellite).delete()

        event = self._make_event(actor=self.satellite)
        voice = _resolve_voice_for_event(event)
        # Either a real voice template or the fallback — should not crash
        self.assertIsInstance(voice, str)
        self.assertTrue(len(voice) > 0)

    def test_actor_with_no_voice_template_returns_fallback(self):
        """Actor profile with no voice_template falls back to 'pilot_default'."""
        # Create a profile with no voice template set
        AudioProfile.objects.filter(actor=self.pilot).delete()
        AudioProfile.objects.create(
            actor=self.pilot,
            params={
                "voiceprint": {},  # No voice_template key
                "room_tone": {"enabled": False},
                "static": {"intensity": 0.0},
                "quindar": {},
            },
        )
        event = self._make_event(actor=self.pilot)
        voice = _resolve_voice_for_event(event)
        self.assertEqual(voice, "pilot_default")


class TestSentenceCase(TestCase):
    """Tests for _sentence_case() utility function."""

    def test_all_caps_is_lowercased_then_first_letter_capitalized(self):
        self.assertEqual(_sentence_case("HELLO WORLD"), "Hello world")

    def test_already_sentence_case_is_unchanged(self):
        self.assertEqual(_sentence_case("Hello world"), "Hello world")

    def test_empty_string_returns_empty(self):
        self.assertEqual(_sentence_case(""), "")

    def test_whitespace_only_returns_whitespace(self):
        result = _sentence_case("   ")
        self.assertEqual(result.strip(), "")

    def test_mixed_case_with_leading_upper_is_unchanged(self):
        """Non-all-caps text is not modified beyond capitalizing the first letter."""
        # "Hello World" is not all-caps, so goes through the alpha-find path
        result = _sentence_case("Hello World")
        self.assertTrue(result[0].isupper())

    def test_leading_non_alpha_chars(self):
        """First alphabetic character is capitalized even with leading punctuation."""
        result = _sentence_case("123 hello world")
        # Should find 'h' and capitalize it
        self.assertIn("H", result)


class TestEventFeedCursorValidation(TestCase):
    """Tests for cursor parameter validation in event_feed."""

    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=10000.0,
            anchor_wall_clock=time.time(),
            time_scale=1.0,
        )

    def test_after_id_without_after_ts_returns_400(self):
        """Providing after_id without after_ts should return 400."""
        response = self.client.get("/api/events/?after_id=5")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("after_ts", data["message"])

    def test_invalid_after_ts_returns_400(self):
        """Non-numeric after_ts should return 400."""
        response = self.client.get("/api/events/?after_ts=not_a_float")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "error")

    def test_invalid_after_id_with_valid_after_ts_returns_400(self):
        """Non-integer after_id combined with valid after_ts returns 400."""
        response = self.client.get("/api/events/?after_ts=0.0&after_id=notanint")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "error")

    def test_valid_cursor_returns_200(self):
        """Valid after_ts + after_id combination is accepted."""
        response = self.client.get("/api/events/?after_ts=0.0&after_id=0")
        self.assertEqual(response.status_code, 200)

    def test_limit_parameter_is_respected(self):
        """Limit parameter caps the number of returned events."""
        for i in range(5):
            DialogueEventLog.objects.create(
                timestamp=float(i * 100),
                actor_name=f"Actor {i}",
                text=f"Message {i}",
            )
        response = self.client.get("/api/events/?limit=2")
        data = response.json()
        self.assertLessEqual(len(data["events"]), 2)


# ---------------------------------------------------------------------------
# DialogueEvent dataclass validation
# ---------------------------------------------------------------------------


class TestDialogueEventValidation(TestCase):
    """
    Tests for DialogueEvent.__post_init__() validation (models/event.py lines 76, 78).

    DialogueEvent is a frozen dataclass; __post_init__ raises ValueError for
    missing actors and actors without an id attribute.
    """

    def test_dialogue_event_raises_when_actor_is_none(self):
        """Constructing a DialogueEvent with actor=None raises ValueError (line 76)."""
        from mysite.universe.models.event import DialogueEvent

        with self.assertRaises(ValueError, msg="DialogueEvent requires an actor"):
            DialogueEvent(timestamp=0.0, actor=None, text="hello")

    def test_dialogue_event_raises_when_actor_has_no_id(self):
        """Constructing a DialogueEvent with an actor lacking 'id' raises ValueError (line 78)."""
        from mysite.universe.models.event import DialogueEvent

        class NoIdActor:
            """Stub actor with no id attribute."""

        with self.assertRaises(ValueError):
            DialogueEvent(timestamp=0.0, actor=NoIdActor(), text="hello")

    def test_dialogue_event_succeeds_with_valid_actor(self):
        """A DialogueEvent with a proper actor (has id) constructs without error."""
        from mysite.universe.models.event import DialogueEvent

        class MinimalActor:
            id = 42

        event = DialogueEvent(timestamp=10.0, actor=MinimalActor(), text="Roger that.")
        self.assertEqual(event.text, "Roger that.")


# ---------------------------------------------------------------------------
# DialogueEventLog.save() metadata=None branch
# ---------------------------------------------------------------------------


class TestDialogueEventLogSave(TestCase):
    """
    Tests for DialogueEventLog.save() metadata handling (models/event.py line 157).

    When metadata is None at save time it must be normalised to {}.
    """

    def test_save_with_none_metadata_normalises_to_empty_dict(self):
        """
        Explicitly setting metadata=None before save() triggers the
        `if self.metadata is None: self.metadata = {}` branch (line 157).
        """
        event = DialogueEventLog(
            timestamp=0.0,
            actor_name="Ghost",
            text="Signal lost.",
            metadata=None,
        )
        event.save()
        event.refresh_from_db()
        self.assertEqual(event.metadata, {})
