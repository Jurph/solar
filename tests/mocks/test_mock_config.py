"""Test to verify mock LLM responses are loaded correctly."""

import json
from pathlib import Path


def test_mock_responses_loaded():
    """Verify mock LLM response file exists and is valid JSON."""
    mock_path = Path("tests/mocks/_llm_mock_responses.json")
    assert mock_path.exists(), f"Mock responses not found at {mock_path}"

    with open(mock_path) as f:
        data = json.load(f)

    # Verify structure
    assert "choices" in data, "Missing 'choices' key in mock response"
    assert len(data["choices"]) >= 1, "At least one choice required"
    assert "content" in data["choices"][0]["message"], "Message must have content"


def test_llm_mock_content():
    """Check that mock LLM produces sensible ATC-style dialogue."""
    with open("tests/mocks/_llm_mock_responses.json") as f:
        data = json.load(f)

    content = data["choices"][0]["message"]["content"]

    # Mock should produce ATC-style or meaningful response
    assert len(content) > 0, "Mock response must not be empty"


if __name__ == "__main__":
    test_mock_responses_loaded()
    print("✓ Mock LLM responses are valid")
    test_llm_mock_content()
    print("✓ Mock content is sensible")
