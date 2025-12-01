# Dialogue Quality Improvement Backlog

Based on analysis of 25 llama3 runs (average score: 68/100, range: 53-74) and ChatGPT evaluation critiques.

## Critical Issues (Score 0-1)

### 1. JSON/Metadata/Template Leakage (Score 0)
**Problem:** JSON blobs, template variables like `${current_situation...}`, and structured data appearing in dialogue output.

**Examples:**
- `{"role": "CONTROLLER", "speaker_callsign": "Mars Control", ...}`
- `${current_situation.maneuver_type} maneuver in progress. Current location: ${current_situation.current_location}`

**Impact:** These events automatically score 0, dragging down entire runs.

**Potential Solutions:**
- [ ] Add stronger validation/filtering in `_validate_text_is_natural_language()` to catch and retry on JSON/metadata leakage
- [ ] Add retry logic: if response contains JSON/metadata, regenerate with stricter prompt
- [ ] Add post-processing filter that detects and strips template variables before returning text
- [ ] Strengthen prompt warnings: "CRITICAL: Your response must be natural dialogue, NOT structured data, NOT JSON, NOT template variables"

### 2. "Error in communications" Fallbacks (Score 1)
**Problem:** Non-sequitur fallback messages appearing in dialogue.

**Examples:**
- "Captain Rodriguez here. Error in communications."

**Impact:** These score only 1 point, indicating system-level failures.

**Potential Solutions:**
- [ ] Add retry logic: if response contains "Error in communications" or similar fallbacks, regenerate
- [ ] Investigate root cause - why is LLM generating these fallbacks?
- [ ] Add detection and filtering for common error phrases

## Grammar/Terminology Issues (Score 2)

### 3. Poor Grammar: "beginning circularize" / "beginning sublight" (Score 2)
**Problem:** Incorrect verb forms appearing frequently.

**Examples:**
- "Acknowledged, beginning circularize" (should be "beginning circularization" or "beginning the circularization burn")
- "Acknowledged, beginning sublight" (should be "beginning sublight burn" or "executing sublight burn")

**Impact:** These score only 2 points instead of 3-4.

**Potential Solutions:**
- [ ] Add hidden imperative field in prompt: `"imperative_maneuver": "begin a sublight burn"` or `"imperative_maneuver": "circularize the orbit"`
- [ ] Strengthen grammar examples in prompts with correct forms
- [ ] Add post-processing grammar correction for common patterns
- [ ] Update acknowledgment examples to show correct grammar: "beginning the circularization burn", "executing sublight burn"

## Context Usage Issues (Score 3 vs 5)

### 4. Controllers Not Using Context (Score 3 instead of 5)
**Problem:** Controllers frequently say generic "Cleared for maneuver" instead of echoing the specific maneuver requested.

**Examples:**
- Pilot: "Requesting clearance for sublight maneuver"
- Controller: "STELLAR HORIZON, Mars Control. Cleared for maneuver." (3 points)
- Should be: "STELLAR HORIZON, Mars Control. Cleared for sublight maneuver." (5 points)

**Impact:** Missing 2 points per controller response - significant score loss across 25 runs.

**Potential Solutions:**
- [ ] Add context cue right before response: "With all that in mind, here's the previous line from the pilot: '[PILOT'S REQUEST]'. Respond naturally and use context from the dialogue to respond."
- [ ] Add hidden imperative field: `"imperative_maneuver": "clear the pilot for sublight maneuver"` or `"imperative_maneuver": "approve the deorbit request"`
- [ ] Strengthen controller prompt: "CRITICAL: You MUST mention the specific maneuver they requested. If they asked for 'sublight', say 'cleared for sublight'. If they asked for 'deorbit', say 'cleared for deorbit'."
- [ ] Add examples showing context usage: "When pilot requests 'sublight maneuver', respond with 'Cleared for sublight maneuver', not just 'Cleared for maneuver'."

### 5. Pilot Acknowledgments Missing Context (Score 3 instead of 4-5)
**Problem:** Pilot acknowledgments are often generic "Roger" or "Acknowledged" without referencing the approved maneuver.

**Examples:**
- Controller: "Cleared for sublight maneuver"
- Pilot: "Roger, proceeding as directed." (3 points)
- Should be: "Acknowledged, beginning sublight burn." (4 points) or "Acknowledged, executing sublight burn now." (5 points)

