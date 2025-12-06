# Dialogue Particle System Design

## Overview
Modular, extensible system for building dialogue prompts using "particles" (Request, Response, Readback, Acknowledgment, etc.). Each particle type has its own examples, rules, and prompt structure.

## Current Architecture Analysis

### LLMService Responsibilities
1. **`chat()`** - Low-level LLM API wrapper (Ollama/OpenAI client)
2. **`generate_with_system_prompt()`** - Convenience wrapper for chat
3. **`get_actor_json_response()`** - ⚠️ **DIALOGUE-SPECIFIC** - builds prompts, generates dialogue (SHOULD MOVE)
4. **`is_invalid_dialogue_message()`** - Validation helper (could stay or move)

**Conclusion**: LLMService should be a thin API wrapper. Dialogue generation belongs elsewhere.

### ScriptService Responsibilities
1. **`parse_navigation_event()`** - Converts NavigationEvent → DialogueEvent (pilot request)
2. **`parse_dialogue_event()`** - Generates replies to DialogueEvents (controller response)
3. **`parse_navigation_events()`** - Batch processing
4. **`_validate_text_is_natural_language()`** - Text extraction/validation
5. **`_extract_message_from_response()`** - JSON parsing
6. **`build_situation_prompt()`** - Context building
7. **`get_dialogue_context()`** - Context extraction
8. **`format_context_for_llm()`** - Context formatting
9. **`build_controller_examples()`** - Example building
10. **`build_pilot_examples()`** - Example building

**Conclusion**: ScriptService already handles dialogue orchestration. Particle system should integrate here or become `dialogue_server.py` following naming convention.

## Revised Architecture Decisions

### 1. Naming Convention
Following the `thing_server.py` convention, dialogue generation should live in **`dialogue_server.py`** which exposes dialogue-related functionality. However, since `script_server.py` already handles dialogue orchestration, we have two options:

**Option A**: Extend `script_server.py` with particle system (keeps existing API)
**Option B**: Create `dialogue_server.py` and migrate dialogue logic there

**Recommendation**: Option A initially (less disruption), with Option B as future refactor.

### 2. LLMService Scope
LLMService becomes a **thin API wrapper**:
- `chat()` - Raw LLM API calls
- `generate_with_system_prompt()` - Convenience method
- `is_invalid_dialogue_message()` - Validation (could move to dialogue_server)

**Removed**: `get_actor_json_response()` → moves to dialogue_server/script_server

### 3. Particle Hierarchy
Support **specific particle types** that chain together:
- `LaunchRequest`, `CircularizationRequest`, `InsertionRequest`, etc. → all chain to `ControlResponse`
- `ControlResponse` → chains to `PilotReadback` or `PilotAcknowledgment`
- Support variable-length chains (3-step vs 5-step with weighted selection)

## Core Architecture

### 1. Base Classes

```python
# mysite/universe/services/dialogue_particles/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pydantic import BaseModel
from mysite.universe.models.actor import Actor
from mysite.universe.schemas.dialogue_schema import DialogueFormat, Role

class UserPromptData(BaseModel):
    """Structured user prompt data - matches recommendations.txt format"""
    role: str  # "Captain Rodriguez, the pilot of the STELLAR HORIZON"
    situation: str  # "STELLAR HORIZON is a ship intending to fly to Earth from Mars..."
    sender: str  # "STELLAR HORIZON"
    recipient: str  # "MARS CONTROL"
    example1: str
    example2: str
    example3: str
    counterexample: str
    last_dialogue_line: Optional[str] = None
    # Future: altitude, inclination, speed, etc. (placeholders for now)
    altitude: Optional[str] = None
    inclination: Optional[str] = None
    speed: Optional[str] = None


class DialogueParticle(ABC):
    """Base class for all dialogue particles (Request, Response, Readback, etc.)"""
    
    # Static system prompt (same for all particles)
    SYSTEM_PROMPT = """Generate a message for a spaceflight simulator. 
You write concise and conversational dialogue that uses
the context of the scene and situation. Observe the
SITUATION, place yourself in the ROLE, and write a 
MESSAGE to the RECIPIENT."""
    
    def __init__(self, actor: Actor, recipient: str, nav_context: Dict):
        self.actor = actor
        self.recipient = recipient
        self.nav_context = nav_context
    
    @abstractmethod
    def get_examples(self) -> List[str]:
        """Return list of 5+ example dialogue lines for this particle type"""
        pass
    
    @abstractmethod
    def get_counterexample(self) -> str:
        """Return a counterexample showing what NOT to do"""
        pass
    
    @abstractmethod
    def get_role_description(self) -> str:
        """Return role description like 'Captain Rodriguez, the pilot of the STELLAR HORIZON'"""
        pass
    
    @abstractmethod
    def get_situation_description(self) -> str:
        """Return situation description from nav_context"""
        pass
    
    @abstractmethod
    def get_format(self) -> DialogueFormat:
        """Return expected DialogueFormat for this particle"""
        pass
    
    def select_examples(self, count: int = 3) -> List[str]:
        """Select N random examples from available examples"""
        import random
        examples = self.get_examples()
        if len(examples) <= count:
            return examples
        return random.sample(examples, count)
    
    def build_user_prompt_data(self, previous_dialogue: Optional[str] = None) -> UserPromptData:
        """Build the structured user prompt data"""
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
        """Get sender callsign (ship name for pilots, station name for controllers)"""
        if self.actor.role == Role.PILOT:
            return self.actor.ship.name.upper() if hasattr(self.actor, 'ship') and self.actor.ship else self.actor.name.upper()
        else:
            return self.actor.name.upper()
    
    def format_user_prompt(self, data: UserPromptData) -> str:
        """Format UserPromptData into the terse, JSON-like prompt format"""
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
```

