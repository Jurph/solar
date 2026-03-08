"""
Tests for DialogueService.

Covers:
- build_prompt() guard against SatelliteResponse
- generate_dialogue() satellite pre-programmed path
- generate_dialogue() callsign stripping
- generate_dialogue() retry on malformed JSON
- generate_dialogue() raises after retry exhaustion
- _select_next_particle_type() edge cases
- _determine_actor_and_recipient() routing
- generate_chain_iteratively() termination
"""

from unittest.mock import MagicMock
from django.test import TestCase

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale
from mysite.universe.models.ship import Ship
from mysite.universe.schemas.dialogue_schema import Role
from mysite.universe.services.dialogue_server import DialogueService
from mysite.universe.services.dialogue.particles import (
    LaunchRequest,
    RadioResponse,
    SatelliteResponse,
)
from mysite.universe.services.llm_service import LLMService


class DialogueServiceTestBase(TestCase):
    """Shared fixtures for DialogueService tests."""

    @classmethod
    def setUpTestData(cls):
        cls.location = Location.objects.create(name="Hub Station", scale=Scale.STATION)
        cls.ship = Ship.objects.create(
            name="STELLAR NOVA", current_location=cls.location, size=Ship.Size.MEDIUM
        )
        cls.pilot = Pilot.create(ship=cls.ship)
        cls.pilot.name = "Lt. Vasquez"
        cls.pilot.save()

        cls.controller = Controller.create(location=cls.location)
        cls.controller.name = "Hub Control"
        cls.controller.save()

        cls.satellite = Satellite.create(name="RELAY ALPHA")

        cls.base_nav_context = {
            "maneuver_type": "launch",
            "current_location": "Hub Station",
            "destination": "Mars",
        }

    def _make_service(self, llm_response: str = '{"message": "cleared for launch"}'):
        """Return a DialogueService with a mocked LLMService."""
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.return_value = llm_response
        return DialogueService(llm_service=mock_llm), mock_llm


class TestBuildPrompt(DialogueServiceTestBase):
    """Tests for DialogueService.build_prompt()."""

    def test_raises_for_satellite_response(self):
        """build_prompt() must reject SatelliteResponse particles."""
        service, _ = self._make_service()
        particle = SatelliteResponse(
            actor=self.satellite,
            recipient="STELLAR NOVA",
            nav_context={},
        )
        with self.assertRaises(ValueError):
            service.build_prompt(particle)

    def test_returns_tuple_for_normal_particle(self):
        """build_prompt() returns (system_prompt, user_prompt) for standard particles."""
        service, _ = self._make_service()
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )
        system_prompt, user_prompt = service.build_prompt(particle)
        self.assertIsInstance(system_prompt, str)
        self.assertIsInstance(user_prompt, str)
        self.assertTrue(len(system_prompt) > 0)
        self.assertTrue(len(user_prompt) > 0)

    def test_previous_dialogue_included_in_user_prompt(self):
        """When previous_dialogue is supplied, user_prompt references it."""
        from mysite.universe.schemas.dialogue_schema import DialogueMessage

        service, _ = self._make_service()
        particle = RadioResponse(
            actor=self.controller,
            recipient="STELLAR NOVA",
            nav_context=self.base_nav_context,
        )
        prev = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR NOVA",
            recipient_callsign="HUB CONTROL",
            message="Hub Control, this is Stellar Nova. Request launch clearance.",
        )
        _, user_prompt = service.build_prompt(particle, previous_dialogue=prev)
        self.assertIn("Stellar Nova", user_prompt)


class TestGenerateDialogueSatellitePath(DialogueServiceTestBase):
    """generate_dialogue() takes a pre-programmed path for SatelliteResponse."""

    def test_satellite_response_does_not_call_llm(self):
        """SatelliteResponse must bypass LLM entirely."""
        service, mock_llm = self._make_service()
        particle = SatelliteResponse(
            actor=self.satellite,
            recipient="STELLAR NOVA",
            nav_context={},
        )
        result = service.generate_dialogue(particle)
        mock_llm.chat.assert_not_called()
        self.assertIsNotNone(result)

    def test_satellite_response_builds_valid_dialogue_message(self):
        """SatelliteResponse produces a well-formed DialogueMessage."""
        service, _ = self._make_service()
        particle = SatelliteResponse(
            actor=self.satellite,
            recipient="STELLAR NOVA",
            nav_context={},
        )
        result = service.generate_dialogue(particle)
        self.assertEqual(result.role, Role.SATELLITE)
        self.assertIn("RELAY ALPHA", result.speaker_callsign)
        self.assertTrue(len(result.message) > 0)

    def test_satellite_message_contains_procedural_greeting(self):
        """Satellite message is prefixed with recipient greeting."""
        service, _ = self._make_service()
        particle = SatelliteResponse(
            actor=self.satellite,
            recipient="STELLAR NOVA",
            nav_context={},
        )
        result = service.generate_dialogue(particle)
        # Message should start with "STELLAR NOVA, RELAY ALPHA."
        self.assertIn("STELLAR NOVA", result.message)


