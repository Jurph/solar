"""
Defines the JSON schemas and validation utilities for the dialogue system.

This module provides the schema definitions for structured dialogue between
pilots and controllers, ensuring consistent format and role adherence.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, model_validator, ConfigDict
import json


class Role(str, Enum):
    """Defines the possible roles in space traffic communications."""
    PILOT = "PILOT"
    CONTROLLER = "CONTROLLER"
    SATELLITE = "SATELLITE"


class DialogueMessage(BaseModel):
    """A single message in a dialogue exchange."""
    role: Role
    speaker_callsign: str = Field(..., description="The callsign of the speaking actor")
    recipient_callsign: str = Field(..., description="The callsign of the intended recipient")
    message: str
    
    model_config = ConfigDict(validate_assignment=True)
    
    @model_validator(mode='after')
    def validate_message_format(self) -> 'DialogueMessage':
        """
        Validates the critical safety requirements of messages:
        1. Message must not be empty
        2. Both parties must be identified in the message (allowing shortened forms)
        
        Runs after all fields are validated and converted to their proper types.
        """
        if not self.message.strip():
            raise ValueError("Message cannot be empty")
            
        # Access fields from the model instance (all fields are validated and converted)
        speaker = self.speaker_callsign.replace('_', ' ')
        recipient = self.recipient_callsign.replace('_', ' ')
        msg_role = self.role
        
        # Get all possible parts of callsigns for matching
        speaker_parts = speaker.upper().split()
        recipient_parts = recipient.upper().split()
        
        # For controllers, also allow generic "Control" or "Control here"
        if msg_role == Role.CONTROLLER:
            speaker_parts.extend(["CONTROL", "CONTROL HERE"])
            
        # Find earliest position where any part of each callsign appears
        msg_upper = self.message.upper()
        speaker_pos = min((msg_upper.find(part) for part in speaker_parts if part in msg_upper), default=-1)
        recipient_pos = min((msg_upper.find(part) for part in recipient_parts if part in msg_upper), default=-1)
        
        # For ongoing dialogue, allow shortened forms (first word of multi-word callsigns)
        if speaker_pos == -1 and len(speaker_parts) > 1:
            speaker_pos = msg_upper.find(speaker_parts[0])
        if recipient_pos == -1 and len(recipient_parts) > 1:
            recipient_pos = msg_upper.find(recipient_parts[0])
        
        # Validate both parties are mentioned (in some form)
        if speaker_pos == -1:
            raise ValueError(f"Message must include speaker identification (any part of {speaker})")
        if recipient_pos == -1:
            raise ValueError(f"Message must include recipient identification (any part of {recipient})")
            
        return self


class DialogueContext(BaseModel):
    """Context information for the current dialogue exchange."""
    maneuver_type: str = Field(..., description="The type of maneuver being performed")
    current_location: str = Field(..., description="Current location of the ship")
    destination: str = Field(..., description="Destination of the ship")
    cargo: Optional[str] = Field(None, description="Cargo being carried, if any")
    previous_exchanges: List[DialogueMessage] = Field(default_factory=list, description="Recent message history")

    model_config = ConfigDict(validate_assignment=True)


class DialoguePrompt(BaseModel):
    """The complete dialogue prompt structure."""
    role: Role
    context: DialogueContext
    example_exchange: Optional[List[DialogueMessage]] = None
    
    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [{
                "role": "CONTROLLER",
                "context": {
                    "maneuver_type": "ORBITAL_INSERTION",
                    "current_location": "Mars Orbit",
                    "destination": "Phobos Station",
                    "cargo": "Medical Supplies",
                    "previous_exchanges": [
                        {
                            "role": "PILOT",
                            "speaker_callsign": "WICKER BASKET",
                            "recipient_callsign": "PHOBOS CONTROL",
                            "message": "PHOBOS CONTROL, this is WICKER BASKET, requesting clearance for orbital insertion."
                        }
                    ]
                },
                "example_exchange": [
                    {
                        "role": "CONTROLLER",
                        "speaker_callsign": "PHOBOS CONTROL",
                        "recipient_callsign": "WICKER BASKET",
                        "message": "WICKER BASKET, PHOBOS CONTROL here. Cleared for orbital insertion, maintain current vector."
                    },
                    {
                        "role": "PILOT",
                        "speaker_callsign": "WICKER BASKET",
                        "recipient_callsign": "PHOBOS CONTROL",
                        "message": "PHOBOS CONTROL, WICKER BASKET. Cleared for orbital insertion, maintaining current vector."
                    }
                ]
            }]
        }
    )


def validate_dialogue_sequence(messages: List[DialogueMessage]) -> bool:
    """
    Validates a sequence of dialogue messages for proper protocol adherence.
    
    Args:
        messages: List of DialogueMessage objects to validate
        
    Returns:
        bool: True if the sequence is valid
        
    Raises:
        ValueError: If any message fails validation or protocol is violated
    """
    if not messages:
        return True
        
    for i, msg in enumerate(messages):
        # Individual message validation happens automatically via model_validator
        # when the DialogueMessage is created. No need to manually validate here.
        
        # Check for proper response sequence
        if i > 0:
            prev_msg = messages[i-1]
            
            # Validate speaker/recipient alternation
            if msg.speaker_callsign != prev_msg.recipient_callsign:
                raise ValueError(f"Message {i} speaker should be previous message's recipient")
                
            if msg.recipient_callsign != prev_msg.speaker_callsign:
                raise ValueError(f"Message {i} recipient should be previous message's speaker")
    
    return True


def create_dialogue_prompt(role: Role, context: Dict) -> DialoguePrompt:
    """
    Creates a properly formatted dialogue prompt from the given parameters.
    
    Args:
        role: The role of the actor who will speak next
        context: Dictionary containing context information
        
    Returns:
        DialoguePrompt: A validated prompt object
    """
    # Convert the context dict to a DialogueContext object
    dialogue_context = DialogueContext(**context)
    
    # Create and validate the prompt
    prompt = DialoguePrompt(
        role=role,
        context=dialogue_context
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