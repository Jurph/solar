# Dialogue Particle System - Implementation Sequence

## Philosophy: Build from Contracts Outward

The key principle: **Define type contracts first, then implement against those contracts**. This minimizes guesswork and catches errors early.

## Dependency Graph

```
UserPromptData (Pydantic model)
  ↓
DialogueParticle ABC (abstract interface)
  ↓
DialogueChain, ChainSelector (data structures)
  ↓
Concrete Particle Classes (implement ABC)
  ↓
ParticleFactory (uses particles)
  ↓
DialogueService (uses factory, chains, LLMService)
  ↓
ScriptService updates (uses DialogueService)
```

## Sequential Build Plan

### Phase 0: Type Foundation (ESTABLISH CONTRACTS)

**Goal**: Define all type contracts and data structures that everything else depends on.

#### Step 0.1: `dialogue/base.py` - UserPromptData Model
**Why First**: This is the most atomic piece - it defines the exact structure of user prompts. Once this exists with full type hints, we know exactly what fields need to be populated.

**Tasks**:
1. Create `UserPromptData` Pydantic model with:
   - `role: str` (with Field description)
   - `situation: str` (with Field description)
   - `sender: str` (with Field description)
   - `recipient: str` (with Field description)
   - `example1: str`, `example2: str`, `example3: str` (with Field descriptions)
   - `counterexample: str` (with Field description)
   - `last_dialogue_line: Optional[str]` (with Field description)
   - `altitude: Optional[str] = None` (placeholder for future)
   - `inclination: Optional[str] = None` (placeholder for future)
   - `speed: Optional[str] = None` (placeholder for future)
2. Add comprehensive docstring explaining structure matches recommendations.txt
3. Add `model_config` with validation settings
4. **Type Safety**: Once this exists, all code that builds prompts knows exactly what fields to populate

**Dependencies**: None (pure Pydantic model)

**Output**: Complete type contract for user prompts

---

#### Step 0.2: `dialogue/base.py` - DialogueParticle ABC
**Why Second**: Defines the interface contract that all particles must implement. Once this exists with full type hints, we know exactly what methods each particle needs.

**Tasks**:
1. Create `DialogueParticle` abstract base class
2. Define `SYSTEM_PROMPT` class variable (str) with docstring
3. Define `__init__(self, actor: Actor, recipient: str, nav_context: Dict[str, Any])` with:
   - Type hints for all parameters
   - Docstring explaining parameters
   - Instance variable assignments
4. Define abstract methods with full signatures and docstrings:
   - `get_examples(self) -> List[str]` - "Return list of 5+ example dialogue lines"
   - `get_counterexample(self) -> str` - "Return counterexample showing what NOT to do"
   - `get_role_description(self) -> str` - "Return role description like 'Captain Rodriguez, the pilot of STELLAR HORIZON'"
   - `get_situation_description(self) -> str` - "Return situation description from nav_context"
   - `get_format(self) -> DialogueFormat` - "Return expected DialogueFormat"
5. Implement concrete methods with full type hints:
   - `select_examples(self, count: int = 3) -> List[str]`
   - `build_user_prompt_data(self, previous_dialogue: Optional[str] = None) -> UserPromptData`
   - `get_sender_callsign(self) -> str`
   - `format_user_prompt(self, data: UserPromptData) -> str`
6. Add comprehensive class docstring explaining purpose and usage

**Dependencies**: 
- `UserPromptData` (from Step 0.1)
- `Actor` (from models)
- `DialogueFormat` (from schemas)
- `Dict`, `List`, `Optional` (from typing)

**Output**: Complete interface contract for all particles

**Type Safety Benefit**: Once this exists, implementing any particle class is just filling in the abstract methods - no guesswork about what's needed.

---

#### Step 0.3: `dialogue/chain.py` - DialogueChain and ChainSelector
**Why Third**: These are pure data structures with no external dependencies. They define how chains work, which particles need to know.