class TestGenerateDialogueCallsignStripping(DialogueServiceTestBase):
    """generate_dialogue() strips callsigns that the LLM accidentally includes."""

    def test_strips_sender_callsign_from_message(self):
        """LLM-included sender callsign is removed from message content."""
        service, _ = self._make_service(
            llm_response='{"message": "STELLAR NOVA cleared for launch on azimuth 045"}'
        )
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )
        result = service.generate_dialogue(particle)
        # Sender callsign should be stripped from message body
        self.assertNotIn("STELLAR NOVA", result.message.split(".", 1)[-1].strip())

    def test_strips_recipient_callsign_from_message(self):
        """LLM-included recipient callsign is removed from message content."""
        # Recipient of RadioResponse is "STELLAR NOVA" (the ship).
        # LLM incorrectly puts the recipient callsign in the body.
        service, _ = self._make_service(
            llm_response='{"message": "STELLAR NOVA cleared for departure, azimuth 127"}'
        )
        particle = RadioResponse(
            actor=self.controller,
            recipient="STELLAR NOVA",
            nav_context=self.base_nav_context,
        )
        result = service.generate_dialogue(particle)
        # Recipient callsign should be stripped from the body portion (after greeting)
        body = result.message.split(".", 1)[-1].strip()
        self.assertNotIn("STELLAR NOVA", body)


class TestGenerateDialogueRetries(DialogueServiceTestBase):
    """generate_dialogue() retries on failure and raises when exhausted."""

    def test_retries_on_json_parse_failure_then_succeeds(self):
        """If LLM returns invalid JSON on first try, retry succeeds."""
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.side_effect = [
            "NOT VALID JSON",
            '{"message": "cleared for launch"}',
        ]
        service = DialogueService(llm_service=mock_llm)
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )
        result = service.generate_dialogue(particle, max_retries=2)
        self.assertEqual(mock_llm.chat.call_count, 2)
        self.assertIn("cleared for launch", result.message)

    def test_raises_after_retry_exhaustion(self):
        """generate_dialogue() raises ValueError after all retries fail."""
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.return_value = "NOT VALID JSON AT ALL <<<>>>"
        service = DialogueService(llm_service=mock_llm)
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )
        with self.assertRaises(Exception):
            service.generate_dialogue(particle, max_retries=1)
        # Should have tried max_retries+1 times
        self.assertEqual(mock_llm.chat.call_count, 2)


