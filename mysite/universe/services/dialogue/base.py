"""
Base classes for dialogue particles.

Defines the abstract interface and data structures for building dialogue prompts
using a particle-based system. Each particle type (Request, Response, etc.) has
its own examples and prompt structure.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from mysite.universe.models.actor import Actor


class UserPromptData(BaseModel):
    """
    Structured user prompt data matching recommendations.txt format.
    
    This model defines the exact structure of user prompts sent to the LLM.
    All fields are required except optional placeholders for future physics data.
    
    Attributes:
        role: Role description like "Captain Rodriguez, the pilot of the STELLAR HORIZON"
        situation: Situation description like "STELLAR HORIZON is a ship intending to fly to Earth from Mars..."
        sender: Sender callsign like "STELLAR HORIZON"
        recipient: Recipient callsign like "MARS CONTROL"
        example1: First example dialogue line
        example2: Second example dialogue line
        example3: Third example dialogue line
        counterexample: Counterexample showing what NOT to do
        last_dialogue_line: Previous dialogue line (if any)
        altitude: Optional altitude placeholder (for future physics integration)
        inclination: Optional inclination placeholder (for future physics integration)
        speed: Optional speed placeholder (for future physics integration)
    """
    role: str = Field(..., description="Role description like 'Captain Rodriguez, the pilot of the STELLAR HORIZON'")
    situation: str = Field(..., description="Situation description from navigation context")
    sender: str = Field(..., description="Sender callsign (ship name for pilots, station name for controllers)")
    recipient: str = Field(..., description="Recipient callsign")
    example1: str = Field(..., description="First example dialogue line")
    example2: str = Field(..., description="Second example dialogue line")
    example3: str = Field(..., description="Third example dialogue line")
    counterexample: str = Field(..., description="Counterexample showing what NOT to do")
    last_dialogue_line: Optional[str] = Field(None, description="Previous dialogue line (N/A if none)")
    altitude: Optional[str] = Field(None, description="Altitude placeholder (for future physics integration)")
    inclination: Optional[str] = Field(None, description="Inclination placeholder (for future physics integration)")
    speed: Optional[str] = Field(None, description="Speed placeholder (for future physics integration)")
    
    model_config = {
        "json_schema_extra": {
            "description": "Structured user prompt data matching recommendations.txt format"
        }
    }


class DialogueParticle(ABC):
    """
    Abstract base class for all dialogue particles (Request, Response, Readback, etc.).
    
    Each particle type represents a specific dialogue exchange type (e.g., pilot request,
    controller response, pilot acknowledgment). Particles encapsulate:
    - Examples (1) Examples (5+ examples of this dialogue type)
    (2) Counterexamples (what NOT to do)
    (3) Role descriptions (how to describe the speaker)
    (4) Situation descriptions (context from navigation)
    (5) Examples and counterexamples
    
    The system prompt is static and shared across all particles. Only the user prompt
    changes based on the particle type and context.
    
    Usage:
        particle = LaunchRequest(actor=pilot, recipient="MARS CONTROL", nav_context={...})
        prompt_data = particle.build_user_prompt_data()
        user_prompt = particle.format_user_prompt(prompt_data)
    """
    
    # Static system prompt (same for all particles)
    SYSTEM_PROMPT: str = """Generate a message for a spaceflight simulator. 
You write concise and conversational dialogue that uses
the context of the scene and situation. Observe the
SITUATION, place yourself in the ROLE, and write a 
MESSAGE to the RECIPIENT. Protocol suggests that you address
the RECIPIENT first, then identify yourself (the SENDER), before 
sending the MESSAGE.

The MESSAGE almost always opens with the fixed text: "RECIPIENT, SENDER," but may vary slightly.  
After the rigid opening, you will need to be creative in constructing a valid and evocative MESSAGE field; those rules follow.  

