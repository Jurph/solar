import pytest
import io
import requests
import yaml
from contextlib import redirect_stdout, redirect_stderr

pytestmark = [pytest.mark.slow, pytest.mark.external, pytest.mark.llm]


@pytest.fixture
def llm():
    """Fixture that returns an initialized LLM service."""
    from mysite.universe.services.llm_service import LLMService

    return LLMService(quiet_mode=True)  # We can disable quiet mode for debugging


@pytest.fixture
def yes_no_prompt():
    """Fixture that returns a system prompt that encourages YES/NO answers."""
    return """
    You are an AI assistant that has been incorporated into a simple
    software program. You are undergoing functional unit testing. 
    
    IMPORTANT GUIDELINES:
    1. Answer all questions with YES or NO only
    2. Do not include any extra words, explanations, or context
    3. If you absolutely cannot answer with YES or NO, use EXACTLY ONE WORD
    """


def ask_question(llm, system_prompt, question):
    """Helper function to ask a question and return the response."""
    print(f"Asking: {question}")
    # Redirect stdout/stderr during the LLM call to suppress ollama output

    # Create string IO objects to capture output
    f_stdout = io.StringIO()
    f_stderr = io.StringIO()

    # Redirect both stdout and stderr during the LLM call
    with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
        response = llm.generate_with_system_prompt(
            user_message=question,
            system_prompt=system_prompt,
            temperature=0.35,
            max_tokens=10,  # We only need a short response
        )

    print(f"Response: {response}")
    return response.strip()


def check_response_format(response):
    """Helper function to check if response is a short yes/no answer."""
    response_lower = response.lower()
    # Check if response contains either 'yes' or 'no'
    has_yes_no = "yes" in response_lower or "no" in response_lower
    # Check that response isn't too long (allowing for some variation)
    is_short = len(response) <= 6
    return has_yes_no, is_short


@pytest.mark.slow
def test_ollama_api_endpoint_available():
    """
    Test that Ollama's /api/chat endpoint is listening and responding.

    Makes a minimal health check request that doesn't engage the LLM model.
    Uses /api/tags endpoint which is a simple GET request that lists available models.
    """
    # Read config to get base URL
    with open("llm.config", "r") as f:
        config = yaml.safe_load(f)

    api_base = config["api_base"].rstrip("/")
    # Remove /v1 suffix if present to get base Ollama URL
    if api_base.endswith("/v1"):
        api_base = api_base[:-3]

    # Ollama's /api/tags endpoint lists models without requiring inference
    tags_url = f"{api_base}/api/tags"

    try:
        response = requests.get(tags_url, timeout=5)
        response.raise_for_status()
        # Should return JSON with models list
        data = response.json()
        assert "models" in data, f"Expected 'models' key in response: {data}"
    except requests.exceptions.ConnectionError:
        pytest.skip("Ollama server not running - cannot test endpoint availability")
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Ollama /api/tags endpoint returned error: {e}")


@pytest.mark.slow
def test_openai_compatible_endpoint_available():
    """
    Test that OpenAI-compatible /v1/completions endpoint is listening.

    Makes a minimal request to verify the endpoint exists. Since we can't easily
    test /v1/completions without engaging the model, we check if the base URL
    responds (many OpenAI-compatible servers have a /health or /v1/models endpoint).
    """
    # Read config to get base URL
    with open("llm.config", "r") as f:
        config = yaml.safe_load(f)

    api_base = config["api_base"].rstrip("/")

    # Try /v1/models endpoint (common in OpenAI-compatible servers)
    models_url = f"{api_base}/models"

    try:
        response = requests.get(models_url, timeout=5)
        # Accept 200 (success) or 404 (endpoint doesn't exist but server is up)
        # 404 means server is listening but endpoint doesn't exist (still useful info)
        assert response.status_code in [200, 404], (
            f"Expected 200 or 404, got {response.status_code}: {response.text}"
        )
    except requests.exceptions.ConnectionError:
        pytest.skip("LLM server not running - cannot test endpoint availability")
    except requests.exceptions.RequestException as e:
        pytest.fail(f"OpenAI-compatible endpoint check failed: {e}")


