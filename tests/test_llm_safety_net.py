"""
Safety-net tests for LLM validation and retry machinery.

All tests are mock-based — no real LLM calls are made.
Covers:
- LLMService.is_invalid_dialogue_message() edge cases
- LLMService.chat() JSON mode path: no-JSON-found and markdown stripping
- DialogueService.generate_dialogue() retry loop behavior
"""

import json
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.test import TestCase

from mysite.universe.schemas.dialogue_schema import DialogueMessage, Role
from mysite.universe.services.dialogue_server import DialogueService
from mysite.universe.services.llm_service import LLMService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_temp_llm_config() -> str:
    """Write a minimal LLMService config to a temp file and return its path."""
    content = "\n".join(
        [
            "api_base: http://localhost:11434/v1/",
            "api_key: ollama",
            "model_name: test-model",
            "temperature: 0.25",
            "max_tokens: 32",
            "",
        ]
    )
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
    f.write(content)
    f.flush()
    f.close()
    return f.name


def _make_svc() -> LLMService:
    """Return an LLMService with a mocked OpenAI client (no network)."""
    config_path = _write_temp_llm_config()
    fake_openai = Mock()
    with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
        return LLMService(config_path=config_path, quiet_mode=True)


def _mock_http_response(content: str) -> Mock:
    """Build a minimal mock for requests.post() returning the given content string."""
    resp = Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"message": {"content": content}}
    return resp


# ---------------------------------------------------------------------------
# 1. is_invalid_dialogue_message() edge cases
# ---------------------------------------------------------------------------


class TestIsInvalidDialogueMessageEdgeCases(TestCase):
    """Edge-case coverage for the content-validity detector."""

    def test_dollar_without_brace_is_clean(self):
        """A bare '$' (e.g. '$100') should not be flagged."""
        self.assertFalse(LLMService.is_invalid_dialogue_message("Cost is $100."))

    def test_brace_without_quote_is_clean(self):
        """{word} without a following quote should not be flagged."""
        self.assertFalse(
            LLMService.is_invalid_dialogue_message("Use {braces} carefully.")
        )

    def test_error_in_communication_all_caps_is_flagged(self):
        """Pattern is case-insensitive; all-caps variant must still trigger."""
        self.assertTrue(
            LLMService.is_invalid_dialogue_message("ERROR IN COMMUNICATION detected.")
        )

    def test_reversed_words_communication_error_is_clean(self):
        """'communication error' (reversed order) must NOT be flagged."""
        self.assertFalse(
            LLMService.is_invalid_dialogue_message("There was a communication error.")
        )

    def test_multiple_bad_patterns_still_flagged(self):
        """A message with both template-var and JSON-fragment is flagged."""
        self.assertTrue(
            LLMService.is_invalid_dialogue_message(
                'The value is ${foo} and { "key": 1}'
            )
        )

    def test_integer_input_returns_false(self):
        """Non-string input (int) must not raise and must return False."""
        self.assertFalse(LLMService.is_invalid_dialogue_message(42))

    def test_list_input_returns_false(self):
        """Non-string input (list) must not raise and must return False."""
        self.assertFalse(LLMService.is_invalid_dialogue_message(["${bad}"]))


# ---------------------------------------------------------------------------
# 2. LLMService.chat() JSON-mode boundary extraction
# ---------------------------------------------------------------------------