### 2. Concrete Particle Classes

```python
# mysite/universe/services/dialogue_particles/particles.py

from .base import DialogueParticle, UserPromptData
from mysite.universe.schemas.dialogue_schema import DialogueFormat, Role

class PilotRequest(DialogueParticle):
    """Base class for pilot requests - specific types inherit from this"""
    
    def get_role_description(self) -> str:
        ship_name = self.get_sender_callsign()
        pilot_name = self.actor.name
        return f"{pilot_name}, the pilot of the {ship_name}"
    
    def get_format(self) -> DialogueFormat:
        return DialogueFormat.INITIAL_CONTACT
    
    def get_situation_description(self) -> str:
        sender = self.get_sender_callsign()
        destination = self.nav_context.get("destination", "destination")
        maneuver = self.nav_context.get("maneuver_type", "maneuver")
        current = self.nav_context.get("current_location", "current location")
        
        return f"{sender} is a ship intending to fly to {destination} from {current}. The {sender} needs permission from {self.recipient} to {maneuver.lower()}."


class LaunchRequest(PilotRequest):
    """Pilot requesting launch clearance"""
    
    def get_examples(self) -> List[str]:
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, this is {sender} requesting permission for lift-off on three two.",
            f"{recipient}, {sender} here. We're planned for 32 degrees departure angle, prepped for launch, and awaiting your clearance.",
            f"{recipient}, {sender}. Request launch clearance to inclination 32 degrees.",
            f"{recipient}, this is {sender}, requesting clearance for launch.",
            f"{recipient}, {sender}. Ready for launch, requesting authorization.",
            f"{recipient}, {sender} here. Requesting clearance for takeoff.",
            f"{recipient}, {sender}. Can we take off?",
        ]
    
    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] Earth Control, we want to launch the STELLAR HORIZON to Earth please."


class CircularizationRequest(PilotRequest):
    """Pilot requesting circularization burn"""
    
    def get_examples(self) -> List[str]:
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for circularization burn.",
            f"{recipient}, {sender}. Ready for circularization, requesting authorization.",
            f"{recipient}, {sender} here. Requesting permission to circularize orbit.",
            f"{recipient}, {sender}. Request circularization clearance.",
            f"{recipient}, this is {sender}, requesting circularization maneuver approval.",
        ]
    
    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] Hey, can we do that circular thing now?"


class InsertionRequest(PilotRequest):
    """Pilot requesting orbital insertion burn"""
    
    def get_examples(self) -> List[str]:
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for insertion burn.",
            f"{recipient}, {sender}. Ready for orbital insertion, requesting authorization.",
            f"{recipient}, {sender} here. Requesting permission for insertion maneuver.",
            f"{recipient}, {sender}. Request insertion burn clearance.",
        ]
    
    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] We're gonna insert now, okay?"


# Generic fallback for other maneuver types
class GenericRequest(PilotRequest):
    """Generic pilot request for unspecified maneuvers"""
    
    def get_examples(self) -> List[str]:
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"{recipient}, this is {sender}, requesting clearance for {maneuver}.",
            f"{recipient}, {sender}. Ready for {maneuver}, requesting authorization.",
            f"{recipient}, {sender} here. Requesting clearance for {maneuver} maneuver.",
        ]
    
    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] Can we do the thing now?"


class RadioResponse(DialogueParticle):
    """Controller responding to pilot request"""
    
    def get_examples(self) -> List[str]:
        """5+ examples of controller responses"""
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"{recipient}, {sender}. Cleared for {maneuver} maneuver.",
            f"{recipient}, {sender}, maneuver is approved.",
            f"{recipient}, {sender}. Approved for {maneuver}, go ahead.",
            f"{recipient}, {sender}, you're cleared to proceed. Begin your {maneuver} when you're ready.",
            f"{recipient}, {sender}, confirmed for {maneuver} maneuver. Safe travels.",
            f"{recipient}, {sender}. Cleared for {maneuver}. Maintain current vector.",
        ]
    
    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] I think we should probably maybe consider allowing this request if you want."
    
    def get_role_description(self) -> str:
        return f"An anonymous space traffic control worker at {self.get_sender_callsign()}."
    
    def get_situation_description(self) -> str:
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver")
        return f"{self.get_sender_callsign()} is responding to {recipient}'s request for {maneuver.lower()} clearance."
    
    def get_format(self) -> DialogueFormat:
        return DialogueFormat.RESPONSE


class RadioAcknowledgment(DialogueParticle):
    """Pilot acknowledging controller approval"""
    
    def get_examples(self) -> List[str]:
        """5+ examples of acknowledgments"""
        sender = self.get_sender_callsign()
        recipient = self.recipient
        maneuver = self.nav_context.get("maneuver_type", "maneuver").lower()
        
        return [
            f"{recipient}, {sender}. Roger, proceeding as directed.",
            f"{recipient}, {sender}. Acknowledged, beginning the {maneuver}.",
            f"{recipient}, {sender}. Copy that, initiating {maneuver} sequence.",
            f"{recipient}, {sender}. Thanks, proceeding as directed.",
            f"{recipient}, {sender}. Got it, thanks.",
            f"{recipient}, {sender}. Acknowledged, starting {maneuver} now.",
        ]
    
    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] Can you repeat that? Also, I have another request..."
    
    def get_role_description(self) -> str:
        ship_name = self.get_sender_callsign()
        pilot_name = self.actor.name
        return f"{pilot_name}, the pilot of the {ship_name}"
    
    def get_situation_description(self) -> str:
        sender = self.get_sender_callsign()
        maneuver = self.nav_context.get("maneuver_type", "maneuver")
        return f"{sender} has just received approval from {self.recipient} for {maneuver.lower()}. Acknowledge and confirm you're proceeding."
    
    def get_format(self) -> DialogueFormat:
        return DialogueFormat.ACKNOWLEDGMENT


class RadioReadback(DialogueParticle):
    """Pilot reading back instructions"""
    
    def get_examples(self) -> List[str]:
        """5+ examples of readbacks"""
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, {sender}. Cleared for orbital insertion, maintaining current vector.",
            f"{recipient}, {sender}. 150km orbit, understood.",
            f"{recipient}, {sender}. Heading 090, confirmed.",
            f"{recipient}, {sender}. Adjusting course 45 degrees right, roger.",
        ]
    
    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] Yeah, sure, whatever you say."
    
    def get_role_description(self) -> str:
        ship_name = self.get_sender_callsign()
        pilot_name = self.actor.name
        return f"{pilot_name}, the pilot of the {ship_name}"
    
    def get_situation_description(self) -> str:
        return f"{self.get_sender_callsign()} is reading back instructions from {self.recipient} to confirm understanding."
    
    def get_format(self) -> DialogueFormat:
        return DialogueFormat.READBACK
```

