"""
Unit tests for DialogueMessage validation logic.

Tests the validate_message_format() function to understand what dialogue
is being accepted or rejected, and whether the validation is too strict.
"""
import pytest
from mysite.universe.schemas.dialogue_schema import (
    DialogueMessage,
    DialogueFormat,
    Role,
    ValidationInfo,
)


class TestDialogueMessageValidation:
    """Test cases for DialogueMessage validation."""
    
    def test_valid_initial_contact_with_both_callsigns(self):
        """Test that initial contact with both callsigns passes validation."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            format=DialogueFormat.INITIAL_CONTACT,
            message="MARS CONTROL, this is STELLAR HORIZON, requesting clearance for launch.",
            requires_readback=False
        )
        # Should not raise
        assert msg.message == "MARS CONTROL, this is STELLAR HORIZON, requesting clearance for launch."
    
    def test_valid_initial_contact_recipient_before_speaker(self):
        """Test that initial contact requires recipient before speaker."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            format=DialogueFormat.INITIAL_CONTACT,
            message="MARS CONTROL, STELLAR HORIZON here. Requesting clearance.",
            requires_readback=False
        )
        # Should not raise
        assert msg.message
    
    def test_invalid_initial_contact_speaker_before_recipient(self):
        """Test that initial contact fails if speaker comes before recipient."""
        with pytest.raises(ValueError, match="Initial contact must address"):
            DialogueMessage(
                role=Role.PILOT,
                speaker_callsign="STELLAR HORIZON",
                recipient_callsign="MARS CONTROL",
                format=DialogueFormat.INITIAL_CONTACT,
                message="STELLAR HORIZON here, MARS CONTROL. Requesting clearance.",
                requires_readback=False
            )
    
    def test_valid_response_with_both_callsigns(self):
        """Test that response with both callsigns passes validation."""
        msg = DialogueMessage(
            role=Role.CONTROLLER,
            speaker_callsign="MARS CONTROL",
            recipient_callsign="STELLAR HORIZON",
            format=DialogueFormat.RESPONSE,
            message="STELLAR HORIZON, MARS CONTROL. Cleared for launch, proceed.",
            requires_readback=True
        )
        # Should not raise
        assert msg.message
    
    def test_valid_acknowledgment_with_both_callsigns(self):
        """Test that acknowledgment with both callsigns passes validation."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            format=DialogueFormat.ACKNOWLEDGMENT,
            message="MARS CONTROL, STELLAR HORIZON. Roger, proceeding.",
            requires_readback=False
        )
        # Should not raise
        assert msg.message
    
    def test_acknowledgment_without_explicit_speaker(self):
        """Test if acknowledgment without explicit speaker identification fails."""
        # This might be too strict - "Roger, proceeding" is valid radio protocol
        with pytest.raises(ValueError, match="speaker identification"):
            DialogueMessage(
                role=Role.PILOT,
                speaker_callsign="STELLAR HORIZON",
                recipient_callsign="MARS CONTROL",
                format=DialogueFormat.ACKNOWLEDGMENT,
                message="MARS CONTROL, roger, proceeding.",
                requires_readback=False
            )
    
    def test_acknowledgment_without_explicit_recipient(self):
        """Test if acknowledgment without explicit recipient identification fails."""
        # This might be too strict - "Roger, proceeding" is valid radio protocol
        with pytest.raises(ValueError, match="recipient identification"):
            DialogueMessage(
                role=Role.PILOT,
                speaker_callsign="STELLAR HORIZON",
                recipient_callsign="MARS CONTROL",
                format=DialogueFormat.ACKNOWLEDGMENT,
                message="STELLAR HORIZON, roger, proceeding.",
                requires_readback=False
            )
    
    def test_shortened_callsigns_accepted(self):
        """Test that shortened callsigns (first word) are accepted."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            format=DialogueFormat.ACKNOWLEDGMENT,
            message="MARS, STELLAR. Roger, proceeding.",
            requires_readback=False
        )
        # Should not raise - shortened forms are allowed
        assert msg.message
    
    def test_controller_generic_control_accepted(self):
        """Test that controllers can use generic 'Control' or 'Control here'."""
        msg = DialogueMessage(
            role=Role.CONTROLLER,
            speaker_callsign="MARS CONTROL",
            recipient_callsign="STELLAR HORIZON",
            format=DialogueFormat.RESPONSE,
            message="STELLAR HORIZON, Control here. Cleared for launch.",
            requires_readback=True
        )
        # Should not raise - "Control" is accepted for controllers
        assert msg.message
    
    def test_readback_with_both_callsigns(self):
        """Test that readback with both callsigns passes validation."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            format=DialogueFormat.READBACK,
            message="MARS CONTROL, STELLAR HORIZON. Cleared for launch, proceeding.",
            requires_readback=False
        )
        # Should not raise
        assert msg.message
    
    def test_empty_message_rejected(self):
        """Test that empty message is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            DialogueMessage(
                role=Role.PILOT,
                speaker_callsign="STELLAR HORIZON",
                recipient_callsign="MARS CONTROL",
                format=DialogueFormat.ACKNOWLEDGMENT,
                message="   ",  # Whitespace only
                requires_readback=False
            )
    
    def test_case_insensitive_callsign_matching(self):
        """Test that callsign matching is case-insensitive."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR HORIZON",
            recipient_callsign="MARS CONTROL",
            format=DialogueFormat.ACKNOWLEDGMENT,
            message="mars control, stellar horizon. Roger.",
            requires_readback=False
        )
        # Should not raise - case insensitive
        assert msg.message
    
    def test_underscores_in_callsigns_handled(self):
        """Test that underscores in callsigns are converted to spaces for matching."""
        msg = DialogueMessage(
            role=Role.PILOT,
            speaker_callsign="STELLAR_HORIZON",
            recipient_callsign="MARS_CONTROL",
            format=DialogueFormat.ACKNOWLEDGMENT,
            message="MARS CONTROL, STELLAR HORIZON. Roger.",
            requires_readback=False
        )
        # Should not raise - underscores converted to spaces
        assert msg.message
    
    def test_natural_acknowledgment_patterns(self):
        """Test common natural acknowledgment patterns that might be rejected."""
        test_cases = [
            # Pattern: "Roger, proceeding" - might not mention both callsigns
            ("MARS CONTROL, roger, proceeding.", True),  # Has recipient, missing speaker
            ("Roger, proceeding.", False),  # Missing both
            ("STELLAR HORIZON, roger.", True),  # Has speaker, missing recipient
            
            # Pattern: "Copy that" - very brief
            ("MARS CONTROL, copy that.", True),  # Has recipient, missing speaker
            ("Copy that.", False),  # Missing both
            
            # Pattern: "Understood" - brief acknowledgment
            ("MARS CONTROL, understood.", True),  # Has recipient, missing speaker
            ("Understood, proceeding.", False),  # Missing both
        ]
        
        for message, should_pass in test_cases:
            if should_pass:
                # Should raise ValueError for missing identification
                with pytest.raises(ValueError):
                    DialogueMessage(
                        role=Role.PILOT,
                        speaker_callsign="STELLAR HORIZON",
                        recipient_callsign="MARS CONTROL",
                        format=DialogueFormat.ACKNOWLEDGMENT,
                        message=message,
                        requires_readback=False
                    )
            else:
                # Should definitely raise ValueError
                with pytest.raises(ValueError):
                    DialogueMessage(
                        role=Role.PILOT,
                        speaker_callsign="STELLAR HORIZON",
                        recipient_callsign="MARS CONTROL",
                        format=DialogueFormat.ACKNOWLEDGMENT,
                        message=message,
                        requires_readback=False
                    )

