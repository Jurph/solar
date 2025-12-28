import json
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from mysite.universe.services.llm_service import LLMService


def _write_temp_llm_config() -> str:
    # Minimal config for LLMService.__init__. We patch OpenAI so no network is used.
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


class TestLLMServiceValidation:
    def test_is_invalid_dialogue_message_patterns(self):
        assert LLMService.is_invalid_dialogue_message("${foo}") is True
        assert LLMService.is_invalid_dialogue_message('{ "role": "PILOT" }') is True
        assert LLMService.is_invalid_dialogue_message("Error in communication: blah") is True
        assert LLMService.is_invalid_dialogue_message("Totally normal text") is False
        assert LLMService.is_invalid_dialogue_message("") is False
        assert LLMService.is_invalid_dialogue_message(None) is False


class TestLLMServiceChat:
    def test_chat_structured_output_json_mode_strips_markdown_and_returns_json(self):
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        fake_openai.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(text="unused")]
        )

        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        response_json = """```json
{"role":"PILOT","speaker_callsign":"ALPHA","recipient_callsign":"BETA","message":"ALPHA, BETA. Hello."}
```"""

        response_obj = Mock()
        response_obj.raise_for_status.return_value = None
        response_obj.json.return_value = {"message": {"content": response_json}}

        schema = {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}
        with patch("mysite.universe.services.llm_service.requests.post", return_value=response_obj) as post:
            out = svc.chat(
                messages=[
                    {"role": "system", "content": "Return ONLY JSON."},
                    {"role": "user", "content": "Say hello."},
                ],
                use_structured_output=True,
                format=schema,
            )

        parsed = json.loads(out)
        assert parsed["role"] == "PILOT"
        assert parsed["speaker_callsign"] == "ALPHA"
        assert parsed["recipient_callsign"] == "BETA"

        # Ensure we used Ollama /api/chat endpoint for structured outputs
        assert post.call_count == 1
        called_url = post.call_args[0][0]
        assert called_url.endswith("/api/chat")

    def test_chat_json_mode_validation_failure_falls_back_to_model_construct(self):
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        fake_openai.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(text="unused")]
        )

        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        # This message will FAIL DialogueMessage validator (missing speaker/recipient mentions),
        # so the service should return model_construct() output instead of raising.
        response_json = """{"role":"PILOT","speaker_callsign":"ALPHA","recipient_callsign":"BETA","message":"Hello."}"""

        response_obj = Mock()
        response_obj.raise_for_status.return_value = None
        response_obj.json.return_value = {"message": {"content": response_json}}

        schema = {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}
        with patch("mysite.universe.services.llm_service.requests.post", return_value=response_obj):
            out = svc.chat(
                messages=[
                    {"role": "system", "content": "JSON schema"},
                    {"role": "user", "content": "Say hello."},
                ],
                use_structured_output=True,
                format=schema,
            )

        parsed = json.loads(out)
        assert parsed["role"] == "PILOT"
        assert parsed["speaker_callsign"] == "ALPHA"
        assert parsed["recipient_callsign"] == "BETA"
        assert parsed["message"] == "Hello."

    def test_chat_plain_text_mode_uses_openai_completion_path(self):
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        fake_openai.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(text="Some plain text")]
        )

        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        out = svc.chat(
            messages=[
                {"role": "system", "content": "You are a helper."},
                {"role": "user", "content": "Hello"},
            ],
            use_structured_output=False,
            format=None,
        )
        assert out == "Some plain text"
        assert fake_openai.completions.create.call_count == 1

    def test_chat_system_prompt_replaces_existing_system_message_in_structured_mode(self):
        """
        Backward-compat behavior: system_prompt arg should override any provided system message.
        This matters because downstream JSON-mode detection is based on system content.
        """
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        response_obj = Mock()
        response_obj.raise_for_status.return_value = None
        response_obj.json.return_value = {
            "message": {
                "content": '{"role":"PILOT","speaker_callsign":"ALPHA","recipient_callsign":"BETA","message":"ALPHA, BETA. Hi."}'
            }
        }

        schema = {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}
        with patch("mysite.universe.services.llm_service.requests.post", return_value=response_obj) as post:
            svc.chat(
                messages=[
                    {"role": "system", "content": "OLD SYSTEM"},
                    {"role": "user", "content": "Hello"},
                ],
                system_prompt="Return JSON.",
                use_structured_output=True,
                format=schema,
            )

        payload = post.call_args.kwargs["json"]
        system_msgs = [m for m in payload["messages"] if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "Return JSON."

    def test_chat_system_prompt_inserts_system_message_when_missing(self):
        config_path = _write_temp_llm_config()
        fake_openai = Mock()
        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        response_obj = Mock()
        response_obj.raise_for_status.return_value = None
        response_obj.json.return_value = {
            "message": {
                "content": '{"role":"PILOT","speaker_callsign":"ALPHA","recipient_callsign":"BETA","message":"ALPHA, BETA. Hi."}'
            }
        }

        schema = {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}
        with patch("mysite.universe.services.llm_service.requests.post", return_value=response_obj) as post:
            svc.chat(
                messages=[{"role": "user", "content": "Hello"}],
                system_prompt="Return JSON.",
                use_structured_output=True,
                format=schema,
            )
        payload = post.call_args.kwargs["json"]
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "Return JSON."

    def test_chat_json_mode_raises_on_non_json_response(self):
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        fake_openai.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(text="Definitely not JSON")]
        )

        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        with pytest.raises(ValueError):
            svc.chat(
                messages=[
                    {"role": "system", "content": "Return JSON."},
                    {"role": "user", "content": "Hello"},
                ],
                use_structured_output=False,
                format=None,
            )

    def test_chat_plain_text_mode_returns_error_string_on_transport_failure(self):
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        fake_openai.completions.create.side_effect = RuntimeError("network down")
        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        out = svc.chat(
            messages=[
                {"role": "system", "content": "You are a helper."},
                {"role": "user", "content": "Hello"},
            ],
            use_structured_output=False,
            format=None,
        )
        assert out.startswith("Error communicating with LLM:")

    def test_generate_with_system_prompt_delegates_to_chat(self):
        config_path = _write_temp_llm_config()
        fake_openai = Mock()
        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        svc.chat = Mock(return_value="OK")
        out = svc.generate_with_system_prompt("hello", "sys", temperature=0.1, max_tokens=5)
        assert out == "OK"
        assert svc.chat.call_count == 1

    def test_chat_plain_text_mode_non_quiet_executes_prompt_and_response_prints(self):
        """
        Cover the non-quiet debug printing branches; we stub print to avoid noisy test output.
        """
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        fake_openai.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(text="Non-quiet plain text")]
        )

        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=False)

        with patch("builtins.print"):
            out = svc.chat(
                messages=[
                    {"role": "system", "content": "You are a helper."},
                    {"role": "user", "content": "Hello"},
                ],
                use_structured_output=False,
                format=None,
            )
        assert out == "Non-quiet plain text"

    def test_chat_invalid_json_non_quiet_prints_warning_and_raises(self):
        """
        In JSON mode, invalid JSON should raise ValueError; in non-quiet mode we also
        exercise the warning print path.
        """
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        fake_openai.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(text="not-json")]
        )

        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=False)

        with (
            patch("builtins.print"),
            pytest.raises(ValueError),
        ):
            svc.chat(
                messages=[
                    {"role": "system", "content": "Return JSON."},
                    {"role": "user", "content": "Hello"},
                ],
                use_structured_output=False,
                format=None,
            )

    def test_chat_json_mode_propagates_transport_errors_as_value_error(self):
        config_path = _write_temp_llm_config()

        fake_openai = Mock()
        with patch("mysite.universe.services.llm_service.OpenAI", return_value=fake_openai):
            svc = LLMService(config_path=config_path, quiet_mode=True)

        schema = {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}
        with patch("mysite.universe.services.llm_service.requests.post", side_effect=RuntimeError("boom")):
            with pytest.raises(ValueError) as e:
                svc.chat(
                    messages=[
                        {"role": "system", "content": "Return JSON."},
                        {"role": "user", "content": "Hello"},
                    ],
                    use_structured_output=True,
                    format=schema,
                )
        assert "Error communicating with LLM" in str(e.value)