### 3. Dialogue Chain Builder

```python
# mysite/universe/services/dialogue_particles/chain.py

from typing import List, Optional, Dict
from .base import DialogueParticle
from .factory import ParticleFactory
from mysite.universe.models.actor import Actor
from mysite.universe.schemas.dialogue_schema import DialogueMessage
import random

class DialogueChain:
    """Represents a dialogue chain (3-step, 5-step, etc.)"""
    
    def __init__(self, steps: List[str], weights: Optional[Dict[str, float]] = None):
        """
        Args:
            steps: List of particle types in order (e.g., ["request", "response", "acknowledgment"])
            weights: Optional weights for selecting chain variants
        """
        self.steps = steps
        self.weights = weights or {}
    
    @classmethod
    def create_standard_chain(cls) -> 'DialogueChain':
        """Standard 3-step chain: Request → Response → Acknowledgment"""
        return cls(["request", "response", "acknowledgment"])
    
    @classmethod
    def create_readback_chain(cls) -> 'DialogueChain':
        """4-step chain with readback: Request → Response → Readback → Acknowledgment"""
        return cls(["request", "response", "readback", "acknowledgment"])
    
    @classmethod
    def create_extended_chain(cls) -> 'DialogueChain':
        """5-step chain with hold: Request → Hold → Holding → Adjusted Response → Acknowledgment"""
        return cls(["request", "hold_response", "holding", "adjusted_response", "acknowledgment"])


class ChainSelector:
    """Selects dialogue chains based on weighted probabilities"""
    
    CHAIN_WEIGHTS = {
        "standard": 0.7,      # 70% chance of 3-step
        "readback": 0.2,     # 20% chance of 4-step with readback
        "extended": 0.1,     # 10% chance of 5-step with hold
    }
    
    @classmethod
    def select_chain(cls, maneuver_type: str) -> DialogueChain:
        """
        Select a chain based on maneuver type and weights.
        
        Some maneuvers (like launch) might have higher probability of extended chains.
        """
        # Adjust weights based on maneuver type
        weights = cls.CHAIN_WEIGHTS.copy()
        if maneuver_type.lower() in ["launch", "takeoff"]:
            # Launch has higher chance of extended chain (hazards, holds, etc.)
            weights["extended"] = 0.2
            weights["standard"] = 0.6
        
        # Weighted random selection
        chains = {
            "standard": DialogueChain.create_standard_chain(),
            "readback": DialogueChain.create_readback_chain(),
            "extended": DialogueChain.create_extended_chain(),
        }
        
        selected = random.choices(
            list(chains.keys()),
            weights=[weights[k] for k in chains.keys()],
            k=1
        )[0]
        
        return chains[selected]


### 4. Prompt Builder (in dialogue_server.py or script_server.py)

```python
# mysite/universe/services/dialogue_server.py (or extend script_server.py)

from typing import Optional, List
from .dialogue_particles.base import DialogueParticle
from .dialogue_particles.factory import ParticleFactory
from .dialogue_particles.chain import DialogueChain, ChainSelector
from mysite.universe.models.actor import Actor
from mysite.universe.schemas.dialogue_schema import DialogueMessage
from mysite.universe.services.llm_service import LLMService

