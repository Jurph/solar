"""Tests for the dialogue schema implementation."""
import pytest
from mysite.universe.schemas.dialogue_schema import (
    Role,
    DialogueFormat,
    DialogueMessage,
    DialogueContext,
    DialoguePrompt,
    validate_dialogue_sequence,
    create_dialogue_prompt,
)


def test_dialogue_message_validation():
    """Test that DialogueMessage validates format correctly."""
    # Valid initial contact
    valid_initial = DialogueMessage(
        role=Role.PILOT,
        speaker_callsign="STELLAR_HORIZON",
        recipient_callsign="MARS_CONTROL",
        format=DialogueFormat.INITIAL_CONTACT,
        message="MARS_CONTROL, this is STELLAR_HORIZON, requesting clearance for takeoff.",
    )
    assert valid_initial.message.startswith("MARS_CONTROL, this is STELLAR_HORIZON")

    # Invalid initial contact should raise error
    with pytest.raises(ValueError):
        DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR_HORIZON",
            recipient_callsign="MARS_CONTROL",
            format=DialogueFormat.INITIAL_CONTACT,
            message="Wrong format message",
        )

    # Valid response
    valid_response = DialogueMessage(
        role=Role.CONTROLLER,
        speaker_callsign="MARS_CONTROL",
        recipient_callsign="STELLAR_HORIZON",
        format=DialogueFormat.RESPONSE,
        message="STELLAR_HORIZON, MARS_CONTROL. Cleared for takeoff.",
        requires_readback=True,
    )
    assert valid_response.message.startswith("STELLAR_HORIZON, MARS_CONTROL")


def test_dialogue_sequence_validation():
    """Test that dialogue sequences are validated correctly."""
    # Create a valid sequence
    sequence = [
        DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR_HORIZON",
            recipient_callsign="MARS_CONTROL",
            format=DialogueFormat.INITIAL_CONTACT,
            message="MARS_CONTROL, this is STELLAR_HORIZON, requesting clearance for takeoff.",
        ),
        DialogueMessage(
            role=Role.CONTROLLER,
            speaker_callsign="MARS_CONTROL",
            recipient_callsign="STELLAR_HORIZON",
            format=DialogueFormat.RESPONSE,
            message="STELLAR_HORIZON, MARS_CONTROL. Cleared for takeoff.",
            requires_readback=True,
        ),
        DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR_HORIZON",
            recipient_callsign="MARS_CONTROL",
            format=DialogueFormat.READBACK,
            message="MARS_CONTROL, STELLAR_HORIZON. Cleared for takeoff, wilco.",
        ),
    ]
    
    assert validate_dialogue_sequence(sequence) is True

    # Test invalid sequence (missing readback)
    invalid_sequence = sequence[:2]  # Remove the readback message
    with pytest.raises(ValueError):
        validate_dialogue_sequence(invalid_sequence)


def test_dialogue_context():
    """Test that DialogueContext handles all required fields."""
    context = DialogueContext(
        maneuver_type="SUBLIGHT",
        current_location="Mars Orbit",
        destination="Phobos Station",
        cargo="Medical Supplies",
        previous_exchanges=[],
    )
    assert context.maneuver_type == "SUBLIGHT"
    assert context.cargo == "Medical Supplies"

    # Test optional cargo
    context_no_cargo = DialogueContext(
        maneuver_type="SUBLIGHT",
        current_location="Mars Orbit",
        destination="Phobos Station",
    )
    assert context_no_cargo.cargo is None


def test_create_dialogue_prompt():
    """Test creation of complete dialogue prompts."""
    context_dict = {
        "maneuver_type": "SUBLIGHT",
        "current_location": "Mars Orbit",
        "destination": "Phobos Station",
        "cargo": "Medical Supplies",
        "previous_exchanges": [],
    }
    
    prompt = create_dialogue_prompt(
        role=Role.CONTROLLER,
        context=context_dict,
        expected_format=DialogueFormat.RESPONSE,
    )
    
    assert prompt.role == Role.CONTROLLER
    assert prompt.context.maneuver_type == "SUBLIGHT"
    assert prompt.expected_format == DialogueFormat.RESPONSE


def test_dialogue_prompt_example():
    """Test that the example in schema_extra is valid."""
    schema = DialoguePrompt.model_json_schema()
    example = schema["examples"][0]  # Access first example from list
    prompt = DialoguePrompt(**example)
    assert prompt.role == Role.CONTROLLER
    assert len(prompt.context.previous_exchanges) == 1
    assert len(prompt.example_exchange) == 2 