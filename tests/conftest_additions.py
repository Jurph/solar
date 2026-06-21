# This file is appended to tests/conftest.py for Docker container testing

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import os

import pytest


@pytest.fixture(autouse=True)
def mock_llm_service_for_docker(monkeypatch):
    """
    Docker-specific fixture: mock LLM service calls when running in container.
    This ensures tests pass without external LLM services.

    To enable real LLM calls, set SOLAR_USE_REAL_LLM=1 before test run.
    """
    # Only mock if we're not explicitly told to use real LLM
    use_real_llm = os.getenv("SOLAR_USE_REAL_LLM", "0") != "1"

    if not use_real_llm:
        # Create a simple mock response factory
        def create_mock_response(content=None, **kwargs):
            return type('ChatCompletion', (), {
                'model': kwargs.get('model', 'qwen2.5:1.5b'),
                'choices': [type('Choice', (), {
                    'index': 0,
                    'message': type('Message', (), {
                        'content': content or "Mock LLM response.",
                        'role': 'assistant'
                    })
                })],
                'usage': {'prompt_tokens': kwargs.get('prompt_tokens', 50),
                          'completion_tokens': kwargs.get('completion_tokens', 30),
                          'total_tokens': kwargs.get('total_tokens', 80)}
            })()

        # Create a chat completion mock
        def mock_chat(*args, **kwargs):
            content = kwargs.get('messages', [])[-1].get('content', '') if args else ''
            return create_mock_response(content=content, **kwargs)

        from mysite.universe.services import llm_service

        # Mock both possible import paths
        llm_service.ChatCompletion.create = mock_chat
        if hasattr(llm_service, 'chat'):
            llm_service.chat.completions.create = mock_chat

    yield


@pytest.fixture(autouse=True)
def mock_tts_for_docker(monkeypatch):
    """
    Disable TTS pre-generation in Docker container to speed up tests.
    Audio files are served from pre-rendered volume if available.
    """
    monkeypatch.setenv("TTS_PRE_RENDER_ENABLED", "False")

    # Optionally mock tts_service if it's being tested
    pass


# --==========================-----------------------------------------------=====
# Append this entire block to the end of tests/conftest.py:
# --==========================-----------------------------------------------=====