class DialogueService:
    """Service for generating dialogue using particle system"""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
    
    def build_prompt(self, 
                     particle: DialogueParticle,
                     previous_dialogue: Optional[DialogueMessage] = None) -> tuple[str, str]:
        """
        Build system and user prompts from a particle.
        
        Returns:
            (system_prompt, user_prompt) tuple
        """
        # System prompt is static
        system_prompt = particle.SYSTEM_PROMPT
        
        # Build user prompt from particle
        previous_text = previous_dialogue.message if previous_dialogue else None
        user_prompt_data = particle.build_user_prompt_data(previous_text)
        user_prompt = particle.format_user_prompt(user_prompt_data)
        
        return system_prompt, user_prompt
    
    def generate_dialogue(self,
                         particle: DialogueParticle,
                         previous_dialogue: Optional[DialogueMessage] = None,
                         temperature: Optional[float] = None) -> DialogueMessage:
        """
        Generate dialogue using structured outputs.
        
        Uses Ollama's structured outputs feature to ensure valid JSON.
        """
        system_prompt, user_prompt = self.build_prompt(particle, previous_dialogue)
        
        # Call LLM with structured outputs
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Use structured outputs (format parameter)
        response = self.llm_service.chat(
            messages=messages,
            temperature=temperature,
            use_structured_output=True  # Uses format parameter
        )
        
        # Parse response (should already be valid JSON)
        import json
        data = json.loads(response)
        
        # Convert to DialogueMessage
        return DialogueMessage(**data)
    
    def generate_chain(self,
                      chain: DialogueChain,
                      pilot: Actor,
                      controller: Actor,
                      nav_context: Dict,
                      temperature: Optional[float] = None) -> List[DialogueMessage]:
        """
        Generate a complete dialogue chain.
        
        Args:
            chain: DialogueChain defining the sequence
            pilot: Pilot actor
            controller: Controller actor
            nav_context: Navigation context
            temperature: Optional temperature override
        
        Returns:
            List of DialogueMessage objects in sequence
        """
        messages = []
        previous_message = None
        
        for step_type in chain.steps:
            # Determine actor and recipient for this step
            if step_type in ["request", "acknowledgment", "readback", "holding"]:
                actor = pilot
                recipient = controller.name
            else:  # response, hold_response, adjusted_response
                actor = controller
                recipient = pilot.ship.name if hasattr(pilot, 'ship') else pilot.name
            
            # Create particle
            particle = ParticleFactory.create_particle(
                particle_type=step_type,
                actor=actor,
                recipient=recipient,
                nav_context=nav_context
            )
            
            # Generate dialogue
            dialogue_msg = self.generate_dialogue(
                particle=particle,
                previous_dialogue=previous_message,
                temperature=temperature
            )
            
            messages.append(dialogue_msg)
            previous_message = dialogue_msg
        
        return messages
```

### 4. Factory for Creating Particles

```python
# mysite/universe/services/dialogue_particles/factory.py

from typing import Dict
from .particles import RadioRequest, RadioResponse, RadioAcknowledgment, RadioReadback
from .base import DialogueParticle
from mysite.universe.models.actor import Actor
from mysite.universe.schemas.dialogue_schema import DialogueFormat

class ParticleFactory:
    """Factory for creating dialogue particles based on context"""
    
    # Specific request types
    REQUEST_PARTICLE_MAP = {
        "launch": LaunchRequest,
        "takeoff": LaunchRequest,
        "circularize": CircularizationRequest,
        "circularization": CircularizationRequest,
        "insertion": InsertionRequest,
        "orbital_insertion": InsertionRequest,
    }
    
    # Generic particle types
    PARTICLE_MAP = {
        "response": RadioResponse,
        "acknowledgment": RadioAcknowledgment,
        "readback": RadioReadback,
    }
    
    @classmethod
    def create_particle(cls,
                       particle_type: str,
                       actor: Actor,
                       recipient: str,
                       nav_context: Dict) -> DialogueParticle:
        """
        Create a particle instance.
        
        Args:
            particle_type: "request", "launch", "circularize", "response", "acknowledgment", "readback"
            actor: The actor speaking
            recipient: The recipient callsign
            nav_context: Navigation context dict
        """
        # Check for specific request types first
        maneuver_type = nav_context.get("maneuver_type", "").lower()
        if particle_type.lower() == "request":
            # Use specific request type if available, otherwise generic
            request_class = cls.REQUEST_PARTICLE_MAP.get(maneuver_type, GenericRequest)
            return request_class(actor, recipient, nav_context)
        
        # Check generic particle map
        particle_class = cls.PARTICLE_MAP.get(particle_type.lower())
        if not particle_class:
            raise ValueError(f"Unknown particle type: {particle_type}")
        
        return particle_class(actor, recipient, nav_context)
    
    @classmethod
    def register_particle(cls, particle_type: str, particle_class: type):
        """Register a new particle type (for extensibility)"""
        cls.PARTICLE_MAP[particle_type.lower()] = particle_class
    
    @classmethod
    def register_request_particle(cls, maneuver_type: str, particle_class: type):
        """Register a new request particle type for a specific maneuver"""
        cls.REQUEST_PARTICLE_MAP[maneuver_type.lower()] = particle_class
```

## Usage Example

```python
# In script_server.py or similar

from mysite.universe.services.dialogue_particles.factory import ParticleFactory
from mysite.universe.services.dialogue_particles.builder import PromptBuilder

# Create particle
particle = ParticleFactory.create_particle(
    particle_type="request",
    actor=pilot,
    recipient="MARS CONTROL",
    nav_context={
        "maneuver_type": "launch",
        "destination": "Earth",
        "current_location": "Mars"
    }
)

# Build prompt and generate
builder = PromptBuilder(llm_service)
dialogue_msg = builder.generate_dialogue(particle, temperature=0.7)
```

## Benefits

1. **Modular**: Each particle type is self-contained
2. **Extensible**: Add new particles by subclassing `DialogueParticle` and registering
3. **Testable**: Each particle can be tested independently
4. **DRY**: Shared logic in base class
5. **Type-safe**: Uses Pydantic for validation
6. **Structured**: Matches recommendations.txt format exactly
7. **Future-proof**: Easy to add physics/vector data later

## File Structure

### Option A: Extend script_server.py (Recommended initially)
```
mysite/universe/services/
├── script_server.py          # Extended with particle system
├── llm_service.py            # Thin API wrapper only
└── dialogue/                 # New module
    ├── __init__.py
    ├── base.py               # DialogueParticle ABC, UserPromptData
    ├── particles.py          # LaunchRequest, CircularizationRequest, RadioResponse, etc.
    ├── factory.py            # ParticleFactory
    ├── chain.py              # DialogueChain, ChainSelector
    └── builder.py            # PromptBuilder (or integrate into script_server)