**Tasks**:
1. Create `DialogueChain` class with:
   - `__init__(self, steps: List[str], weights: Optional[Dict[str, float]] = None)`
   - Type hints: `steps: List[str]`, `weights: Optional[Dict[str, float]]`
   - Docstring explaining chain structure
   - Class methods:
     - `create_standard_chain() -> DialogueChain` (returns ["request", "response", "acknowledgment"])
     - `create_readback_chain() -> DialogueChain` (returns ["request", "response", "readback", "acknowledgment"])
     - `create_extended_chain() -> DialogueChain` (returns ["request", "hold_response", "holding", "adjusted_response", "acknowledgment"])
2. Create `ChainSelector` class with:
   - `CHAIN_WEIGHTS: Dict[str, float]` class variable (typed)
   - `select_chain(self, maneuver_type: str) -> DialogueChain` classmethod
   - Full type hints and docstrings
   - Logic for weighted selection based on maneuver type

**Dependencies**: None (pure data structures)

**Output**: Complete type contract for chain selection

**Type Safety Benefit**: Once this exists, we know exactly what chain types exist and how they're selected.

---

### Phase 1: Concrete Implementations (IMPLEMENT CONTRACTS)

**Goal**: Implement all particle classes against the ABC contract. Order matters - implement base classes before derived classes.

#### Step 1.1: `dialogue/particles.py` - PilotRequest Base Class
**Why First**: This is the base for all pilot request particles. Other request types inherit from it.

**Tasks**:
1.1: Create `PilotRequest` class inheriting from `DialogueParticle`
**Tasks**:
1. Implement `get_role_description(self) -> str`:
   - Type hints: returns `str`
   - Logic: `f"{pilot_name}, the pilot of the {ship_name}"`
   - Docstring explaining format
2. Implement `get_format(self) -> DialogueFormat`:
   - Returns `DialogueFormat.INITIAL_CONTACT`
   - Type hint and docstring
3. Implement `get_situation_description(self) -> str`:
   - Type hints: uses `nav_context: Dict[str, Any]`
   - Logic: builds situation string from nav_context
   - Docstring explaining what it builds
4. Leave `get_examples()` and `get_counterexample()` abstract (subclasses implement)

**Dependencies**: 
- `DialogueParticle` ABC (from Step 0.2)
- `DialogueFormat` (from schemas)

**Output**: Base class for all pilot requests

**Type Safety Benefit**: Once this exists, all specific request types (LaunchRequest, etc.) inherit shared logic and only need to implement examples.

---

#### Step 1.2: `dialogue/particles.py` - Specific Request Classes
**Why Second**: These implement the PilotRequest interface. Order doesn't matter much, but implement all of them.

**Tasks** (for each: LaunchRequest, CircularizationRequest, InsertionRequest):
1. Create class inheriting from `PilotRequest`
2. Implement `get_examples(self) -> List[str]`:
   - Type hint: returns `List[str]`
   - Return 5+ examples using `self.get_sender_callsign()` and `self.recipient`
   - Use `self.nav_context` for maneuver-specific details
   - Docstring: "Return 5+ examples of [maneuver type] requests"
3. Implement `get_counterexample(self) -> str`:
   - Type hint: returns `str`
   - Return specific counterexample for this maneuver type
   - Docstring: "Return counterexample showing what NOT to do"

**Dependencies**: 
- `PilotRequest` (from Step 1.1)

**Output**: Complete request particle classes

**Type Safety Benefit**: Each class is self-contained with clear examples. No guesswork about what examples to use.

---

#### Step 1.3: `dialogue/particles.py` - GenericRequest Fallback
**Why Third**: Provides fallback for unspecified maneuvers.

**Tasks**:
1. Create `GenericRequest` class inheriting from `PilotRequest`
2. Implement `get_examples()` using generic templates
3. Implement `get_counterexample()` with generic counterexample
4. Docstring explaining this is a fallback

