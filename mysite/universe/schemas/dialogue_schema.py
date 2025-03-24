"""
Defines the JSON schemas and validation utilities for the dialogue system.

This module provides the schema definitions for structured dialogue between
pilots and controllers, ensuring consistent format and role adherence.
"""

from enum import Enum
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
import json


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
        2. Both parties must be identified in the message (allowing shortened forms)
        3. For INITIAL_CONTACT only: recipient must be addressed before speaker
        """
        values = info.data
        if not v.strip():
            raise ValueError("Message cannot be empty")
            
        # Convert callsigns to possible spoken variations
        speaker = values['speaker_callsign'].replace('_', ' ')
        recipient = values['recipient_callsign'].replace('_', ' ')
        
        # Get all possible parts of callsigns for matching
        speaker_parts = speaker.upper().split()
        recipient_parts = recipient.upper().split()
        
        # For controllers, also allow generic "Control" or "Control here"
        if values['role'] == Role.CONTROLLER:
            speaker_parts.extend(["CONTROL", "CONTROL HERE"])
            
        # Find earliest position where any part of each callsign appears
        v_upper = v.upper()
        speaker_pos = min((v_upper.find(part) for part in speaker_parts if part in v_upper), default=-1)
        recipient_pos = min((v_upper.find(part) for part in recipient_parts if part in v_upper), default=-1)
        
        # For ongoing dialogue, allow shortened forms (first word of multi-word callsigns)
        if speaker_pos == -1 and len(speaker_parts) > 1:
            speaker_pos = v_upper.find(speaker_parts[0])
        if recipient_pos == -1 and len(recipient_parts) > 1:
            recipient_pos = v_upper.find(recipient_parts[0])
        
        # Validate both parties are mentioned (in some form)
        if speaker_pos == -1:
            raise ValueError(f"Message must include speaker identification (any part of {speaker})")
        if recipient_pos == -1:
            raise ValueError(f"Message must include recipient identification (any part of {recipient})")
            
        # Only enforce recipient-before-speaker order for initial contact
        if values['format'] == DialogueFormat.INITIAL_CONTACT and speaker_pos < recipient_pos:
            raise ValueError(f"Initial contact must address {recipient} before {speaker} identifies themselves")
            
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
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "role": "CONTROLLER",
                "context": {
                    "current_location": "Mars Orbit",
                    "destination": "Phobos Station",
                    "cargo": "Medical Supplies",
                    "previous_exchanges": [
                        {
                            "role": "PILOT",
                            "speaker_callsign": "WICKER BASKET",
                            "recipient_callsign": "PHOBOS CONTROL",
                            "format": "INITIAL_CONTACT",
                            "message": "Phobos Control, this is Wicker Basket, <contextually appropriate request for a maneuver>.",
                            "requires_readback": False
                        }
                    ]
                },
                "expected_format": "RESPONSE",
                "example_exchange": [
                    {
                        "role": "CONTROLLER",
                        "speaker_callsign": "PHOBOS CONTROL",
                        "recipient_callsign": "WICKER BASKET",
                        "format": "RESPONSE",
                        "message": "Wicker Basket, Phobos Control here. <OPTIONAL course correction>, <contextually appropriate approval for maneuver>.",
                        "requires_readback": True
                    },
                    {
                        "role": "PILOT",
                        "speaker_callsign": "WICKER BASKET",
                        "recipient_callsign": "PHOBOS CONTROL",
                        "format": "READBACK",
                        "message": "Phobos Control, Wicker Basket, thank you. <Acknowledgement of instructions>. <OPTIONAL confirmation of course correction>. <OPTIONAL small talk>",
                        "requires_readback": False
                    }
                ]
            }
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


def get_schema_and_rules() -> str:
    """Returns a formatted string containing the schema and critical rules."""
    return f"""DIALOGUE SCHEMA AND RULES:
{json.dumps(DialogueMessage.model_json_schema(), indent=2)}

CRITICAL SAFETY RULES:
1. Your message MUST include both speaker and recipient identification
2. For initial contact, you MUST address recipient before identifying yourself
3. Keep messages clear, concise, and professional
4. Include readback requirements for any vectors, headings, or critical instructions

COMMUNICATION FORMATS:
- INITIAL_CONTACT: First message in an exchange
- RESPONSE: Reply to a message
- ACKNOWLEDGMENT: Confirm receipt
- READBACK: Repeat instructions back
- HANDOFF: Transfer to another controller""" 