```

### Option B: Create dialogue_server.py (Future refactor)
```
mysite/universe/services/
├── dialogue_server.py        # New service following naming convention
├── script_server.py          # Orchestrates navigation → dialogue conversion
├── llm_service.py            # Thin API wrapper only
└── dialogue/                 # Same structure as Option A
```

## Additional Particle Types Needed

### Hold/Extended Chain Particles

```python
class HoldResponse(RadioResponse):
    """Controller responding with a hold (hazard, traffic, etc.)"""
    
    def get_examples(self) -> List[str]:
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, {sender}. Negative, hold position. There's a hazard in your flight path.",
            f"{recipient}, {sender}. Hold, there's traffic ahead. Stand by.",
            f"{recipient}, {sender}. Negative, hold. Adjusting clearance parameters.",
        ]
    
    def get_counterexample(self) -> str:
        return "[DON'T DO THIS!] Umm, maybe wait a bit?"


class Holding(PilotRequest):
    """Pilot acknowledging hold instruction"""
    
    def get_examples(self) -> List[str]:
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, {sender}. Holding position.",
            f"{recipient}, {sender}. Roger, holding.",
            f"{recipient}, {sender}. Copy, holding.",
        ]
    
    def get_format(self) -> DialogueFormat:
        return DialogueFormat.ACKNOWLEDGMENT


class AdjustedResponse(RadioResponse):
    """Controller providing adjusted clearance after hold"""
    
    def get_examples(self) -> List[str]:
        sender = self.get_sender_callsign()
        recipient = self.recipient
        
        return [
            f"{recipient}, {sender}. Okay, adjust to azimuth seven zero, and launch. Sorry for the delay.",
            f"{recipient}, {sender}. Cleared now, proceed with adjusted vector.",
            f"{recipient}, {sender}. Traffic cleared, you're good to go.",
        ]
```

## Addressing Design Concerns

### 1. LLMService Responsibilities
**Current**: LLMService does too much (dialogue generation, prompt building)
**Solution**: 
- LLMService becomes thin API wrapper: `chat()`, `generate_with_system_prompt()`
- Move `get_actor_json_response()` → `DialogueService.generate_dialogue()`
- Keep `is_invalid_dialogue_message()` in LLMService (or move to DialogueService)

**Rationale**: If LLM is only for dialogue, it could be part of dialogue_server. But keeping it separate allows future non-dialogue LLM uses (descriptions, logs, etc.).

### 2. ScriptService Responsibilities  
**Current**: ScriptService orchestrates NavigationEvent → DialogueEvent conversion
**New Responsibilities**:
- **Orchestration**: `parse_navigation_event()` converts NavigationEvent → complete dialogue chain
- **Context Building**: Extracts nav context from NavigationEvent (maneuver, locations, actors)
- **Event Conversion**: Converts `DialogueMessage` → `DialogueEvent` with timestamps, metadata, actors
- **Integration**: Works with existing queue/event system

**Delegates To DialogueService**:
- Chain selection (which chain type to use)
- Chain generation (prompt building, LLM calls)
- Returns `List[DialogueMessage]` (not DialogueEvents)

**Rationale**: 
- ScriptService = "what dialogue to generate" + "how to integrate with event system"
- DialogueService = "how to generate dialogue" (prompts, LLM, particles)
- Clear separation: ScriptService owns events, DialogueService owns dialogue generation

### 3. Naming Convention (`thing_server.py`)
**Current**: Design uses `dialogue_particles/` directory
**Options**:
- **Option A**: Extend `script_server.py` (keeps existing API, less disruption)
- **Option B**: Create `dialogue_server.py` (follows convention, cleaner separation)

**Recommendation**: Start with Option A, migrate to Option B later if needed.

**Rationale**: `dialogue_particles/` is a module, not a service. The service layer (`DialogueService`) can live in `script_server.py` or `dialogue_server.py`.

### 4. Specific Particle Types (LaunchRequest, CircularizationRequest, etc.)
**Solution**: 
- Base class `PilotRequest` with shared logic
- Specific subclasses: `LaunchRequest`, `CircularizationRequest`, `InsertionRequest`
- `GenericRequest` fallback for unspecified maneuvers
- All chain to `RadioResponse` (controller) → `RadioReadback`/`RadioAcknowledgment`

**Factory Logic**:
```python
# When particle_type="request", factory checks maneuver_type:
if maneuver_type == "launch": → LaunchRequest
elif maneuver_type == "circularize": → CircularizationRequest
else: → GenericRequest
```

### 5. Variable-Length Chains (3-step vs 5-step)
**Solution**:
- `DialogueChain` class defines step sequences
- `ChainSelector` uses weighted probabilities
- Launch maneuvers have higher probability of extended chains (20% vs 10%)
- Extended chain: Request → Hold → Holding → Adjusted Response → Acknowledgment

**Example**:
```python
chain = ChainSelector.select_chain("launch")
# 70% standard (3-step)
# 20% readback (4-step)  
# 10% extended (5-step) - but launch gets 20%