**Dependencies**: `PilotRequest` (from Step 1.1)

---

#### Step 1.4: `dialogue/particles.py` - Response and Acknowledgment Classes
**Why Fourth**: These are independent particle types (not request subtypes).

**Tasks** (for each: RadioResponse, RadioAcknowledgment, RadioReadback, HoldResponse, Holding, AdjustedResponse):
1. Create class inheriting from `DialogueParticle` (not PilotRequest)
2. Implement ALL abstract methods:
   - `get_examples(self) -> List[str]`
   - `get_counterexample(self) -> str`
   - `get_role_description(self) -> str`
   - `get_situation_description(self) -> str`
   - `get_format(self) -> DialogueFormat`
3. Full type hints and docstrings for each method

**Dependencies**: `DialogueParticle` ABC (from Step 0.2)

**Output**: Complete set of particle classes

---

### Phase 2: Factory (USES CONCRETE CLASSES)

**Goal**: Create factory that uses all particle classes.

#### Step 2.1: `dialogue/factory.py` - ParticleFactory
**Why Now**: All particle classes exist, so factory can reference them with full type hints.

**Tasks**:
1. Create `ParticleFactory` class
2. Define `REQUEST_PARTICLE_MAP: Dict[str, Type[DialogueParticle]]` class variable:
   - Type hint: maps maneuver type strings to particle classes
   - Populate with: `"launch": LaunchRequest`, `"circularize": CircularizationRequest`, etc.
3. Define `PARTICLE_MAP: Dict[str, Type[DialogueParticle]]` class variable:
   - Type hint: maps generic particle types to classes
   - Populate with: `"response": RadioResponse`, `"acknowledgment": RadioAcknowledgment`, etc.
4. Implement `create_particle(...) -> DialogueParticle` classmethod:
   - Parameters: `particle_type: str`, `actor: Actor`, `recipient: str`, `nav_context: Dict[str, Any]`
   - Return type: `DialogueParticle`
   - Logic: Check REQUEST_PARTICLE_MAP first, then PARTICLE_MAP
   - Full type hints and docstring
5. Implement `register_particle()` and `register_request_particle()` classmethods:
   - Type hints for parameters
   - Docstrings explaining extensibility

**Dependencies**: 
- All particle classes (from Phase 1)
- `DialogueParticle` ABC (for type hints)

**Output**: Factory with complete type safety

**Type Safety Benefit**: Factory methods have full type hints, so callers know exactly what they get back.

---

### Phase 3: Service Layer (USES FACTORY AND CHAINS)

**Goal**: Create DialogueService that orchestrates particles and chains.

#### Step 3.1: `llm_service.py` - Add Structured Outputs Support
**Why First**: DialogueService needs this functionality. Update LLMService contract first.

**Tasks**:
1. Modify `chat()` method signature:
   - Add `use_structured_output: bool = True` parameter
   - Add `format: Optional[Dict] = None` parameter
   - Update docstring
2. Implement structured outputs logic:
   - If `use_structured_output=True` and `format` provided, use Ollama `format` parameter
   - Switch from `completions.create()` to `chat.completions.create()`
   - Handle response extraction from chat completion format
3. Update return type docstring to reflect structured outputs
4. Add type hints for all parameters

**Dependencies**: None (updates existing code)

**Output**: LLMService with structured outputs support

**Type Safety Benefit**: Once this exists, DialogueService knows exactly how to call LLM with structured outputs.

---

#### Step 3.2: `dialogue_server.py` - DialogueService Core Methods
**Why Second**: Build the service layer that uses all the contracts we've defined.

**Tasks**:
1. Create `DialogueService` class with:
   - `__init__(self, llm_service: LLMService)`:
     - Type hint: `llm_service: LLMService`
     - Store as `self.llm_service: LLMService`
     - Initialize `self.chain_selector: ChainSelector = ChainSelector()`
     - Docstring
