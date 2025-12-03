# LLM Safety Net Test Plan

## Overview
These tests verify the safety net functions that validate and correct LLM responses. **No actual LLM calls** - we mock bad responses and verify the safety nets catch and fix them.

## Functions Under Test

1. `_is_bad_llm_output()` / `bad_msg_re` regex (in `llm_service.py`)
2. `_validate_text_is_natural_language()` (in `script_server.py`)
3. `_extract_message_from_response()` (in `script_server.py`)
4. Recipient correction logic (in `llm_service.py`)
5. Retry logic with safety fence (in `llm_service.py`)
6. JSON parsing and schema detection (in `llm_service.py`)

---

## Test Categories

### 1. Bad Message Content Detection (`bad_msg_re` regex)

**Pattern: `r"\$\{|\{\s*\"|Error in communication"`**

#### 1.1 Template Variable Detection
- [ ] **Test**: Message contains `${...}` pattern (e.g., `${current_situation.maneuver_type}`) → should trigger retry
- [ ] **Test**: Message contains `$` but not `${` (e.g., "cost $100") → should NOT trigger retry

#### 1.2 JSON Fragment Detection
- [ ] **Test**: Message contains `{ "` pattern (e.g., `{ "role": "PILOT"`) → should trigger retry
- [ ] **Test**: Message contains `{` but not `{ "` (e.g., "{hello}") → should NOT trigger retry

#### 1.3 Error Fallback Detection
- [ ] **Test**: Message contains "Error in communication" (case-insensitive) → should trigger retry
- [ ] **Test**: Message contains "communication error" (reversed word order) → should NOT trigger retry

#### 1.4 Combined Bad Patterns
- [ ] **Test**: Message contains multiple bad patterns (e.g., `${...}` AND `{ "`) → should trigger retry

#### 1.5 Edge Cases
- [ ] **Test**: Empty or None message → should NOT trigger retry (handled earlier)

---

### 2. Recipient Correction Logic

#### 2.1 Speaker/Recipient Reversal
- [ ] **Test**: LLM returns wrong recipient (reversed or incorrect) → should correct to actual recipient
- [ ] **Test**: LLM returns correct recipient → should NOT modify
- [ ] **Test**: LLM returns null or empty recipient → should correct to actual recipient

#### 2.2 Wrong Recipient Callsign
- [ ] **Test**: LLM returns placeholder or template variable as recipient (e.g., "CONTROL", "$SHIP") → should correct to actual recipient

#### 2.3 Recipient Correction with Bad Message Content
- [ ] **Test**: LLM returns wrong recipient AND bad message content → should correct recipient AND trigger retry

---

### 3. JSON Parsing and Extraction

#### 3.1 Valid JSON Responses
- [ ] **Test**: Clean JSON with all required fields → should parse and extract message
- [ ] **Test**: JSON with escaped characters in message → should parse correctly
- [ ] **Test**: JSON wrapped in markdown code blocks → should strip markdown and parse

#### 3.2 Schema Definition Detection
- [ ] **Test**: Response is schema definition (contains `"$defs"` or `"properties"` + `"type"`) → should detect and extract embedded message
- [ ] **Test**: Schema with no embedded message → should raise ValueError
- [ ] **Test**: Schema with embedded message that has bad content → should extract, detect bad content, trigger retry

#### 3.3 Malformed JSON
- [ ] **Test**: JSON parsing fails (malformed) → should try regex extraction fallback

#### 3.4 Missing or Invalid Fields
- [ ] **Test**: JSON missing required fields (e.g., `"message"`, `"role"`) → should raise ValueError or use fallback
- [ ] **Test**: JSON with invalid enum values or wrong types → should handle conversion error

#### 3.5 Regex Extraction Fallbacks
- [ ] **Test**: Malformed JSON, regex finds `"message": "text"` → should extract and unescape message
- [ ] **Test**: Malformed JSON, regex finds nothing → should return error message

---

### 4. Message Text Extraction (`_extract_message_from_response`)

#### 4.1 JSON Response Extraction
- [ ] **Test**: Valid DialogueMessage JSON → should return (message_text, DialogueMessage_obj)

#### 4.2 Plain Text Response
- [ ] **Test**: Plain text response (no JSON) → should return (text, None)