messages = dialogue_service.generate_chain(chain, pilot, controller, nav_context)
```

## Chain Generation Flow

**See `DIALOGUE_CHAIN_FLOW.md` for detailed flow diagrams.**

### Key Decision: ScriptService Owns Orchestration

**ScriptService** (`script_server.py`):
- Converts `NavigationEvent` → Complete dialogue chain
- Builds navigation context from NavigationEvent
- Converts `DialogueMessage` → `DialogueEvent` with timestamps/metadata
- Integrates with existing queue/event system

**DialogueService** (`dialogue_server.py`):
- Selects chain type (3-step, 4-step, 5-step) based on maneuver
- Generates complete chain using particle system
- Builds prompts and calls LLM with structured outputs
- Returns `List[DialogueMessage]` (not DialogueEvents)

### Flow Summary

```
NavigationEvent
  → ScriptService.parse_navigation_event()
    → Build nav_context
    → DialogueService.generate_chain_from_nav_event()
      → ChainSelector.select_chain() → DialogueChain
      → Generate each step in chain → List[DialogueMessage]
    → Convert messages to events → List[DialogueEvent]
    → Return complete chain
```

### Breaking Change: Return Type

**Old**: `parse_navigation_event()` returns `DialogueEvent` (single event)
**New**: `parse_navigation_event()` returns `List[DialogueEvent]` (complete chain)

**Migration**: Update all callers:
```python
# Old
event = script_service.parse_navigation_event(nav_event, ship)
queue.add_event(event)

# New  
events = script_service.parse_navigation_event(nav_event, ship)
for event in events:
    queue.add_event(event)