@pytest.mark.slow
def test_llm_connection(llm, yes_no_prompt):
    """Test that the LLM responds to a basic connection test."""
    response = ask_question(llm, yes_no_prompt, "Are you connected and functional?")
    has_yes_no, is_short = check_response_format(response)

    assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
    assert is_short, f"Response is too long: {response}"


@pytest.mark.slow
def test_llm_understands_instructions(llm, yes_no_prompt):
    """Test that the LLM follows instructions to give one-word answers."""
    response = ask_question(
        llm, yes_no_prompt, "Will you respond with only YES or NO to these questions?"
    )
    has_yes_no, is_short = check_response_format(response)

    assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
    assert is_short, f"Response is too long: {response}"


@pytest.mark.slow
def test_llm_space_knowledge(llm, yes_no_prompt):
    """Test that the LLM has knowledge about basic space concepts."""
    response = ask_question(
        llm, yes_no_prompt, "Is a Hohmann transfer orbit used for space travel?"
    )
    has_yes_no, is_short = check_response_format(response)

    assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
    assert is_short, f"Response is too long: {response}"


@pytest.mark.slow
def test_llm_false_statement(llm, yes_no_prompt):
    """Test that the LLM can correctly identify false statements."""
    response = ask_question(
        llm,
        yes_no_prompt,
        "The Earth is 12,756km in diameter. The Moon is 3,474km in diameter. Is the Moon larger than the Earth?",
    )
    has_yes_no, is_short = check_response_format(response)

    assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
    assert is_short, f"Response is too long: {response}"
    assert "no" in response.lower(), (
        f"Expected 'no' in response for false statement but got: {response}"
    )


@pytest.mark.slow
def test_llm_ambiguous_question(llm, yes_no_prompt):
    """Test that the LLM handles ambiguous questions appropriately."""
    response = ask_question(
        llm, yes_no_prompt, "Can spaceships travel faster than light?"
    )
    # Just check it's short, allow any one-word answer
    assert len(response.split()) <= 1, f"Expected single word but got: {response}"


@pytest.mark.slow
def test_battery_of_questions(llm, yes_no_prompt):
    """Run through a battery of YES/NO questions and check responses."""
    questions = [
        # Definite facts
        ("Is Earth a planet?", "yes"),
        (
            "Do most spacecraft use chemical rockets?",
            ["yes", "no"],
        ),  # Allow either response
        ("Can humans survive in space without a spacesuit?", "no"),
        ("Is orbital mechanics a field of physics?", "yes"),
    ]

    for question, expected in questions:
        response = ask_question(llm, yes_no_prompt, question)
        has_yes_no, is_short = check_response_format(response)

        assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
        assert is_short, f"Response is too long: {response}"

        # For more definite questions, check the specific answer
        if isinstance(expected, str):
            assert expected in response.lower(), (
                f"For '{question}', expected '{expected}' but got: '{response}'"
            )
        else:
            # For questions with multiple acceptable answers, check that one matches
            assert any(exp in response.lower() for exp in expected), (
                f"For '{question}', expected one of {expected} but got: '{response}'"
            )


# Keep the main function for manual testing outside of pytest
def main():
    """Run the tests manually outside of pytest."""
    from mysite.universe.services.llm_service import LLMService

    # Note: LLMService.__init__ takes config_path, not model_name directly
    # For now, using default config_path - this may need adjustment after refactoring
    llm_instance = LLMService(quiet_mode=True)
    prompt = """
    You are an AI assistant that has been incorporated into a simple
    software program. You are undergoing functional testing.
    
    IMPORTANT GUIDELINES:
    1. Answer all questions with YES or NO only
    2. Do not include any extra words, explanations, or context
    3. If you absolutely cannot answer with YES or NO, use EXACTLY ONE WORD
    """

    questions = [
        "Are you connected and functional?",
        "Will you respond with only YES or NO to these questions?",
        "Is a Hohmann transfer orbit used for space travel?",
        "Can spaceships travel faster than light?",
    ]

    for question in questions:
        response = ask_question(llm_instance, prompt, question)
        print(f"Q: {question}")
        print(f"A: {response}")
        print("-" * 50)


if __name__ == "__main__":
    main()
