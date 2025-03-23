"""
Defines the JSON schemas and validation utilities for the dialogue system.

This module provides the schema definitions for structured dialogue between
pilots and controllers, ensuring consistent format and role adherence.
"""

from enum import Enum
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class Role(str, Enum):
    """Defines the possible roles in space traffic communications."""
    PILOT = "PILOT"
    CONTROLLER = "CONTROLLER"
    SATELLITE = "SATELLITE"


class DialogueFormat(str, Enum):
    """Standard formats for space traffic control communications."""
    INITIAL_CONTACT = "INITIAL_CONTACT"  # First contact in an exchange
    RESPONSE = "RESPONSE"  # Response to a contact
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"  # Confirming receipt
    READBACK = "READBACK"  # Repeating instructions
    HANDOFF = "HANDOFF"  # Transferring to another controller


class DialogueMessage(BaseModel):
    """A single message in a dialogue exchange."""
    role: Role
    speaker_callsign: str = Field(..., description="The callsign of the speaking actor")
    recipient_callsign: str = Field(..., description="The callsign of the intended recipient")
    format: DialogueFormat
    message: str
    requires_readback: bool = Field(default=False, description="Whether this message requires verbal confirmation")
    
    @field_validator('message')
    @classmethod
    def validate_message_format(cls, v: str, info) -> str:
        """
        Validates the critical safety requirements of messages:
        1. Message must not be empty
        2. Both parties must be identified in the message
        3. Recipient must be addressed before speaker identifies themselves
        """
        values = info.data
        if not v.strip():
            raise ValueError("Message cannot be empty")
            
        # Convert callsigns to possible spoken variations
        speaker = values['speaker_callsign'].replace('_', ' ')
        recipient = values['recipient_callsign'].replace('_', ' ')
        
        # Find the earliest mention of each party
        speaker_parts = speaker.upper().split()
        recipient_parts = recipient.upper().split()
        
        # Find earliest position where any part of each callsign appears
        v_upper = v.upper()
        speaker_pos = min((v_upper.find(part) for part in speaker_parts if part in v_upper), default=-1)
        recipient_pos = min((v_upper.find(part) for part in recipient_parts if part in v_upper), default=-1)
        
        # Validate both parties are mentioned
        if speaker_pos == -1:
            raise ValueError(f"Message must include speaker identification ({speaker})")
        if recipient_pos == -1:
            raise ValueError(f"Message must include recipient identification ({recipient})")
            
        # Validate recipient is addressed before speaker identifies themselves
        if speaker_pos < recipient_pos:
            raise ValueError(f"Message must address {recipient} before {speaker} identifies themselves")
            
        return v


class DialogueContext(BaseModel):
    """Context information for the current dialogue exchange."""
    maneuver_type: str = Field(..., description="The type of maneuver being performed")
    current_location: str = Field(..., description="Current location of the ship")
    destination: str = Field(..., description="Destination of the ship")
    cargo: Optional[str] = Field(None, description="Cargo being carried, if any")
    previous_exchanges: List[DialogueMessage] = Field(default_factory=list, description="Recent message history")


class DialoguePrompt(BaseModel):
    """The complete dialogue prompt structure."""
    role: Role
    context: DialogueContext
    expected_format: DialogueFormat
    example_exchange: Optional[List[DialogueMessage]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "role": "CONTROLLER",
                "context": {
                    "maneuver_type": "SUBLIGHT",
                    "current_location": "Mars Orbit",
                    "destination": "Phobos Station",
                    "cargo": "Medical Supplies",
                    "previous_exchanges": [
                        {
                            "role": "PILOT",
                            "speaker_callsign": "STELLAR_HORIZON",
                            "recipient_callsign": "PHOBOS_CONTROL",
                            "format": "INITIAL_CONTACT",
                            "message": "Phobos Control, this is Stellar Horizon, requesting approach vector for docking.",
                            "requires_readback": False
                        }
                    ]
                },
                "expected_format": "RESPONSE",
                "example_exchange": [
                    {
                        "role": "CONTROLLER",
                        "speaker_callsign": "PHOBOS_CONTROL",
                        "recipient_callsign": "STELLAR_HORIZON",
                        "format": "RESPONSE",
                        "message": "Stellar Horizon, Phobos Control. Cleared for approach on vector 120. Maintain current velocity.",
                        "requires_readback": True
                    },
                    {
                        "role": "PILOT",
                        "speaker_callsign": "STELLAR_HORIZON",
                        "recipient_callsign": "PHOBOS_CONTROL",
                        "format": "READBACK",
                        "message": "Phobos Control, Stellar Horizon. Vector 120, maintaining velocity. Wilco.",
                        "requires_readback": False
                    }
                ]
            }
        }


def validate_dialogue_sequence(messages: List[DialogueMessage]) -> bool:
    """
    Validates a sequence of dialogue messages for proper protocol adherence.
    
    Args:
        messages: List of DialogueMessage objects to validate
        
    Returns:
        bool: True if the sequence is valid, False otherwise
        
    Raises:
        ValueError: If any message fails validation
    """
    if not messages:
        return True
        
    for i, msg in enumerate(messages):
        # Validate individual message
        msg.validate_message_format(msg.message, {"format": msg.format, 
                                                "recipient_callsign": msg.recipient_callsign,
                                                "speaker_callsign": msg.speaker_callsign})
        
        # Check for proper response sequence
        if i > 0:
            prev_msg = messages[i-1]
            
            # Validate readback requirements
            if prev_msg.requires_readback:
                if msg.format != DialogueFormat.READBACK:
                    raise ValueError(f"Message {i} should be a readback of previous instructions")
                    
            # Validate speaker/recipient alternation
            if msg.speaker_callsign != prev_msg.recipient_callsign:
                raise ValueError(f"Message {i} speaker should be previous message's recipient")
                
            if msg.recipient_callsign != prev_msg.speaker_callsign:
                raise ValueError(f"Message {i} recipient should be previous message's speaker")
    
    return True


def create_dialogue_prompt(role: Role, context: Dict, expected_format: DialogueFormat) -> DialoguePrompt:
    """
    Creates a properly formatted dialogue prompt from the given parameters.
    
    Args:
        role: The role of the actor who will speak next
        context: Dictionary containing context information
        expected_format: The expected format of the next message
        
    Returns:
        DialoguePrompt: A validated prompt object
    """
    # Convert the context dict to a DialogueContext object
    dialogue_context = DialogueContext(**context)
    
    # Create and validate the prompt
    prompt = DialoguePrompt(
        role=role,
        context=dialogue_context,
        expected_format=expected_format
    )
    
    return prompt 