class TestGenerateDialogueBadContentDetection(DialogueServiceTestBase):
    """generate_dialogue() retries and raises when LLM returns bad content patterns."""

    def _particle(self):
        return LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )

    def test_retries_on_template_variable_leakage(self):
        """If LLM returns a ${...} template variable, retry with next attempt."""
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.side_effect = [
            '{"message": "requesting clearance for ${current_situation.maneuver_type}"}',
            '{"message": "requesting clearance for launch"}',
        ]
        service = DialogueService(llm_service=mock_llm)
        result = service.generate_dialogue(self._particle(), max_retries=2)
        self.assertEqual(mock_llm.chat.call_count, 2)
        self.assertNotIn("${", result.message)

    def test_retries_on_json_fragment_leakage(self):
        """If LLM response contains a leaked JSON fragment, retry."""
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.side_effect = [
            '{"message": \'{ "role": "CONTROLLER", "message": "cleared"}\'}',
            '{"message": "cleared for departure"}',
        ]
        service = DialogueService(llm_service=mock_llm)
        result = service.generate_dialogue(self._particle(), max_retries=2)
        self.assertEqual(mock_llm.chat.call_count, 2)
        self.assertIn("cleared for departure", result.message)

    def test_retries_on_error_in_communication_fallback(self):
        """If LLM returns an 'Error in communication' fallback, retry."""
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.side_effect = [
            '{"message": "Error in communication, please stand by"}',
            '{"message": "standing by for your transmission"}',
        ]
        service = DialogueService(llm_service=mock_llm)
        result = service.generate_dialogue(self._particle(), max_retries=2)
        self.assertEqual(mock_llm.chat.call_count, 2)
        self.assertIn("standing by", result.message)

    def test_raises_after_exhausting_retries_on_bad_content(self):
        """If all attempts return bad content, raises ValueError after max_retries+1 tries."""
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.return_value = '{"message": "${current_situation.maneuver_type}"}'
        service = DialogueService(llm_service=mock_llm)
        with self.assertRaises(ValueError):
            service.generate_dialogue(self._particle(), max_retries=1)
        self.assertEqual(mock_llm.chat.call_count, 2)

    def test_clean_content_on_first_attempt_does_not_retry(self):
        """A valid clean response succeeds immediately with a single LLM call."""
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.return_value = '{"message": "cleared for takeoff"}'
        service = DialogueService(llm_service=mock_llm)
        result = service.generate_dialogue(self._particle(), max_retries=3)
        self.assertEqual(mock_llm.chat.call_count, 1)
        self.assertIn("cleared for takeoff", result.message)


class TestSelectNextParticleType(DialogueServiceTestBase):
    """_select_next_particle_type() edge cases."""

    def setUp(self):
        mock_llm = MagicMock(spec=LLMService)
        self.service = DialogueService(llm_service=mock_llm)

    def test_empty_probabilities_returns_none(self):
        """Empty dict → chain ends → returns None."""
        result = self.service._select_next_particle_type({})
        self.assertIsNone(result)

    def test_zero_total_returns_none(self):
        """Probabilities that all sum to zero → returns None."""
        result = self.service._select_next_particle_type({"response": 0.0, "hold": 0.0})
        self.assertIsNone(result)

    def test_single_full_probability_always_returns_that_type(self):
        """When one type has probability 1.0, it must always be selected."""
        for _ in range(20):
            result = self.service._select_next_particle_type({"readback": 1.0})
            self.assertEqual(result, "readback")

    def test_probabilities_less_than_one_normalizes_not_ends(self):
        """When sum < 1.0, selection is normalized across the given types (not ended).

        The code does r = random.random() * total, so it always picks a winner
        among the provided types regardless of sum. Chain ends only via empty dict.
        """
        results = [
            self.service._select_next_particle_type({"response": 0.01})
            for _ in range(50)
        ]
        # All should be "response" — normalization means the single entry always wins
        self.assertTrue(all(r == "response" for r in results))

    def test_deterministic_selection_with_only_one_nonzero(self):
        """With only one non-zero entry, it must win every time."""
        result = self.service._select_next_particle_type(
            {"response": 0.95, "hold": 0.0}
        )
        self.assertEqual(result, "response")


