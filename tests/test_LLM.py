import pytest
import io
from contextlib import redirect_stdout, redirect_stderr
from mysite.universe.services.llm_service import LLMService

@pytest.fixture
def llm():
    """Fixture that returns an initialized LLM service."""
    return LLMService(quiet_mode=True) # We can disable quiet mode for debugging    

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
            max_tokens=10     # We only need a short response
        )
    
    print(f"Response: {response}")
    return response.strip()

def check_response_format(response):
    """Helper function to check if response is a short yes/no answer."""
    response_lower = response.lower()
    # Check if response contains either 'yes' or 'no'
    has_yes_no = 'yes' in response_lower or 'no' in response_lower
    # Check that response isn't too long (allowing for some variation)
    is_short = len(response) <= 6
    return has_yes_no, is_short

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
    response = ask_question(llm, yes_no_prompt, "Will you respond with only YES or NO to these questions?")
    has_yes_no, is_short = check_response_format(response)
    
    assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
    assert is_short, f"Response is too long: {response}"

@pytest.mark.slow
def test_llm_space_knowledge(llm, yes_no_prompt):
    """Test that the LLM has knowledge about basic space concepts."""
    response = ask_question(llm, yes_no_prompt, "Is a Hohmann transfer orbit used for space travel?")
    has_yes_no, is_short = check_response_format(response)
    
    assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
    assert is_short, f"Response is too long: {response}"

@pytest.mark.slow
def test_llm_false_statement(llm, yes_no_prompt):
    """Test that the LLM can correctly identify false statements."""
    response = ask_question(llm, yes_no_prompt, "The Earth is 12,756km in diameter. The Moon is 3,474km in diameter. Is the Moon larger than the Earth?")
    has_yes_no, is_short = check_response_format(response)
    
    assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
    assert is_short, f"Response is too long: {response}"
    assert 'no' in response.lower(), f"Expected 'no' in response for false statement but got: {response}"

@pytest.mark.slow
def test_llm_ambiguous_question(llm, yes_no_prompt):
    """Test that the LLM handles ambiguous questions appropriately."""
    response = ask_question(llm, yes_no_prompt, "Can spaceships travel faster than light?")
    # Just check it's short, allow any one-word answer
    assert len(response.split()) <= 1, f"Expected single word but got: {response}"

@pytest.mark.slow
def test_battery_of_questions(llm, yes_no_prompt):
    """Run through a battery of YES/NO questions and check responses."""
    questions = [
        # Definite facts
        ("Is Earth a planet?", "yes"),
        ("Do most spacecraft use chemical rockets?", ["yes", "no"]),  # Allow either response
        ("Can humans survive in space without a spacesuit?", "no"),
        ("Is orbital mechanics a field of physics?", "yes")
    ]
    
    for question, expected in questions:
        response = ask_question(llm, yes_no_prompt, question)
        has_yes_no, is_short = check_response_format(response)
        
        assert has_yes_no, f"Response doesn't contain 'yes' or 'no': {response}"
        assert is_short, f"Response is too long: {response}"
        
        # For more definite questions, check the specific answer
        if isinstance(expected, str):
            assert expected in response.lower(), f"For '{question}', expected '{expected}' but got: '{response}'"
        else:
            # For questions with multiple acceptable answers, check that one matches
            assert any(exp in response.lower() for exp in expected), \
                f"For '{question}', expected one of {expected} but got: '{response}'"

# Add a pytest configuration to register the 'slow' marker
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )

# Keep the main function for manual testing outside of pytest
def main():
    """Run the tests manually outside of pytest."""
    llm_instance = LLMService(model_name="qwen2.5:0.5b", quiet_mode=True)
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
        "Can spaceships travel faster than light?"
    ]
    
    for question in questions:
        response = ask_question(llm_instance, prompt, question)
        print(f"Q: {question}")
        print(f"A: {response}")
        print("-" * 50)

if __name__ == "__main__":
    main()

def test_json_dialogue_generation(self):
    """Test that the JSON dialogue path works correctly."""
    from mysite.universe.services.llm_service import LLMJSONService
    from mysite.universe.models.actor import Pilot, Controller, Role
    from mysite.universe.schemas.dialogue_schema import DialogueMessage, DialogueFormat
    import json

    # Create test actors
    pilot = Pilot.create(name="TEST PILOT")
    controller = Controller.create(name="TEST CONTROL")

    # Initialize service
    service = LLMJSONService(quiet_mode=True)

    # Test pilot -> controller dialogue
    context = ["TEST PILOT: TEST CONTROL, requesting clearance for plane change maneuver."]
    nav_ctx = {
        "maneuver": "PLANE_CHANGE",
        "current_location": "EARTH ORBIT",
        "destination": "MARS",
        "recipient": "TEST CONTROL"
    }

    # Generate response
    response = service.get_actor_text(
        line="",
        actor=controller,
        context=context,
        navigation_context=nav_ctx
    )

    # Verify response is valid JSON and matches schema
    self.assertTrue(isinstance(response, str))
    self.assertTrue(response.strip().startswith('{'))
    
    # Should parse without error
    msg_obj = None
    try:
        msg_obj = DialogueMessage(**json.loads(response))
    except Exception as e:
        self.fail(f"Failed to parse JSON response: {e}")

    # Verify required fields
    self.assertEqual(msg_obj.role, Role.CONTROLLER.value)
    self.assertEqual(msg_obj.speaker_callsign, controller.name)
    self.assertEqual(msg_obj.recipient_callsign, pilot.name)
    self.assertTrue(isinstance(msg_obj.format, DialogueFormat))
    self.assertTrue(isinstance(msg_obj.message, str))
    self.assertTrue(isinstance(msg_obj.requires_readback, bool))