```

## Migration Path

1. **Phase 1**: Create particle system alongside existing code
2. **Phase 2**: Create `DialogueService` with chain generation
3. **Phase 3**: Update `ScriptService.parse_navigation_event()` to return `List[DialogueEvent]`
4. **Phase 4**: Update all callers to handle list return type
5. **Phase 5**: Test with structured outputs
6. **Phase 6**: Deprecate `parse_dialogue_event()` (no longer needed for chains)
7. **Phase 7**: Remove old prompt-building code

---

## Implementation TODO List

### Files to CREATE

#### `mysite/universe/services/dialogue_server.py` (NEW FILE)
1. Create `DialogueService` class
2. Implement `__init__(llm_service: LLMService)`
3. Implement `generate_chain_from_nav_event()` method
4. Implement `generate_chain()` method
5. Implement `generate_dialogue()` method (single message generation)
6. Implement `build_prompt()` method (system + user prompt building)
7. Add `chain_selector` instance variable (ChainSelector)

#### `mysite/universe/services/dialogue/__init__.py` (NEW FILE)
1. Create module `__init__.py`
2. Export `DialogueParticle`, `UserPromptData` from `base`
3. Export particle classes from `particles`
4. Export `ParticleFactory` from `factory`
5. Export `DialogueChain`, `ChainSelector` from `chain`

#### `mysite/universe/services/dialogue/base.py` (NEW FILE)
1. Create `UserPromptData` Pydantic model
2. Create `DialogueParticle` abstract base class
3. Implement `SYSTEM_PROMPT` class variable (static prompt)
4. Implement `__init__(actor, recipient, nav_context)` method
5. Implement abstract methods:
   - `get_examples() -> List[str]`
   - `get_counterexample() -> str`
   - `get_role_description() -> str`
   - `get_situation_description() -> str`
   - `get_format() -> DialogueFormat`
6. Implement `select_examples(count=3)` method (random selection)
7. Implement `build_user_prompt_data()` method
8. Implement `get_sender_callsign()` method
9. Implement `format_user_prompt()` method (JSON-like format)

#### `mysite/universe/services/dialogue/particles.py` (NEW FILE)
1. Create `PilotRequest` base class (inherits from `DialogueParticle`)
2. Create `LaunchRequest` class (inherits from `PilotRequest`)
3. Create `CircularizationRequest` class (inherits from `PilotRequest`)
4. Create `InsertionRequest` class (inherits from `PilotRequest`)
5. Create `GenericRequest` class (inherits from `PilotRequest`, fallback)
6. Create `RadioResponse` class (controller responses)
7. Create `RadioAcknowledgment` class (pilot acknowledgments)
8. Create `RadioReadback` class (pilot readbacks)
9. Create `HoldResponse` class (controller hold responses)
10. Create `Holding` class (pilot holding acknowledgment)
11. Create `AdjustedResponse` class (controller adjusted clearance)
12. Implement `get_examples()` for each class (5+ examples each)
13. Implement `get_counterexample()` for each class
14. Implement `get_role_description()` for each class
15. Implement `get_situation_description()` for each class
16. Implement `get_format()` for each class

#### `mysite/universe/services/dialogue/factory.py` (NEW FILE)
1. Create `ParticleFactory` class
2. Implement `REQUEST_PARTICLE_MAP` class variable (maneuver → particle mapping)
3. Implement `PARTICLE_MAP` class variable (generic particle types)
4. Implement `create_particle()` classmethod
5. Implement `register_particle()` classmethod
6. Implement `register_request_particle()` classmethod

#### `mysite/universe/services/dialogue/chain.py` (NEW FILE)
1. Create `DialogueChain` class
2. Implement `__init__(steps, weights)` method
3. Implement `create_standard_chain()` classmethod (3-step)
4. Implement `create_readback_chain()` classmethod (4-step)
5. Implement `create_extended_chain()` classmethod (5-step)
6. Create `ChainSelector` class
7. Implement `CHAIN_WEIGHTS` class variable
8. Implement `select_chain(maneuver_type)` classmethod

### Files to MODIFY

#### `mysite/universe/services/llm_service.py`
1. **REMOVE**: `get_actor_json_response()` method (move to DialogueService)
2. **MODIFY**: `chat()` method - add `use_structured_output` parameter support
3. **MODIFY**: `chat()` method - implement structured outputs via `format` parameter when enabled
4. **KEEP**: `is_invalid_dialogue_message()` classmethod (or move to DialogueService)
5. **KEEP**: `generate_with_system_prompt()` convenience method
6. **UPDATE**: Docstrings to reflect thin wrapper role

#### `mysite/universe/services/script_server.py`
1. **MODIFY**: `parse_navigation_event()` method
   - Change return type: `DialogueEvent` → `List[DialogueEvent]`
   - Add call to `DialogueService.generate_chain_from_nav_event()`
   - Add `_convert_messages_to_events()` call
   - Remove old prompt-building code
2. **ADD**: `_build_nav_context()` helper method
3. **ADD**: `_convert_messages_to_events()` helper method
   - Converts `List[DialogueMessage]` → `List[DialogueEvent]`
   - Sets sequential timestamps
   - Builds metadata for each event
   - Sets `expect_reply` flags correctly
4. **MODIFY**: `parse_navigation_events()` method
   - Change `append()` to `extend()` to handle list return type
5. **DEPRECATE**: `parse_dialogue_event()` method
   - Add deprecation warning
   - Keep for backward compatibility during migration
   - Mark for removal in future version
6. **REMOVE**: Old prompt-building methods (after migration):
   - `build_situation_prompt()` (if no longer used)
   - `build_controller_examples()` (replaced by particles)
   - `build_pilot_examples()` (replaced by particles)
7. **REMOVE**: Old helper methods (if no longer used):
   - `format_context_for_llm()` (replaced by particle system)
   - `get_dialogue_context()` (replaced by particle system)
8. **UPDATE**: `__init__()` to optionally accept `DialogueService` instance
9. **ADD**: Import `DialogueService` from `dialogue_server`

#### `mysite/universe/management/commands/character_dialogue_demo.py`
1. **MODIFY**: `handle()` method
   - Update `parse_navigation_events()` result handling (already returns list, but verify)
   - Update any direct `parse_navigation_event()` calls to handle list
2. **VERIFY**: Comms check insertion logic still works with list return type

#### `dialogue_quality_eval.py` (if exists in root)
1. **MODIFY**: Update `parse_navigation_events()` handling
2. **MODIFY**: Update `process_dialogue_chain()` if it calls `parse_dialogue_event()`
3. **VERIFY**: Comms check event creation still works

#### `mysite/universe/models/event.py`
1. **MODIFY**: `DialogueEvent.expect_reply_action()` method
   - Currently calls `ScriptService.parse_dialogue_event()` (lines 148, 153)
   - **DECISION NEEDED**: Should chain events still trigger replies, or are chains complete?
   - If chains are complete, remove `parse_dialogue_event()` calls
   - If chains need dynamic replies, update logic
2. **VERIFY**: `DialogueEvent.process()` handles chain events correctly

#### `tests/test_space_traffic_llm.py`
1. **UPDATE**: Test that calls `parse_navigation_events()` to handle list return type
2. **VERIFY**: Test assertions work with list of events

#### `mysite/universe/models/event.py`
1. **VERIFY**: `DialogueEvent.expect_reply_action()` still works correctly
2. **VERIFY**: `DialogueEvent.process()` handles chain events correctly
3. **NOTE**: May need updates if chain events have different metadata structure

### Files to VERIFY/UPDATE (Callers of Changed Methods)

#### `mysite/universe/simulation_queue.py`
1. **VERIFY**: `SimulationQueue.add_event()` handles list of events correctly
2. **VERIFY**: `process_due_events()` handles chain events correctly

#### `tests/test_queue_functions.py`
1. **UPDATE**: Tests that call `parse_navigation_event()` to expect list return type
2. **ADD**: Tests for chain generation
3. **ADD**: Tests for sequential timestamps in chains

#### `tests/test_llm_error_handling.py`
1. **VERIFY**: Still works after `get_actor_json_response()` removal
2. **UPDATE**: If tests reference old method, update to use `DialogueService`

#### `tests/test_route_planning.py`
1. **VERIFY**: No direct calls to `parse_navigation_event()` that need updating

### Files to CREATE (Tests)

#### `tests/test_dialogue_particles.py` (NEW FILE)
1. Create test class for `DialogueParticle` base class
2. Create test class for each particle type (LaunchRequest, etc.)
3. Test `get_examples()` returns 5+ examples
4. Test `get_counterexample()` returns valid counterexample
5. Test `select_examples()` returns correct number
6. Test `build_user_prompt_data()` creates valid `UserPromptData`
7. Test `format_user_prompt()` creates correct format

#### `tests/test_dialogue_factory.py` (NEW FILE)
1. Test `ParticleFactory.create_particle()` with specific maneuver types
2. Test `ParticleFactory.create_particle()` with generic types
3. Test `ParticleFactory.register_particle()` extensibility
4. Test fallback to `GenericRequest` for unknown maneuvers

#### `tests/test_dialogue_chains.py` (NEW FILE)
1. Test `DialogueChain.create_standard_chain()` structure
2. Test `DialogueChain.create_readback_chain()` structure
3. Test `DialogueChain.create_extended_chain()` structure
4. Test `ChainSelector.select_chain()` weighted selection
5. Test chain selection probabilities for different maneuvers

#### `tests/test_dialogue_service.py` (NEW FILE)
1. Test `DialogueService.generate_chain_from_nav_event()`
2. Test `DialogueService.generate_chain()` with mock LLM
3. Test `DialogueService.generate_dialogue()` with structured outputs
4. Test `DialogueService.build_prompt()` output format
5. Test integration with real LLM (marked as slow test)

#### `tests/test_script_service_chains.py` (NEW FILE)
1. Test `ScriptService.parse_navigation_event()` returns list
2. Test `ScriptService._convert_messages_to_events()` timestamp sequencing
3. Test `ScriptService._convert_messages_to_events()` metadata building
4. Test `ScriptService.parse_navigation_events()` with multiple nav events
5. Test integration: NavigationEvent → complete chain → DialogueEvents

### Files to UPDATE (Documentation)

#### `docs/DIALOGUE_PARTICLE_DESIGN.md`
1. **VERIFY**: All code examples match final implementation
2. **UPDATE**: Add usage examples for new API

#### `docs/DIALOGUE_CHAIN_FLOW.md`
1. **VERIFY**: Flow diagrams match final implementation
2. **UPDATE**: Add migration examples for common patterns

### Implementation Order

**Phase 1: Foundation (Create Particle System)**
1. Create `dialogue/__init__.py` (empty initially)
2. Create `dialogue/base.py` with `DialogueParticle` ABC and `UserPromptData`
3. Create `dialogue/particles.py` with all particle classes
4. Create `dialogue/factory.py` with `ParticleFactory`
5. Create `dialogue/chain.py` with `DialogueChain` and `ChainSelector`
6. Update `dialogue/__init__.py` with proper exports
7. Write unit tests for particles (`tests/test_dialogue_particles.py`)
8. Write unit tests for factory (`tests/test_dialogue_factory.py`)
9. Write unit tests for chains (`tests/test_dialogue_chains.py`)

**Phase 2: Service Layer (Create DialogueService)**
10. Add structured outputs support to `llm_service.py` `chat()` method
11. Create `dialogue_server.py` with `DialogueService` class
12. Implement `DialogueService.generate_chain_from_nav_event()` method
13. Implement `DialogueService.generate_chain()` method
14. Implement `DialogueService.generate_dialogue()` method
15. Implement `DialogueService.build_prompt()` method
16. Write unit tests for DialogueService (`tests/test_dialogue_service.py`)

**Phase 3: Integration (Update ScriptService)**
17. Add `DialogueService` import to `script_server.py`
18. Add `_build_nav_context()` helper method to `ScriptService`
19. Add `_convert_messages_to_events()` helper method to `ScriptService`
20. Modify `ScriptService.parse_navigation_event()` to:
    - Call `DialogueService.generate_chain_from_nav_event()`
    - Call `_convert_messages_to_events()`
    - Return `List[DialogueEvent]` instead of `DialogueEvent`
21. Modify `ScriptService.parse_navigation_events()` to use `extend()` instead of `append()`
22. Deprecate `ScriptService.parse_dialogue_event()` with warning
23. Write integration tests (`tests/test_script_service_chains.py`)

**Phase 4: Migration (Update Callers)**
24. Update `mysite/universe/models/event.py` `DialogueEvent.expect_reply_action()`
    - **DECISION**: Determine if chain events should trigger dynamic replies
    - If chains are complete, remove `parse_dialogue_event()` calls
    - If chains need replies, update logic
25. Update `mysite/universe/management/commands/character_dialogue_demo.py`
26. Update `dialogue_quality_eval.py` (if exists)
27. Update `tests/test_space_traffic_llm.py`
28. Verify `mysite/universe/simulation_queue.py` handles lists correctly

**Phase 5: Cleanup (Remove Old Code)**
29. Remove `get_actor_json_response()` from `llm_service.py`
30. Remove old prompt-building methods from `script_server.py`:
    - `build_situation_prompt()` (if unused)
    - `build_controller_examples()` (replaced by particles)
    - `build_pilot_examples()` (replaced by particles)
    - `format_context_for_llm()` (replaced by particles)
    - `get_dialogue_context()` (replaced by particles)
31. Remove deprecated `parse_dialogue_event()` (after migration period)
32. Update all docstrings to reflect new architecture

### Testing Strategy

1. **Unit Tests**: Test each particle class independently
2. **Integration Tests**: Test chain generation end-to-end
3. **Regression Tests**: Verify existing functionality still works
4. **Performance Tests**: Ensure chain generation is fast enough
5. **Structured Outputs Tests**: Verify Ollama structured outputs work correctly

### Critical Decision Points

#### Decision 1: Chain Events and Dynamic Replies
**Location**: `mysite/universe/models/event.py` - `DialogueEvent.expect_reply_action()`

**Current Behavior**: When a `DialogueEvent` has `expect_reply=True`, it calls `ScriptService.parse_dialogue_event()` to generate a reply dynamically.

**Question**: Should chain events (which are complete) still trigger dynamic replies, or are chains self-contained?

**Option A**: Chains are complete - remove `parse_dialogue_event()` calls from `expect_reply_action()`
- Chains generated upfront are complete sequences
- No dynamic reply generation needed
- Simpler, more predictable

**Option B**: Chains can trigger replies - keep dynamic reply logic
- Some events might need dynamic replies even within chains
- More flexible but more complex

**Recommendation**: Option A - chains are complete. If a chain event has `expect_reply=True`, it means the NEXT event in the chain is the reply (already generated). Remove dynamic reply generation.

#### Decision 2: Backward Compatibility Period
**How long to keep deprecated `parse_dialogue_event()`?**
- Recommendation: Keep for 1-2 release cycles with deprecation warning
- Remove after all callers migrated

#### Decision 3: LLMService Validation Method
**Location**: `llm_service.py` - `is_invalid_dialogue_message()`

**Question**: Should this stay in `LLMService` or move to `DialogueService`?

**Option A**: Keep in `LLMService` (shared utility)
**Option B**: Move to `DialogueService` (dialogue-specific)

**Recommendation**: Option A - it's a validation utility that could be used by other LLM consumers.

