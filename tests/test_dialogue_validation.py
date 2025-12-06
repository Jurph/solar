"""
Unit tests for DialogueMessage validation logic.

Tests the validate_message_format() function to understand what dialogue
is being accepted or rejected by the current validation rules.
"""
import pytest
from mysite.universe.schemas.dialogue_schema import (
    DialogueMessage,
    Role,
)


class TestDialogueMessageValidation:
    """Test cases for DialogueMessage validation."""
    
    def test_valid_message_with_both_callsigns(self):
        """Test that message with both callsigns passes validation."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            message="MARS CONTROL, this is STELLAR HORIZON, requesting clearance for launch.",
        )
        # Should not raise
        assert msg.message == "MARS CONTROL, this is STELLAR HORIZON, requesting clearance for launch."
    
    def test_valid_response_with_both_callsigns(self):
        """Test that response with both callsigns passes validation."""
        msg = DialogueMessage(
            role=Role.CONTROLLER,
            speaker_callsign="MARS CONTROL",
            recipient_callsign="STELLAR HORIZON",
            message="STELLAR HORIZON, MARS CONTROL. Cleared for launch, proceed.",
        )
        # Should not raise
        assert msg.message
    
    def test_message_without_explicit_speaker_fails(self):
        """Test that message without speaker identification fails."""
        with pytest.raises(ValueError, match="speaker identification"):
            DialogueMessage(
                role=Role.PILOT,
                speaker_callsign="STELLAR HORIZON",
                recipient_callsign="MARS CONTROL",
                message="MARS CONTROL, roger, proceeding.",
            )
    
    def test_message_without_explicit_recipient_fails(self):
        """Test that message without recipient identification fails."""
        with pytest.raises(ValueError, match="recipient identification"):
            DialogueMessage(
                role=Role.PILOT,
                speaker_callsign="STELLAR HORIZON",
                recipient_callsign="MARS CONTROL",
                message="STELLAR HORIZON here, roger, proceeding.",
            )
    
    def test_shortened_callsigns_accepted(self):
        """Test that shortened callsigns (first word) are accepted."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            message="MARS, STELLAR. Roger, proceeding.",
        )
        # Should not raise - shortened forms are allowed
        assert msg.message
    
    def test_controller_generic_control_accepted(self):
        """Test that controllers can use generic 'Control' or 'Control here'."""
        msg = DialogueMessage(
            role=Role.CONTROLLER,
            speaker_callsign="MARS CONTROL",
            recipient_callsign="STELLAR HORIZON",
            message="STELLAR HORIZON, Control here. Cleared for launch.",
        )
        # Should not raise - "Control" is accepted for controllers
        assert msg.message
    
    def test_empty_message_rejected(self):
        """Test that empty message is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            DialogueMessage(
                role=Role.PILOT,
                speaker_callsign="STELLAR HORIZON",
                recipient_callsign="MARS CONTROL",
                message="   ",  # Whitespace only
            )
    
    def test_case_insensitive_callsign_matching(self):
        """Test that callsign matching is case-insensitive."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            message="mars control, stellar horizon. Roger.",
        )
        # Should not raise - case insensitive
        assert msg.message
    
    def test_underscores_in_callsigns_handled(self):
        """Test that underscores in callsigns are converted to spaces for matching."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR_HORIZON",
            recipient_callsign="MARS_CONTROL",
            message="MARS CONTROL, STELLAR HORIZON. Roger.",
        )
        # Should not raise - underscores converted to spaces
        assert msg.message