"""
    
    def __init__(self, actor: Actor, recipient: str, nav_context: Dict[str, Any]):
        """
        Initialize a dialogue particle.
        
        Args:
            actor: The actor speaking (Pilot, Controller, etc.)
            recipient: The recipient callsign (e.g., "MARS CONTROL")
            nav_context: Navigation context dictionary with keys like:
                - maneuver_type: str (e.g., "launch", "circularize")
                - current_location: str (e.g., "Mars")
                - destination: str (e.g., "Earth")
                - origin: Optional[str]
                - ship_name: Optional[str]
                - pilot_name: Optional[str]
        """
        self.actor: Actor = actor
        self.recipient: str = recipient
        self.nav_context: Dict[str, Any] = nav_context
    
    @abstractmethod
    def get_examples(self) -> List[str]:
        """
        Return list of 5+ example dialogue lines for this particle type.
        
        Examples should be natural, conversational dialogue that demonstrates
        the correct format and style for this particle type. Examples will be
        randomly selected (typically 3) to provide variety.
        
        Returns:
            List of example dialogue strings. Must contain at least 5 examples.
        """
        pass
    
    @abstractmethod
    def get_counterexample(self) -> str:
        """
        Return a counterexample showing what NOT to do.
        
        Counterexamples help the LLM understand common mistakes to avoid.
        Should be prefixed with "[DON'T DO THIS!]" for clarity.
        
        Returns:
            Counterexample string showing incorrect dialogue.
        """
        pass
    
    @abstractmethod
    def get_role_description(self) -> str:
        """
        Return role description for the speaker.
        
        Format examples:
        - For pilots: "Captain Rodriguez, the pilot of the STELLAR HORIZON"
        - For controllers: "An anonymous space traffic control worker at MARS CONTROL"
        
        """
        pass
    
    @abstractmethod
    def get_situation_description(self) -> str:
        """
        Return situation description from nav_context.
        
        Should describe the current situation, what the speaker wants to do,
        and why they're communicating with the recipient.
        
        Returns:
            Situation description string built from nav_context.
        """
        pass
    
    
    def get_duration(self) -> float:
        """
        Return duration of this dialogue event (for event scheduling).
        
        Default: 2.0 seconds. Override in subclasses for longer events
        (e.g., hold responses might take 60 seconds).
        
        Returns:
            Duration in seconds.
        """
        return 2.0
    
    @abstractmethod
    def get_next_particle_probabilities(self) -> Dict[str, float]:
        """
        Return probabilities for what particle types can follow this one.
        
        Each particle defines what can come next and with what probability.
        Probabilities should sum to <= 1.0. If sum < 1.0, remaining probability
        represents chance that chain ends here.
        
        Returns:
            Dict mapping particle type strings to probabilities.
            Empty dict means chain always ends here.
            
        Example:
            {
                "response": 0.85,      # 85% chance of response
                "hold_response": 0.10,  # 10% chance of hold
                "gratitude": 0.05       # 5% chance of casual gratitude
            }
            # Sum = 1.0, so chain always continues
        """
        pass
    
    def get_delay_until_next(self) -> Optional[float]:
        """
        Return time delay until next event should occur.
        
        This is the gap/delay between this event and the next event.
        Default: 5.0 seconds. Override in subclasses for different timing
        (e.g., hold responses might have longer delays).
        
        Returns:
            Seconds until next event, or None if chain ends here.
            None is returned automatically if get_next_particle_probabilities()
            returns empty dict or probabilities sum to 0.
        """
        probs = self.get_next_particle_probabilities()
        if not probs or sum(probs.values()) == 0:
            return None
        return 5.0  # Default 5-second delay
    
    def select_examples(self, count: int = 3) -> List[str]:
        """
        Select N random examples from available examples.
        
        Args:
            count: Number of examples to select (default: 3)
            
        Returns:
            List of selected example strings. Returns all examples if count >= available.
        """
        import random
        examples = self.get_examples()
        if len(examples) <= count:
            return examples
        return random.sample(examples, count)
    
    def build_user_prompt_data(self, previous_dialogue: Optional[str] = None) -> UserPromptData:
        """
        Build the structured user prompt data.
        
        This method orchestrates the creation of UserPromptData by calling
        abstract methods to get role, situation, examples, etc. It selects
        3 random examples from the available examples.
        
        Args:
            previous_dialogue: Optional previous dialogue line text
            
        Returns:
            UserPromptData instance with all fields populated.
        """
        examples = self.select_examples(3)
        return UserPromptData(
            role=self.get_role_description(),
            situation=self.get_situation_description(),
            sender=self.get_sender_callsign(),
            recipient=self.recipient,
            example1=examples[0] if len(examples) > 0 else "",
            example2=examples[1] if len(examples) > 1 else "",
            example3=examples[2] if len(examples) > 2 else "",
            counterexample=self.get_counterexample(),
            last_dialogue_line=previous_dialogue,
        )
    
    def get_sender_callsign(self) -> str:
        """
        Get sender callsign (ship name for pilots, station name for controllers).
        
        Returns:
            Uppercase callsign string.
        """
        # Check actor role - Actor.role is stored as string, compare with enum value
        if hasattr(self.actor, 'role') and self.actor.role == Actor.Role.PILOT.value:
            # For pilots, use ship name as callsign
            if hasattr(self.actor, 'ship') and self.actor.ship:
                return self.actor.ship.name.upper()
        # For controllers or if no ship, use actor name
        return self.actor.name.upper()
    
    def generate_procedural_greeting(self) -> str:
        """
        Generate procedural greeting prefix for this particle type.
        
        Default pattern: "{recipient}, {sender}."
        Override in subclasses for different greeting patterns (e.g., "this is" for initial contact).
        
        Returns:
            Greeting string to prepend to message content.
        """
        sender = self.get_sender_callsign()
        recipient = self.recipient
        return f"{recipient}, {sender}."
    
    def format_user_prompt(self, data: UserPromptData) -> str:
        """
        Format UserPromptData into the terse, JSON-like prompt format.
        
        This matches the recommendations.txt format exactly:
        - role: ...
        - situation: ...
        - sender: ...
        - recipient: ...
        - example1: ...
        - example2: ...
        - example3: ...
        - counterexample: ...
        - last_dialogue_line: ...
        - RETURN: { "message": "<your_radio_reply>" }
        
        Args:
            data: UserPromptData instance to format
            
        Returns:
            Formatted prompt string matching recommendations.txt format.
        """
        lines = [
            f"role: {data.role}",
            f"situation: {data.situation}",
            f"sender: {data.sender}",
            f"recipient: {data.recipient}",
        ]
        
        # Add optional fields if present
        if data.altitude:
            lines.append(f"altitude: {data.altitude}")
        if data.inclination:
            lines.append(f"inclination: {data.inclination}")
        if data.speed:
            lines.append(f"speed: {data.speed}")
        
        lines.extend([
            f"example1: {data.example1}",
            f"example2: {data.example2}",
            f"example3: {data.example3}",
            f"counterexample: {data.counterexample}",
            f"last_dialogue_line: {data.last_dialogue_line or 'N/A'}",
            "",
            "RETURN:",
            '{ "message": "<your_radio_reply>" }'
        ])
        
        return "\n".join(lines)