class TestChatJsonBoundaryExtraction(TestCase):
    """Verify that chat() handles edge cases in the { } boundary scan."""

    def test_response_with_no_json_object_raises(self):
        """chat() in JSON mode should raise ValueError when there is no '{' in response."""
        svc = _make_svc()
        schema = {"type": "object"}

        with patch(
            "mysite.universe.services.llm_service.requests.post",
            return_value=_mock_http_response("no braces here at all"),
        ):
            with pytest.raises(ValueError):
                svc.chat(
                    messages=[
                        {"role": "system", "content": "Return JSON."},
                        {"role": "user", "content": "Go."},
                    ],
                    use_structured_output=True,
                    format=schema,
                )

    def test_response_with_open_brace_no_close_raises(self):
        """A response with '{' but no '}' produces 'No JSON object found' ValueError."""
        svc = _make_svc()
        schema = {"type": "object"}

        with patch(
            "mysite.universe.services.llm_service.requests.post",
            return_value=_mock_http_response("{ unclosed brace"),
        ):
            with pytest.raises(ValueError):
                svc.chat(
                    messages=[
                        {"role": "system", "content": "Return JSON."},
                        {"role": "user", "content": "Go."},
                    ],
                    use_structured_output=True,
                    format=schema,
                )


# ---------------------------------------------------------------------------
# 3. DialogueService.generate_dialogue() retry loop
# ---------------------------------------------------------------------------


def _make_dialogue_service() -> DialogueService:
    """Return a DialogueService with a real mock for llm_service."""
    mock_llm = MagicMock(spec=LLMService)
    svc = DialogueService(llm_service=mock_llm)
    return svc


def _make_particle(sender: str = "ALPHA", recipient: str = "BETA") -> MagicMock:
    """Return a mock DialogueParticle (non-SatelliteResponse)."""
    particle = MagicMock()
    particle.get_sender_callsign.return_value = sender
    particle.recipient = recipient
    particle.get_role.return_value = Role.PILOT
    # Greeting includes both callsigns so DialogueMessage validator always passes
    particle.generate_procedural_greeting.return_value = f"{sender}, {recipient}."
    particle.SYSTEM_PROMPT = "You are a dialogue generator."
    particle.build_user_prompt_data.return_value = {"situation": "test"}
    particle.format_user_prompt.return_value = "Generate dialogue for: test"
    return particle


class TestDialogueServiceRetryLoop(TestCase):
    """Verify that generate_dialogue() retries on parse failure and gives up correctly."""

    def test_success_first_attempt_no_retry(self):
        """When LLM returns valid JSON on attempt 0, the loop exits immediately."""
        svc = _make_dialogue_service()
        particle = _make_particle()

        good_json = json.dumps({"message": "Ready for departure."})
        svc.llm_service.chat.return_value = good_json

        result = svc.generate_dialogue(particle, max_retries=2)

        self.assertIsInstance(result, DialogueMessage)
        # chat() should have been called exactly once (no retry)
        self.assertEqual(svc.llm_service.chat.call_count, 1)

    def test_retry_on_bad_json_succeeds_second_attempt(self):
        """When attempt 0 returns non-JSON and attempt 1 returns valid JSON, result is from attempt 1."""
        svc = _make_dialogue_service()
        particle = _make_particle()

        bad_response = "this is not json"
        good_json = json.dumps({"message": "Cleared for approach."})
        svc.llm_service.chat.side_effect = [bad_response, good_json]

        result = svc.generate_dialogue(particle, max_retries=2)

        self.assertIsInstance(result, DialogueMessage)
        self.assertEqual(svc.llm_service.chat.call_count, 2)

    def test_raises_after_max_retries_exhausted(self):
        """When every attempt returns bad JSON, generate_dialogue() raises after max_retries+1 calls."""
        svc = _make_dialogue_service()
        particle = _make_particle()

        svc.llm_service.chat.return_value = "definitely not json"

        with pytest.raises(Exception):
            svc.generate_dialogue(particle, max_retries=2)

        # Should have attempted 3 times (0, 1, 2)
        self.assertEqual(svc.llm_service.chat.call_count, 3)

    def test_zero_max_retries_raises_on_first_failure(self):
        """max_retries=0 means one attempt total; failure raises immediately."""
        svc = _make_dialogue_service()
        particle = _make_particle()

        svc.llm_service.chat.return_value = "bad json"

        with pytest.raises(Exception):
            svc.generate_dialogue(particle, max_retries=0)

        self.assertEqual(svc.llm_service.chat.call_count, 1)