class TestDetermineActorAndRecipient(DialogueServiceTestBase):
    """_determine_actor_and_recipient() routing for all particle types."""

    def setUp(self):
        mock_llm = MagicMock(spec=LLMService)
        self.service = DialogueService(llm_service=mock_llm)

    def test_request_actor_is_pilot(self):
        actor, recipient = self.service._determine_actor_and_recipient(
            "request", self.pilot, self.controller
        )
        self.assertEqual(actor, self.pilot)
        self.assertEqual(recipient, "HUB CONTROL")

    def test_readback_actor_is_pilot(self):
        actor, recipient = self.service._determine_actor_and_recipient(
            "readback", self.pilot, self.controller
        )
        self.assertEqual(actor, self.pilot)

    def test_holding_actor_is_pilot(self):
        actor, recipient = self.service._determine_actor_and_recipient(
            "holding", self.pilot, self.controller
        )
        self.assertEqual(actor, self.pilot)

    def test_response_actor_is_controller(self):
        actor, recipient = self.service._determine_actor_and_recipient(
            "response", self.pilot, self.controller
        )
        self.assertEqual(actor, self.controller)
        self.assertIn("STELLAR NOVA", recipient)

    def test_hold_response_actor_is_controller(self):
        actor, recipient = self.service._determine_actor_and_recipient(
            "hold_response", self.pilot, self.controller
        )
        self.assertEqual(actor, self.controller)

    def test_adjusted_response_actor_is_controller(self):
        actor, recipient = self.service._determine_actor_and_recipient(
            "adjusted_response", self.pilot, self.controller
        )
        self.assertEqual(actor, self.controller)

    def test_comms_check_actor_is_pilot(self):
        actor, recipient = self.service._determine_actor_and_recipient(
            "comms_check", self.pilot, self.controller, satellite=self.satellite
        )
        self.assertEqual(actor, self.pilot)
        self.assertIn("RELAY ALPHA", recipient)

    def test_comms_check_requires_satellite(self):
        with self.assertRaises(ValueError):
            self.service._determine_actor_and_recipient(
                "comms_check", self.pilot, self.controller, satellite=None
            )

    def test_satellite_response_actor_is_satellite(self):
        actor, recipient = self.service._determine_actor_and_recipient(
            "satellite_response", self.pilot, self.controller, satellite=self.satellite
        )
        self.assertEqual(actor, self.satellite)

    def test_satellite_response_requires_satellite(self):
        with self.assertRaises(ValueError):
            self.service._determine_actor_and_recipient(
                "satellite_response", self.pilot, self.controller, satellite=None
            )

    def test_unknown_type_falls_back_to_pilot(self):
        actor, _ = self.service._determine_actor_and_recipient(
            "mystery_particle", self.pilot, self.controller
        )
        self.assertEqual(actor, self.pilot)

    def test_particle_type_is_case_insensitive(self):
        """Particle type matching is lowercase-normalized."""
        actor1, _ = self.service._determine_actor_and_recipient(
            "RESPONSE", self.pilot, self.controller
        )
        actor2, _ = self.service._determine_actor_and_recipient(
            "response", self.pilot, self.controller
        )
        self.assertEqual(actor1, actor2)


class TestGenerateChainIteratively(DialogueServiceTestBase):
    """generate_chain_iteratively() termination and structure."""

    def _make_service_with_llm(self):
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.chat.return_value = '{"message": "affirmative"}'
        return DialogueService(llm_service=mock_llm), mock_llm

    def test_chain_returns_list_of_tuples(self):
        """Returns list of (DialogueMessage, float) tuples."""
        service, _ = self._make_service_with_llm()
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )
        results = service.generate_chain_iteratively(
            initial_particle=particle,
            pilot=self.pilot,
            controller=self.controller,
            nav_context=self.base_nav_context,
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        msg, t = results[0]
        self.assertIsInstance(t, float)

    def test_chain_first_time_offset_is_zero(self):
        """First message in chain always has time offset 0.0."""
        service, _ = self._make_service_with_llm()
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )
        results = service.generate_chain_iteratively(
            initial_particle=particle,
            pilot=self.pilot,
            controller=self.controller,
            nav_context=self.base_nav_context,
        )
        _, first_time = results[0]
        self.assertEqual(first_time, 0.0)

    def test_chain_time_offsets_are_monotonically_increasing(self):
        """Subsequent messages have increasing time offsets."""
        service, _ = self._make_service_with_llm()
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )
        results = service.generate_chain_iteratively(
            initial_particle=particle,
            pilot=self.pilot,
            controller=self.controller,
            nav_context=self.base_nav_context,
        )
        if len(results) > 1:
            times = [t for _, t in results]
            self.assertEqual(times, sorted(times))
            self.assertEqual(len(set(times[:2])), 2)  # first two are distinct

    def test_chain_terminates_on_empty_probabilities(self):
        """Chain stops when particle returns empty probabilities."""
        service, _ = self._make_service_with_llm()
        # RadioReadback returns {} → chain ends after 3 steps (request→response→readback)
        # Walk a complete standard chain and verify it terminates
        particle = LaunchRequest(
            actor=self.pilot,
            recipient="HUB CONTROL",
            nav_context=self.base_nav_context,
        )
        results = service.generate_chain_iteratively(
            initial_particle=particle,
            pilot=self.pilot,
            controller=self.controller,
            nav_context=self.base_nav_context,
        )
        # Standard chain is 3 messages: request, response, readback
        self.assertGreaterEqual(len(results), 3)
        # Should not go on forever
        self.assertLessEqual(len(results), 10)
