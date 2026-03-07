# Test Coverage Improvement

This is not a "make the number go up" plan.

The goal is to improve **diagnostic value**: tests that fail for a useful reason, point at a real problem, and protect behavior we actually care about.

Current baseline:
- `pytest -m "not slow"`: **387 passed**, **14 deselected**
- App coverage: roughly **77%** on active `mysite/universe` code

---

## Principles

When deciding whether to keep, add, or rewrite a test, prefer:

1. **Tests that protect important invariants**
   - actor/event bookkeeping
   - route planning correctness
   - event ordering and time gating
   - audio worker queue semantics

2. **Tests that fail close to the bug**
   - not "the UI looks weird"
   - yes "this function returned a malformed dialogue message"

3. **Tests that isolate application behavior**
   - not "is Ollama feeling cooperative today?"
   - yes "when the LLM returns malformed JSON, we retry / fail clearly"

4. **Tests that cover meaningful branches**
   - not just "list is non-empty"
   - yes "arrival maneuver chooses destination body, departure maneuver chooses origin body"

---

## Keep As-Is

These parts of the suite are already doing useful work.

### Route planning / navigation
- `tests/test_route_planning.py`
- `tests/test_navigation.py`
- `tests/test_location_service.py`
- `tests/test_controller_fallback.py`

Why keep:
- High business value
- Strong invariants
- Good failure locality
- Protects the "physics + routing + controller assignment" spine of the project

### Simulation timing and event feed basics
- `tests/test_simulation.py`
- `tests/test_simulation_views.py`
- `tests/test_event_feed.py`

Why keep:
- These protect time gating, cursor semantics, and simulation controls
- Regressions here would make the whole ambient simulation feel wrong immediately

### Audio worker and audio endpoint tests
- `tests/test_audio_worker.py`
- `tests/test_audio_views.py`

Why keep:
- These now encode real architectural decisions
- They protect queue behavior, retry semantics, stale lock cleanup, and worker/web integration

### Import/export and procedural generation
- `tests/test_import_export.py`
- `tests/test_procedural_generation.py`

Why keep:
- High-value core functionality
- Good examples of tests that validate real project behavior rather than scaffolding

---

## Rewrite / Downgrade

These tests are not necessarily bad, but they currently provide less diagnostic value than their cost suggests.

### `tests/test_LLM.py`

Current role:
- "Is the local LLM endpoint up?"
- "Did the model answer YES/NO?"
- "Does the model know a space fact?"

Problems:
- Very environment-sensitive
- Failures often reflect GPU pressure, model loading, or Ollama state rather than application bugs
- They do not strongly validate Solar's own LLM integration behavior

Recommendation:
- Keep **one** or **two** smoke tests for endpoint availability
- Move the rest into a clearly marked "environment sanity" category, or remove them

Better replacement:
- More tests like `test_llm_service.py`
- Mock-based tests that verify:
  - transport error handling
  - JSON-mode behavior
  - quiet/non-quiet behavior
  - structured-output validation

### Parts of `tests/test_dialogue_particles.py`

Current role:
- examples are non-empty
- examples contain keywords like "azimuth" or "hyperspace"
- examples are diverse

Problems:
- Keyword presence is weaker than semantic correctness
- These tests will not catch vague, contradictory, or operationally nonsensical examples

Recommendation:
- Keep the structural tests
- Add a small number of **semantic invariants**

Examples of stronger assertions:
- controller launch response includes at least one concrete flight parameter when physics params are available
- readback examples do not invent units irrelevant to the maneuver
- transfer/hyperspace readbacks do not invent kilometers when only azimuth was given

---

## High-Value Missing Tests

These are the best targets for the next few passes.

### 1. `mysite/universe/services/dialogue_server.py`
Coverage is very low and this file is central.

Add tests for:
- `build_prompt()` rejects `SatelliteResponse`
- `generate_dialogue()` uses pre-programmed path for satellites
- `generate_dialogue()` retries on malformed JSON
- `generate_dialogue()` strips callsigns from LLM-provided message content
- `generate_dialogue()` raises clearly after retry exhaustion
- `_select_next_particle_type()` when:
  - probabilities are empty
  - total is zero
  - probabilities sum to less than 1.0
