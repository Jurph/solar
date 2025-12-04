# Dialogue Chain Generation Flow

## Current Flow (Single Events)

```
NavigationEvent 
  → ScriptService.parse_navigation_event()
    → DialogueEvent (pilot request, expect_reply=True)
      → Later: ScriptService.parse_dialogue_event()
        → DialogueEvent (controller response, expect_reply=True)
          → Later: ScriptService.parse_dialogue_event()
            → DialogueEvent (pilot acknowledgment, expect_reply=False)
```

**Problem**: Events generated one at a time, requires multiple passes.

## New Flow (Complete Chains)

```
NavigationEvent
  → ScriptService.parse_navigation_event()
    → DialogueService.generate_chain_from_nav_event()
      → ChainSelector.select_chain(maneuver_type)
        → DialogueChain (e.g., ["request", "response", "acknowledgment"])
      → DialogueService.generate_chain()
        → For each step in chain:
          → Create particle
          → Generate DialogueMessage
        → Returns List[DialogueMessage]
      → ScriptService._convert_messages_to_events()
        → Convert each DialogueMessage → DialogueEvent
        → Set sequential timestamps, metadata, actors
        → Returns List[DialogueEvent] (complete chain)
```

## Architecture Decision: Who Owns What?

### ScriptService Responsibilities
- **Orchestration**: Convert NavigationEvent → Dialogue chain
- **Context Building**: Extract nav context from NavigationEvent
- **Event Sequencing**: Set timestamps, durations, metadata
- **Integration**: Works with existing queue/event system

### DialogueService Responsibilities  
- **Chain Selection**: Choose chain type based on maneuver
- **Chain Generation**: Generate complete dialogue chain
- **Prompt Building**: Build prompts from particles
- **LLM Interaction**: Call LLM with structured outputs
- **Returns**: `List[DialogueMessage]` (not DialogueEvents - ScriptService handles conversion)

## Detailed Flow

### 1. NavigationEvent → Dialogue Chain

```python
# In script_server.py

class ScriptService:
    def parse_navigation_event(self, nav_event: NavigationEvent, ship: Ship) -> List[DialogueEvent]:
        """
        Convert NavigationEvent to complete dialogue chain.
        
        Returns:
            List[DialogueEvent] - Complete chain (3-step, 4-step, or 5-step)
        """
        # Build navigation context
        nav_context = self._build_nav_context(nav_event, ship)
        
        # Get actors
        pilot = ship.pilot
        controller = self._get_controller(nav_event)
        
        # Delegate to DialogueService for chain generation
        from mysite.universe.services.dialogue_server import DialogueService
        dialogue_service = DialogueService(self.llm)
        
        # Generate complete chain
        dialogue_messages = dialogue_service.generate_chain_from_nav_event(
            nav_event=nav_event,
            pilot=pilot,
            controller=controller,
            nav_context=nav_context
        )
        
        # Convert DialogueMessages to DialogueEvents with timestamps
        dialogue_events = self._convert_messages_to_events(
            messages=dialogue_messages,
            nav_event=nav_event,
            ship=ship
        )
        
        return dialogue_events
    
    def _build_nav_context(self, nav_event: NavigationEvent, ship: Ship) -> Dict:
        """Extract navigation context from NavigationEvent"""
        return {
            "maneuver_type": nav_event.maneuver.value if hasattr(nav_event.maneuver, 'value') else str(nav_event.maneuver),
            "current_location": get_location_name(nav_event.current) if hasattr(nav_event, 'current') else None,
            "destination": get_location_name(nav_event.destination) if hasattr(nav_event, 'destination') else None,
            "origin": get_location_name(nav_event.origin) if hasattr(nav_event, 'origin') else None,
            "ship_name": ship.name,
            "pilot_name": ship.pilot.name if ship.pilot else None,
        }
    
    def _convert_messages_to_events(self, 
                                    messages: List[DialogueMessage],
                                    nav_event: NavigationEvent,
                                    ship: Ship) -> List[DialogueEvent]:
        """
        Convert DialogueMessages to DialogueEvents with proper timestamps and metadata.
        
        Events are spaced sequentially (e.g., 0.0s, 2.0s, 4.0s for 3-step chain).
        """
        events = []
        base_timestamp = nav_event.timestamp
        current_timestamp = base_timestamp
        
        for i, msg in enumerate(messages):
            # Determine if this expects a reply
            is_last = (i == len(messages) - 1)
            expect_reply = not is_last
            
            # Get actor from message
            actor = self._get_actor_from_message(msg, ship)
            
            # Build metadata
            metadata = {
                "control_name": msg.recipient_callsign if msg.role == Role.CONTROLLER else None,
                "ship_name": msg.speaker_callsign if msg.role == Role.PILOT else None,
                "maneuver": nav_context.get("maneuver_type"),
                "pilot_name": ship.pilot.name if ship.pilot else None,
                "chain_position": i,
                "chain_length": len(messages),
            }
            
            # Create DialogueEvent
            event = DialogueEvent(
                timestamp=current_timestamp,
                actor=actor,
                text=msg.message,  # Natural language text
                expect_reply=expect_reply,
                duration=2.0,  # Default duration
                event_type="dialogue",
                metadata=metadata,
                expected_reply_actor=self._get_reply_actor(msg, ship) if expect_reply else None
            )
            
            events.append(event)
            current_timestamp += event.duration
        
        return events
```

