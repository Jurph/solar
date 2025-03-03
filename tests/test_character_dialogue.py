"""
Test for the new character-based dialogue features in the LLM service.
This demonstrates how to use the LLM service to generate in-character
dialogue for pilots and controllers.
"""

import pytest
from mysite.universe.services.llm_service import LLMService

@pytest.fixture
def llm():
    """Fixture that provides an LLM service instance."""
    return LLMService(model_name="qwen2.5:0.5b")

@pytest.mark.slow
def test_controller_dialogue(llm):
    """Test generating controller dialogue with personality traits."""
    controller_prompt = llm.build_controller_prompt(
        controller_name="Mars Orbital Control",
        controller_location="Mars Orbit",
        personality_traits=["experienced", "cautious", "detail-oriented"]
    )
    
    # Example incoming message from a pilot
    incoming_message = "Mars Orbital Control, this is Cargo Vessel Hermes requesting landing vector for Olympus City."
    
    # Generate a response from the controller
    response = llm.generate_with_system_prompt(
        user_message=f"Respond to this incoming transmission: \"{incoming_message}\"",
        system_prompt=controller_prompt,
        temperature=0.7,
        max_tokens=150
    )
    
    print(f"\nController prompt: {controller_prompt[:100]}...\n")
    print(f"Incoming message: {incoming_message}")
    print(f"Controller response: {response}")
    
    # Basic validation
    assert "Hermes" in response, "Response should mention the ship name"
    assert len(response) > 20, "Response should be substantial"

@pytest.mark.slow
def test_pilot_dialogue(llm):
    """Test generating pilot dialogue with ship and mission context."""
    pilot_prompt = llm.build_pilot_prompt(
        pilot_name="Captain Sarah Chen",
        ship_name="Hermes",
        ship_class="Class II Cargo Vessel",
        cargo="Medical supplies and research equipment",
        current_location="Mars orbit",
        destination="Olympus City, Mars",
        personality_traits=["experienced", "efficient", "calm under pressure"]
    )
    
    # Example incoming message from a controller
    incoming_message = "Hermes, this is Mars Orbital Control. You're cleared for landing approach to Olympus City. Follow descent corridor Echo-7, winds are 15 knots northeasterly."
    
    # Generate a response from the pilot
    response = llm.generate_with_system_prompt(
        user_message=f"Respond to this incoming transmission: \"{incoming_message}\"",
        system_prompt=pilot_prompt,
        temperature=0.7,
        max_tokens=150
    )
    
    print(f"\nPilot prompt: {pilot_prompt[:100]}...\n")
    print(f"Incoming message: {incoming_message}")
    print(f"Pilot response: {response}")
    
    # Basic validation
    assert "Echo-7" in response or "corridor" in response, "Response should acknowledge instructions"
    assert len(response) > 20, "Response should be substantial"

@pytest.mark.slow
def test_pilot_greeting(llm):
    """Test generating a pilot's initial greeting."""
    greeting = llm.build_pilot_greeting(
        pilot_name="Captain Lee Rodriguez",
        ship_name="Pathfinder",
        controller_name="Earth Orbital Control",
        maneuver="departure",
        cargo="Agricultural equipment and seeds for Mars Colony"
    )
    
    print(f"\nPilot greeting: {greeting}")
    
    # Basic validation
    assert "Earth Orbital Control" in greeting, "Greeting should address the controller"
    assert "Pathfinder" in greeting, "Greeting should mention the ship name"
    assert "departure" in greeting.lower() or "clearance" in greeting.lower(), "Greeting should mention the maneuver or clearance"

@pytest.mark.slow
def test_character_conversation_flow(llm):
    """Test a complete back-and-forth conversation between characters."""
    # Initial setup
    pilot_name = "Captain Alex Morgan"
    ship_name = "Stellar Horizon"
    controller_name = "Luna Base Control"
    
    # Step 1: Pilot initial greeting
    pilot_greeting = llm.build_pilot_greeting(
        pilot_name=pilot_name,
        ship_name=ship_name,
        controller_name=controller_name,
        maneuver="docking",
        cargo="Scientific equipment and personnel rotation"
    )
    print(f"\n--- Conversation Start ---")
    print(f"{ship_name}: {pilot_greeting}")
    
    # Step 2: Controller response
    controller_response = llm.generate_in_character_response(
        character_type="controller",
        incoming_message=pilot_greeting,
        controller_name=controller_name,
        controller_location="Lunar orbit"
    )
    print(f"{controller_name}: {controller_response}")
    
    # Step 3: Pilot response to controller
    pilot_response = llm.generate_in_character_response(
        character_type="pilot",
        incoming_message=controller_response,
        pilot_name=pilot_name,
        ship_name=ship_name,
        ship_class="Research Vessel",
        cargo="Scientific equipment and personnel rotation",
        current_location="Lunar approach vector",
        destination="Luna Base"
    )
    print(f"{ship_name}: {pilot_response}")
    
    # Step 4: Final controller response
    final_controller_response = llm.generate_in_character_response(
        character_type="controller",
        incoming_message=pilot_response,
        controller_name=controller_name,
        controller_location="Lunar orbit"
    )
    print(f"{controller_name}: {final_controller_response}")
    print(f"--- Conversation End ---\n")
    
    # Basic validation of conversation flow
    assert len(pilot_greeting) > 0
    assert len(controller_response) > 0
    assert len(pilot_response) > 0
    assert len(final_controller_response) > 0

if __name__ == "__main__":
    # This allows running the test directly with Python
    import sys
    
    # Create LLM instance
    test_llm = LLMService()
    
    # Run all tests
    test_controller_dialogue(test_llm)
    test_pilot_dialogue(test_llm)
    test_pilot_greeting(test_llm)
    test_character_conversation_flow(test_llm)
    
    print("\nAll character dialogue tests completed successfully!")
    sys.exit(0) 