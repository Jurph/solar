# LLM Service Deduplication TODO

## Test-Driven Development Plan

Based on test failures, here's what needs to be done to unify `LLMService` and `LLMJSONService`.

## Current Test Status

✅ **67 tests passing** - Basic functionality works
❌ **1 test failing** - `test_json_dialogue_generation` - JSON extraction issue

## Test Failure Analysis

**Failure:** `test_json_dialogue_generation`
- **Issue:** Response wrapped in markdown code blocks: ````json\n{...}\n````
- **Expected:** Raw JSON string starting with `{`
- **Root Cause:** `LLMService.chat()` doesn't extract JSON from markdown code blocks like `LLMJSONService.chat()` does

## TODO List (In Order)

### 1. Extract Shared Helper Methods
- [ ] Extract `_parse_context_messages()` - Context parsing logic (lines 175-217 in both classes, identical)
- [ ] Extract `_build_dialogue_context()` - Dialogue context building (lines 219-246 in LLMService, similar in LLMJSONService)
- [ ] Extract `_determine_expected_format()` - Format determination logic (lines 248-257 in LLMService, similar in LLMJSONService)
- [ ] Extract `_determine_recipient_callsign()` - Recipient determination (scattered in both)

### 2. Merge `chat()` Method
- [ ] Replace `LLMService.chat()` with `LLMJSONService.chat()` implementation
  - **Why:** `LLMJSONService.chat()` has:
    - JSON schema validation in system prompt
    - JSON extraction from markdown code blocks (lines 598-609)
    - Better error handling
    - Logging support
- [ ] **BUT:** Keep `LLMService.chat()` signature for backward compatibility:
  - Support `system_prompt` parameter (from old `LLMService.chat()`)
  - Support both plain text mode and JSON mode
  - **Decision needed:** Should `chat()` always return JSON, or have a mode parameter?

### 3. Merge `get_actor_json_response()` Method
- [ ] Replace `LLMService.get_actor_json_response()` with `LLMJSONService.get_actor_json_response()` implementation
  - **Why:** `LLMJSONService` version has:
    - Better acknowledgment handling (lines 728-814)
    - More robust error recovery (lines 1044-1092)
    - Better recipient determination logic
    - More detailed prompts
- [ ] Use shared helper methods from step 1

### 4. Keep `generate_with_system_prompt()` Method
- [ ] This method exists only in `LLMService` (lines 123-146)
- [ ] Keep it - it's used by tests and may be useful for simple text generation
- [ ] Ensure it works with the merged `chat()` method

### 5. Remove `LLMJSONService` Class
- [ ] After merging, delete the `LLMJSONService` class definition (lines 456-1092)
- [ ] Update all imports:
  - [ ] `character_dialogue_demo.py` (line 29, 98)
  - [ ] `script_server.py` (lines 40-42, 380-381)
  - [ ] Any other references

### 6. Update Production Code
- [ ] `character_dialogue_demo.py`: Remove `LLMJSONService` import, use `LLMService` only
- [ ] `script_server.py`: 
  - Remove `LLMJSONService` import and type check (lines 379-381)
  - Update `get_instance()` to use `LLMService` only (lines 39-46)

### 7. Verify All Tests Pass
- [ ] Run `pytest tests/test_LLM.py` - should all pass
- [ ] Run `pytest tests/test_space_traffic_llm.py` - should all pass
- [ ] Run full test suite to ensure no regressions

## Key Design Decisions Needed

1. **`chat()` method behavior:**
   - Option A: Always return JSON (like `LLMJSONService`)
   - Option B: Have a `json_mode` parameter to toggle
   - Option C: Detect if JSON is requested based on system prompt
   - **Recommendation:** Option A - always return JSON, validate it

2. **`generate_with_system_prompt()` behavior:**
   - Should it return plain text or JSON?
   - **Recommendation:** Keep as plain text for backward compatibility, but document it

3. **Error handling:**
   - `LLMJSONService` raises exceptions
   - `LLMService` returns error strings
   - **Recommendation:** Use exceptions (better for error handling)

## Implementation Order

1. Extract shared helpers (low risk, no behavior change)
2. Merge `chat()` method (fixes test failure)
3. Merge `get_actor_json_response()` (improves robustness)
4. Update production code references
5. Remove `LLMJSONService` class
6. Run full test suite

## Notes

- The `model_name` parameter removal in `main()` was correct - `__init__()` reads from config file
- Test failure is **expected and helpful** - it shows exactly what needs to be merged
- All 67 other tests passing means basic functionality is solid

