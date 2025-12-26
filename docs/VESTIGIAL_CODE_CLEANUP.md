# Vestigial Code Cleanup Plan

## Status: ⚠️ NEEDS UPDATE (document was written against an older code snapshot)

This document was written when reply generation and JSON-response helpers were still active.
As of late Dec 2025, several items listed below no longer exist in the codebase and the line
references are stale.

## Current Usage

### Previously Active (verify before acting)

1. **`LLMService.get_actor_json_response()`**
   - **NOTE:** This method name no longer appears in the current codebase.
   - If you see similar behavior today, it likely lives in `LLMService.chat()` and/or dialogue-server code.

2. **`ScriptService.parse_dialogue_event()`**
   - **NOTE:** This method name no longer appears in the current `script_server.py`.
   - Dialogue is generated as full chains via `ScriptService.parse_navigation_events()` and DialogueService.

3. **Old Prompt Building Methods** (all in `script_server.py`):
   - **NOTE:** These method names no longer appear in the current file; prompts are particle-driven.

## Cleanup Plan (rewrite needed)

Recommendation: rewrite this document around *current* cleanup targets (if any) by first
grepping the codebase for the methods you plan to remove and capturing their current call sites.

### Step 1: Remove Old Prompt Building Methods

**File**: `mysite/universe/services/script_server.py`

Remove these methods (replaced by particle system):
- [ ] `build_situation_prompt()` - line 775
- [ ] `get_dialogue_context()` - line 783
- [ ] `format_context_for_llm()` - line 792
- [ ] `build_controller_examples()` - line 818
- [ ] `build_pilot_examples()` - line 831

**Rationale**: These methods build prompts manually. The particle system (`DialogueParticle`, `UserPromptData`) replaces all of this.

### Step 2: Deprecate `get_actor_json_response()`

**File**: `mysite/universe/services/llm_service.py`

- [ ] Add deprecation warning to `get_actor_json_response()`
- [ ] Update docstring: "DEPRECATED: Use DialogueService.generate_dialogue() instead"
- [ ] Keep method for backward compatibility during migration period
- [ ] Remove after all callers migrated (see Step 3)

**Rationale**: `DialogueService.generate_dialogue()` uses structured outputs and particles, replacing this method.

### Step 3: Update Callers of `get_actor_json_response()`

**Files to update**:
- [ ] `script_server.py` line 387 (`parse_navigation_event()`)
- [ ] `script_server.py` line 548 (`parse_dialogue_event()` - controller response)
- [ ] `script_server.py` line 693 (`parse_dialogue_event()` - pilot acknowledgment)
- [ ] `test_LLM.py` line 197 (update test to use DialogueService)

**Action**: Replace calls with `DialogueService.generate_dialogue()` or `generate_chain_from_nav_event()`

### Step 4: Deprecate `parse_dialogue_event()`

**File**: `mysite/universe/services/script_server.py`

- [ ] Add deprecation warning: "DEPRECATED: Chains are now generated upfront. Use DialogueService.generate_chain_from_nav_event() instead"
- [ ] Update docstring
- [ ] Keep method for backward compatibility
- [ ] Remove after `expect_reply_action()` updated (see Step 5)

**Rationale**: Chains are generated upfront, so dynamic reply generation is no longer needed.

### Step 5: Update `expect_reply_action()`

**File**: `mysite/universe/models/event.py`

**Current behavior** (lines 148, 153):
- Calls `ScriptService.parse_dialogue_event()` to generate replies dynamically

**New behavior** (after chains):
- Chains are complete sequences generated upfront
- If `expect_reply=True`, the next event in the chain is already generated
- Remove dynamic reply generation logic

**Decision needed**: 
- Option A: Chains are complete - remove `parse_dialogue_event()` calls entirely
- Option B: Some events still need dynamic replies - keep but simplify

**Recommendation**: Option A - chains are complete sequences.

### Step 6: Remove Old Prompt Building Code from `parse_navigation_event()`

**File**: `mysite/universe/services/script_server.py`

Remove old prompt building logic (lines ~360-410):
- [ ] Template selection logic
- [ ] Manual prompt construction
- [ ] Old `nav_context` building (replaced by `_build_nav_context()` helper)

**Action**: Replace with `DialogueService.generate_chain_from_nav_event()` call

### Step 7: Remove Old Prompt Building Code from `parse_dialogue_event()`

**File**: `mysite/universe/services/script_server.py`

Remove old prompt building logic (lines ~450-700):
- [ ] Manual controller response prompt building
- [ ] Manual pilot acknowledgment prompt building
- [ ] Old `nav_context` extraction from metadata

**Action**: This entire method will be deprecated/removed (see Step 4)

### Step 8: Clean Up Imports

**Files**: Various

Remove unused imports:
- [ ] Check `script_server.py` for unused imports after cleanup
- [ ] Check `llm_service.py` for unused imports after cleanup

### Step 9: Update Tests

**Files**: `tests/test_LLM.py`, `tests/test_space_traffic_llm.py`

- [ ] Update `test_json_dialogue_generation` to use DialogueService
- [ ] Update integration tests to expect `List[DialogueEvent]` from `parse_navigation_event()`
- [ ] Add tests for chain generation

## Migration Checklist

Before removing any code:

- [ ] Phase 4 integration complete (`parse_navigation_event()` returns `List[DialogueEvent]`)
- [ ] All callers updated to handle list return type
- [ ] `expect_reply_action()` updated (no longer calls `parse_dialogue_event()`)
- [ ] All tests passing with new system
- [ ] Deprecation warnings added and migration period elapsed

## Estimated Lines of Code to Remove

- `script_server.py`: ~500-600 lines (old prompt building + `parse_dialogue_event()`)
- `llm_service.py`: ~400 lines (`get_actor_json_response()`)
- **Total**: ~900-1000 lines of vestigial code

## Benefits After Cleanup

1. **Simpler codebase**: Remove ~1000 lines of complex prompt-building code
2. **Single source of truth**: All prompts come from particles
3. **Better maintainability**: Particle system is modular and extensible
4. **Type safety**: Full type hints throughout
5. **Testability**: Particles can be tested independently