2. Implement `build_prompt(self, particle: DialogueParticle, previous_dialogue: Optional[DialogueMessage] = None) -> tuple[str, str]`:
   - Type hints: `particle: DialogueParticle`, `previous_dialogue: Optional[DialogueMessage]`
   - Return type: `tuple[str, str]` (system_prompt, user_prompt)
   - Logic: calls `particle.build_user_prompt_data()` and `particle.format_user_prompt()`
   - Docstring explaining what it does
3. Implement `generate_dialogue(self, particle: DialogueParticle, previous_dialogue: Optional[DialogueMessage] = None, temperature: Optional[float] = None) -> DialogueMessage`:
   - Type hints for all parameters
   - Return type: `DialogueMessage`
   - Logic: builds prompt, calls `llm_service.chat()` with structured outputs
   - Docstring explaining structured outputs usage

**Dependencies**: 
- `DialogueParticle` ABC (for type hints)
- `DialogueMessage` (from schemas)
- `LLMService` (from Step 3.1)
- `ChainSelector` (from Step 0.3)

**Output**: Core dialogue generation methods with full type safety

**Type Safety Benefit**: Methods have complete type contracts - callers know exactly what to pass and what they'll get.

---

#### Step 3.3: `dialogue_server.py` - Chain Generation Methods
**Why Third**: Build chain generation on top of single-message generation.

**Tasks**:
1. Implement `generate_chain(self, chain: DialogueChain, pilot: Actor, controller: Actor, nav_context: Dict[str, Any], temperature: Optional[float] = None) -> List[DialogueMessage]`:
   - Type hints: `chain: DialogueChain`, `pilot: Actor`, `controller: Actor`, `nav_context: Dict[str, Any]`
   - Return type: `List[DialogueMessage]`
   - Logic: iterate through `chain.steps`, create particles, generate messages
   - Docstring explaining chain generation process
2. Implement `generate_chain_from_nav_event(self, nav_event: NavigationEvent, pilot: Actor, controller: Actor, nav_context: Dict[str, Any]) -> List[DialogueMessage]`:
   - Type hints for all parameters
   - Return type: `List[DialogueMessage]`
   - Logic: calls `chain_selector.select_chain()`, then `generate_chain()`
   - Docstring explaining entry point for chain generation

**Dependencies**: 
- `DialogueChain` (from Step 0.3)
- `ParticleFactory` (from Step 2.1)
- `generate_dialogue()` (from Step 3.2)
- `NavigationEvent` (from models)

**Output**: Complete chain generation with full type safety

---

### Phase 4: Integration (USES SERVICE LAYER)

**Goal**: Integrate DialogueService into ScriptService.

#### Step 4.1: `script_server.py` - Helper Methods
**Why First**: Build helper methods that ScriptService needs, with full type hints.

**Tasks**:
1. Implement `_build_nav_context(self, nav_event: NavigationEvent, ship: Ship) -> Dict[str, Any]`:
   - Type hints: `nav_event: NavigationEvent`, `ship: Ship`
   - Return type: `Dict[str, Any]`
   - Logic: extracts all nav context from NavigationEvent
   - Docstring explaining what context is built
2. Implement `_get_controller(self, nav_event: NavigationEvent) -> Controller`:
   - Type hints: `nav_event: NavigationEvent`
   - Return type: `Controller`
   - Logic: extracts or creates controller from nav_event
   - Docstring
3. Implement `_convert_messages_to_events(self, messages: List[DialogueMessage], nav_event: NavigationEvent, ship: Ship) -> List[DialogueEvent]`:
   - Type hints: `messages: List[DialogueMessage]`, `nav_event: NavigationEvent`, `ship: Ship`
   - Return type: `List[DialogueEvent]`
   - Logic: converts each DialogueMessage to DialogueEvent with timestamps, metadata
   - Docstring explaining conversion process

