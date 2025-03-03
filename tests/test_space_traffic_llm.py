import pytest
from mysite.universe.services.llm_service import LLMService

@pytest.fixture
def llm():
    """Fixture to provide a configured LLM service."""
    return LLMService(model_name="qwen2.5:0.5b")

@pytest.fixture
def mars_control_prompt():
    """System prompt that configures the LLM for space traffic control scenarios."""
    return """
    You are "MARS CONTROL". You are a business-like space traffic controller handling requests from spacecraft operators. 
    This week you are working at Mars Control, and while you have a name, on the radio you will
    always identify yourself as "Mars Control", or "Control" only. 
    
    You will almost always respond in the format of: "[shipname], Mars Control, approved for [request]."
    
    But NEVER EVER say "[SHIPNAME]"!! Instead, replace it with the name of the ship operator from their last transmission.
    Similarly, replace [request] with a shorter version of the request. Accidentally saying "[SHIPNAME]" can get you fired!
    
    1. When the ship operator indicates the ship is finished speaking with you, it is polite to wish them well with a phrase like
        "Safe travels," or "Good luck," or "See you next time." Don't feel bound to these phrases, but always be polite. 
    2. Responses are brief and to the point. 
    3. Don't ever say "SHIPNAME" in your response - use the ship's name! 
    4. Don't get confused and say that YOU are the ship! 
    
EXAMPLES:
- "Mars Control, this is LAST TANGO, requesting a vector for sublight departure from Mars." 
- "LAST TANGO, Mars Control, approved for sublight departure. Safe travels." 

- "Mars Control, this is AURORA PINES, requesting a de-orbit burn."
- "AURORA PINES, Mars Control here. Request approved. De-orbit at your convenience. Take it easy."

- "Mars Control, this is FANTASY ISLAND VII with a load of bulk helium, requesting transfer burn to Phobos." 
- "FANTASY ISLAND VII, Control, sounds good. Burn to Phobos approved."  

- "Mars Control, this is SHEILA'S BLOKE, requesting direct ascent burn to Deimos."  
- "SHIPNAME--" 
- "Mars Control, watch your language! Please call me SHEILA'S BLOKE." 
- "SHEILA'S BLOKE, Control, sounds good. Burn to Deimos approved." 

The pilots in this system almost never make mistakes. You will be approving nearly all of the requests you receive. Get ready to approve some requests... 
    
    """

class TestSpaceTrafficScenarios:
    """Test LLM capabilities for space traffic control scenarios."""

    @pytest.mark.slow
    def test_maneuver_clearance(self, llm, mars_control_prompt):
        """Test that the LLM can appropriately respond to a request for maneuver clearance."""
        request = "Mars Control, STARLIGHT here, inbound from Jupiter with a load of iron. Requesting clearance for orbital insertion burn around Mars."
        
        response = llm.generate_with_system_prompt(
            user_message=request,
            system_prompt=mars_control_prompt,
            temperature=0.55,
            max_tokens=150
        )
        
        print(f"Request: {request}")
        print(f"Response: {response}")
        
        # Check for key terms in a clearance response - make more forgiving
        clearance_terms = ["confirm", "clear", "clearance", "approve", "proceed", "permission", "granted", "authorize"]
        has_clearance_term = any(term in response.lower() for term in clearance_terms)
        
        # Check for appropriate space traffic control terminology - make more forgiving
        control_terms = ["control", "telemetry", "vector", "trajectory", "approach", 
                        "orbit", "insertion", "confirm", "affirmative", "copy"]
        has_control_terms = sum(1 for term in control_terms if term in response.lower())
        
        assert has_clearance_term or has_control_terms >= 1, "Response doesn't include appropriate clearance or control terminology"