### 2. DialogueService Chain Generation

```python
# In dialogue_server.py

class DialogueService:
    """Service for generating dialogue chains using particle system"""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.chain_selector = ChainSelector()
    
    def generate_chain_from_nav_event(self,
                                     nav_event: NavigationEvent,
                                     pilot: Actor,
                                     controller: Actor,
                                     nav_context: Dict) -> List[DialogueMessage]:
        """
        Generate complete dialogue chain from NavigationEvent.
        
        This is the main entry point for chain generation.
        """
        # Select chain type based on maneuver
        maneuver_type = nav_context.get("maneuver_type", "").lower()
        chain = self.chain_selector.select_chain(maneuver_type)
        
        # Generate chain
        return self.generate_chain(
            chain=chain,
            pilot=pilot,
            controller=controller,
            nav_context=nav_context
        )
    
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
                recipient = pilot.ship.name if hasattr(pilot, 'ship') and pilot.ship else pilot.name
            
            # Create particle
            particle = ParticleFactory.create_particle(
                particle_type=step_type,
                actor=actor,
                recipient=recipient,
                nav_context=nav_context
            )
            
            # Generate dialogue message
            dialogue_msg = self.generate_dialogue(
                particle=particle,
                previous_dialogue=previous_message,
                temperature=temperature
            )
            
            messages.append(dialogue_msg)
            previous_message = dialogue_msg
        
        return messages
    
    def generate_dialogue(self,
                         particle: DialogueParticle,
                         previous_dialogue: Optional[DialogueMessage] = None,
                         temperature: Optional[float] = None) -> DialogueMessage:
        """
        Generate single dialogue message using structured outputs.
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
```

## Integration Points

### 1. Existing Code That Calls parse_navigation_event()

**Current**: Expects single `DialogueEvent`
```python
dialogue_event = script_service.parse_navigation_event(nav_event, ship)
```

**New**: Returns `List[DialogueEvent]`
```python
dialogue_events = script_service.parse_navigation_event(nav_event, ship)
# Handle as list
```

**Migration**: Update callers to handle list:
```python
# Old
event = script_service.parse_navigation_event(nav_event, ship)
queue.add_event(event)

# New
events = script_service.parse_navigation_event(nav_event, ship)
for event in events:
    queue.add_event(event)
```

### 2. parse_navigation_events() (Batch Processing)

**Current**: 
```python
def parse_navigation_events(self, nav_events, ship):
    script_events = []
    for nav_event in nav_events:
        dialogue_event = self.parse_navigation_event(nav_event, ship)
        script_events.append(dialogue_event)
    return script_events
```

**New**: Already handles lists, just flatten:
```python
def parse_navigation_events(self, nav_events, ship):
    script_events = []
    for nav_event in nav_events:
        dialogue_events = self.parse_navigation_event(nav_event, ship)  # Returns list
        script_events.extend(dialogue_events)  # Extend, not append
    return script_events
```

### 3. parse_dialogue_event() (Reply Generation)

**Current**: Generates replies one at a time
**New**: **DEPRECATED** - chains are generated complete

**Migration**: 
- Keep `parse_dialogue_event()` for backward compatibility
- Mark as deprecated
- Eventually remove once all code uses chains

## Benefits of This Approach

1. **Single Pass**: Generate entire chain in one call
2. **Consistent Timestamps**: All events in chain have sequential timestamps
3. **Better Context**: Each message in chain sees previous messages
4. **Cleaner API**: ScriptService orchestrates, DialogueService generates
5. **Backward Compatible**: Can keep old methods during migration

## File Structure

```
mysite/universe/services/
├── script_server.py          # Orchestration: NavigationEvent → Dialogue chain
├── dialogue_server.py        # Generation: Chain selection, prompt building, LLM calls
├── llm_service.py            # Thin API wrapper
└── dialogue/                 # Particle system module
    ├── __init__.py
    ├── base.py               # DialogueParticle ABC, UserPromptData
    ├── particles.py           # LaunchRequest, CircularizationRequest, etc.
    ├── factory.py             # ParticleFactory
    ├── chain.py               # DialogueChain, ChainSelector
    └── builder.py             # Prompt building utilities (or in dialogue_server)
```