- chain termination behavior in `generate_chain_iteratively()`

Why this matters:
- This file sits at the center of particles, LLM responses, and message construction
- A bug here can create plausible-looking but broken dialogue everywhere

### 2. `mysite/universe/services/controller_physics.py`
Low coverage, high domain importance.

Add tests for:
- `get_relevant_body()` for:
  - arrival maneuvers
  - departure maneuvers
  - transfer maneuvers
  - missing controller location
  - station target resolving to its parent body
- parameter generation for:
  - launch
  - circularization
  - insertion
  - sublight
  - hyperspace
  - plane change
  - deorbit
  - landing/dock
- fallback behavior when names or bodies are missing

Why this matters:
- These values are literally what controllers tell ships to do
- Bad physics parameters make the simulation sound wrong even if everything else is functioning

### 3. `mysite/universe/views/events.py`

Add tests for:
- `_resolve_voice_for_event()` branches:
  - `voice_id` in metadata
  - actor missing
  - missing audio profile
  - missing voice template
- `clear_events()` / `clear_all_events()`:
  - deletes DB rows
  - deletes audio files
  - clears cache
- health endpoint:
  - LLM responding
  - LLM unavailable
  - worker active
  - worker idle
  - worker warning state

Why this matters:
- This is where real runtime weirdness tends to surface first

### 4. `mysite/universe/services/audio_plans.py`

Add tests for:
- pilot/controller room tone branches
- satellite no-room-tone branch
- modem noise plan structure for satellites
- static layer inclusion/exclusion
- fallback behavior when actor/profile data is incomplete

Why this matters:
- We recently found real bugs here
- This is the point where "sounds right" becomes encoded policy

---

## Existing Tests That Still Miss Important Conditions

### `tests/test_event_feed.py`
Good baseline, but missing:
- malformed `limit`
- more cursor tie-break edge cases for duplicate timestamps
- behavior around `audio_ready` when file and cache state diverge
- health-related event feed expectations, if any are added later

### `tests/test_audio_worker.py`
Strong overall, but still missing:
- explicit warmup test coverage
- room tone path resolution
- modem noise branch validation
- behavior when referenced audio assets are missing
- actor-less event handling / loud failure policy

### `tests/test_dialogue_particles.py`
Good breadth, but missing:
- semantic checks for controller specificity
- checks against wishy-washy or contradictory examples
- checks that response/readback examples reflect the maneuver category correctly

---

## Low-Priority or Low-Value Areas

These should not be the focus just to raise the percentage.

### `manage.py`, `wsgi.py`, migrations
Do not chase coverage here.

### Infinite-loop command runners
Examples:
- `audio_worker.py` main loop
- `start_simulation_loop.py`

Test the decision logic and helpers, not the forever-loop mechanics.

### Dev-only endpoints / tooling
Examples:
- some of `views/logs.py`
- shallow template render checks beyond smoke coverage

Keep smoke tests, but don’t over-invest unless the tool becomes central.

---

## Suggested Next Passes

### Pass 1: Add tests
1. `dialogue_server.py`
2. `controller_physics.py`
3. `views/events.py` edge cases

### Pass 2: Strengthen tests
1. semantic invariants in `test_dialogue_particles.py`
2. audio plan branch tests
3. worker warmup / asset-resolution tests

### Pass 3: Prune or downgrade noisy tests
1. collapse `tests/test_LLM.py` into smaller smoke coverage
2. remove low-information keyword-only dialogue checks if better semantic tests replace them

---

## Summary

The suite is already strong in the areas that define the simulation:
- world model
- route planning
- timing
- actor/event integrity
- audio worker core behavior

The biggest remaining blind spots are:
- **dialogue orchestration**
- **controller physics**
- **audio plan branching**
- **view-layer edge cases**

If we improve those, we’ll get better diagnostics and likely higher coverage as a side effect.