**Dependencies**: 
- `NavigationEvent`, `Ship`, `Controller` (from models)
- `DialogueMessage`, `DialogueEvent` (from models/schemas)

**Output**: Helper methods with complete type contracts

**Type Safety Benefit**: Once these exist, `parse_navigation_event()` knows exactly what helpers are available and their signatures.

---

#### Step 4.2: `script_server.py` - Update parse_navigation_event()
**Why Second**: Now we can update the main method with full type safety.

**Tasks**:
1. Update method signature:
   - Change return type: `DialogueEvent` → `List[DialogueEvent]`
   - Add type hints for all parameters
   - Update docstring
2. Add DialogueService import and initialization:
   - Import `DialogueService` from `dialogue_server`
   - Create instance: `dialogue_service = DialogueService(self.llm)`
3. Replace old prompt-building logic with:
   - Call `_build_nav_context()`
   - Call `dialogue_service.generate_chain_from_nav_event()`
   - Call `_convert_messages_to_events()`
   - Return list
4. Remove old prompt-building code (templates, etc.)

**Dependencies**: 
- `DialogueService` (from Step 3.3)
- Helper methods (from Step 4.1)

**Output**: Updated method with full type safety

---

#### Step 4.3: `script_server.py` - Update parse_navigation_events()
**Why Third**: Simple update to handle list return type.

**Tasks**:
1. Update method to use `extend()` instead of `append()`
2. Update docstring to reflect list return type
3. Add type hints if missing

**Dependencies**: Updated `parse_navigation_event()` (from Step 4.2)

---

## Why This Sequence Works

### Type Safety Cascade

1. **Step 0.1-0.3**: Define all contracts first
   - `UserPromptData` → Know exactly what fields to populate
   - `DialogueParticle` ABC → Know exactly what methods to implement
   - `DialogueChain` → Know exactly what chain structures exist

2. **Step 1.1-1.4**: Implement against contracts
   - Each particle class fills in the ABC contract
   - No guesswork - just implement the abstract methods
   - Type hints guide implementation

3. **Step 2.1**: Factory uses typed classes
   - Factory methods have full type hints
   - Know exactly what classes are available
   - Type checker can verify correctness

4. **Step 3.1-3.3**: Service uses typed components
   - Methods have complete type signatures
   - Know exactly what to pass to LLM
   - Know exactly what particles/chains provide

5. **Step 4.1-4.3**: Integration uses typed service
   - Helper methods have clear contracts
   - Main method knows exactly what DialogueService provides
   - Type checker catches integration errors

### Benefits of This Sequence

1. **No Guesswork**: Each step builds on fully-typed contracts
2. **Early Error Detection**: Type checker catches mistakes at each step
3. **Clear Dependencies**: Each step only depends on previous steps
4. **Testable**: Can test each layer independently as it's built
5. **Documentation**: Type hints serve as inline documentation

### Critical Path

The **critical path** (must be done in order):
1. `UserPromptData` → `DialogueParticle` ABC → `DialogueChain`
2. `PilotRequest` → Specific request classes
3. Response/acknowledgment classes
4. `ParticleFactory` (needs all particles)
5. `DialogueService` (needs factory + chains)
6. `ScriptService` updates (needs DialogueService)

### Parallel Opportunities

These can be done in parallel once dependencies are met:
- All specific request classes (LaunchRequest, CircularizationRequest, etc.) - after PilotRequest exists
- All response/acknowledgment classes - after DialogueParticle ABC exists
- Helper methods in ScriptService - after types are defined

## Implementation Checklist

- [ ] Phase 0: Type Foundation (Steps 0.1-0.3)
- [ ] Phase 1: Concrete Implementations (Steps 1.1-1.4)
- [ ] Phase 2: Factory (Step 2.1)
- [ ] Phase 3: Service Layer (Steps 3.1-3.3)
- [ ] Phase 4: Integration (Steps 4.1-4.3)

Each step builds on the previous, with full type safety reducing guesswork and errors.