**Impact:** Missing 1-2 points per acknowledgment.

**Potential Solutions:**
- [ ] Add context cue: "With all that in mind, here's what the controller just approved: '[CONTROLLER'S APPROVAL]'. Acknowledge naturally and reference the approved maneuver."
- [ ] Add hidden imperative field: `"imperative_maneuver": "acknowledge the sublight clearance and begin the burn"`
- [ ] Strengthen acknowledgment examples to show maneuver reference: "Acknowledged, beginning the sublight burn" instead of just "Acknowledged"
- [ ] Update acknowledgment instruction to emphasize: "Echo back the approved maneuver in your acknowledgment"

## Prompt Structure Improvements

### 6. Add Context Cue Before Response Request
**Problem:** LLM may not be focusing on the immediate dialogue context when generating responses.

**Solution:**
- [ ] Add to user prompt, right before asking for response:
  ```
  With all that in mind, here's the previous line from [SPEAKER]:
  "[PREVIOUS_LINE]"
  
  Respond naturally and use context from the dialogue to respond.
  ```
- [ ] This should appear AFTER all the instructions but RIGHT BEFORE the JSON schema/example

### 7. Add Hidden Imperative Maneuver Fields
**Problem:** LLM may not understand the specific action required.

**Solution:**
- [ ] Add hidden JSON field in system prompt (not in output schema):
  ```json
  {
    "imperative_maneuver": "clear the pilot for sublight maneuver",
    "imperative_maneuver": "acknowledge the deorbit clearance and begin the burn",
    "imperative_maneuver": "request clearance for insertion burn into Mars orbit"
  }
  ```
- [ ] These should be in comments or as "internal notes" that guide the LLM but aren't part of the output
- [ ] Format: "INTERNAL CONTEXT (not part of your response): imperative_maneuver: [specific action]"

## Error Handling & Retry Logic

### 8. Implement Retry Logic for Failed Responses
**Problem:** When LLM generates JSON/metadata leakage or error fallbacks, we currently just accept them.

**Solution:**
- [ ] Add retry mechanism in `get_actor_json_response()`:
  - If response contains JSON/metadata → retry with stricter prompt
  - If response contains "Error in communications" → retry
  - If response contains template variables → retry
  - Max 2-3 retries before falling back to error message
- [ ] Add exponential backoff between retries
- [ ] Log retry attempts for analysis

### 9. Improve Response Validation
**Problem:** Current validation may not catch all failure modes.

**Solution:**
- [ ] Enhance `_validate_text_is_natural_language()` to detect:
  - Template variables (${...})
  - JSON objects
  - Metadata patterns
  - Error fallback phrases
- [ ] Return validation result that triggers retry if needed

## Destination/Phase Confusion

### 10. Strengthen Navigation Context in Prompts
**Problem:** Some confusion about current location vs destination (e.g., "towards Mars" when going to Earth).

**Solution:**
- [ ] Add explicit navigation context to prompts:
  ```
  NAVIGATION CONTEXT:
  - Current location: [CURRENT]
  - Destination: [DESTINATION]
  - You are going FROM [CURRENT] TO [DESTINATION]
  - Do NOT mention going to [CURRENT] - you're already there!
  ```
- [ ] Add to hidden imperative: `"imperative_navigation": "going from Mars to Earth"`

## Implementation Priority

**High Priority (Biggest Score Impact):**
1. #4 - Controllers using context (2 points per response × ~6 controllers = 12 points potential)
2. #1 - JSON/metadata leakage (0 points per event, can kill entire runs)
3. #6 - Context cue before response (should help with #4 and #5)

**Medium Priority:**
4. #5 - Pilot acknowledgments using context (1-2 points per acknowledgment)
5. #3 - Grammar fixes (1 point per event)
6. #8 - Retry logic (prevents 0-1 point failures)

**Low Priority (Polish):**
7. #2 - Error fallback detection
8. #7 - Hidden imperative fields (experimental)
9. #9 - Enhanced validation
10. #10 - Navigation context strengthening

## Notes

- Average score: 68/100 (68%)
- Best run: 74/100 (Run 24)
- Worst run: 53/100 (Run 3)
- Satellite behavior: Nearly perfect (consistently 3/3)
- Main opportunity: Controller context usage (could gain ~12 points per run)