#### 4.3 Schema Response Extraction
- [ ] **Test**: Schema definition with embedded message → should extract embedded message
- [ ] **Test**: Schema definition with no message → should return error message

#### 4.4 Error Cases
- [ ] **Test**: Response is None or not a string → should handle gracefully

---

### 5. Natural Language Validation (`_validate_text_is_natural_language`)

#### 5.1 JSON Input
- [ ] **Test**: Input is JSON string → should extract message field (via DialogueMessage or regex)

#### 5.2 Plain Text Input
- [ ] **Test**: Input is plain text → should return as-is

#### 5.3 Edge Cases
- [ ] **Test**: Input is None or not a string → should return "[Error: Invalid text]"

---

### 6. Retry Logic with Safety Fence

#### 6.1 Retry Triggering
- [ ] **Test**: First attempt has bad message content → should retry (attempt 1)
- [ ] **Test**: Second attempt has bad message content → should retry (attempt 2)
- [ ] **Test**: Third attempt has bad message content → should NOT retry, return anyway (max retries reached)
- [ ] **Test**: First attempt passes safety fence → should return immediately (no retry)

#### 6.2 Retry with Different Bad Patterns
- [ ] **Test**: Attempt 1 has bad pattern, attempt 2 passes → should return attempt 2
- [ ] **Test**: All 3 attempts have bad patterns → should return attempt 3 (after max retries)

#### 6.3 Retry with Recipient Correction
- [ ] **Test**: Attempt 1 has wrong recipient AND bad message → should correct recipient, then retry for bad message

#### 6.4 Retry with Schema Extraction
- [ ] **Test**: Attempt 1 is schema with bad message, attempt 2 passes → should extract from schema, retry, then return attempt 2
- [ ] **Test**: Attempt 1 is schema with good message → should extract and return (no retry)

---

### 7. Fallback Response Construction

#### 7.1 JSON Parsing Failure Fallback
- [ ] **Test**: JSON parsing fails, recipient available → should construct fallback JSON with recipient
- [ ] **Test**: JSON parsing fails, no recipient available → should raise ValueError

#### 7.2 Top-Level Exception Fallback
- [ ] **Test**: Exception during processing → should return "Error in communications" message with correct recipient

#### 7.3 Fallback Message Format
- [ ] **Test**: Fallback message format is valid DialogueMessage JSON with correct role, speaker, and recipient

---

### 8. Integration Tests (Multiple Safety Nets)

#### 8.1 Full Pipeline with Bad Input
- [ ] **Test**: LLM returns JSON with wrong recipient AND bad message → should correct recipient, detect bad message, retry
- [ ] **Test**: LLM returns schema with embedded message that has bad content → should extract, detect bad content, retry

#### 8.2 Full Pipeline with Good Input After Retry
- [ ] **Test**: Attempt 1 has issues (wrong recipient + bad message OR schema with bad message), Attempt 2 is good → should return attempt 2

#### 8.3 Full Pipeline with All Retries Failing
- [ ] **Test**: All 3 attempts fail (bad message content OR JSON parsing failure) → should return attempt 3 or construct fallback

---

## Test Implementation Notes

### Mocking Strategy
- Mock `self.chat()` to return predetermined bad responses
- Test each safety net function in isolation where possible
- Use dependency injection to test retry logic without actual LLM calls

### Test Data
- Create fixtures for common bad response patterns
- Create fixtures for valid DialogueMessage objects
- Create fixtures for schema definitions

### Assertions
- Verify retry count (should not exceed max_retries)
- Verify recipient correction (should match expected recipient)
- Verify message content (should not contain bad patterns after processing)
- Verify return format (should always be valid JSON string for DialogueMessage)

### Code Organization
- Consider extracting safety net functions to testable modules if needed
- Keep tests fast (no actual LLM calls)
- Keep tests deterministic (same input → same output)

---

## Priority Order

**High Priority (Must Have):**
1. Bad message content detection (all patterns)
2. Recipient correction logic
3. Retry logic with max retries
4. JSON parsing with schema detection

**Medium Priority (Should Have):**
5. Message extraction edge cases
6. Natural language validation
7. Fallback response construction

**Low Priority (Nice to Have):**
8. Complex integration scenarios
9. Unicode/edge case handling
10. Performance tests (if needed)

