# Test Coverage Improvement

Current baseline:
- Test suite size is now in the **500+ test** range
- Earlier low-coverage hotspots such as `dialogue_server.py`, `controller_physics.py`, `events` view edges, and `audio_plans.py` have already received dedicated test passes
- App coverage is still useful to monitor, but the main focus of this document is **where the remaining testing risks are**

This document is about **test risk**, not coverage theater.

The right question is not "where can we add assertions?" The right question is:

> Where does the current suite create a false sense of safety?

There are three main failure modes in the current coverage picture:

1. **False security from tests that do not tell us anything useful**
2. **False security from tests that touch code, but do not really exercise the important logic**
3. **Glaring gaps where important code is barely tested or not tested at all**

---

## 1. False Security from Meaningless Tests

These tests may pass often, but their failures do not diagnose application regressions well.

### `tests/test_LLM.py`

This file mostly tests the local model environment, not the application.

Examples:
- endpoint responds
- model says YES/NO briefly
- model knows a space fact

Why this is risky:
- failures are often caused by GPU pressure, model loading, or Ollama state
- a passing result does not tell us much about whether Solar is using the LLM correctly
- a failing result often tells us only that local infrastructure is unhappy

Diagnostic value:
- **low** as application tests
- **acceptable** as developer-environment smoke checks

What to do:
- keep one or two basic availability/smoke checks
- do not treat the rest as core quality signal
- prefer `test_llm_service.py`-style tests for real application behavior

### Shallow keyword/content checks in `tests/test_dialogue_particles.py`

A number of these tests check things like:
- example list is non-empty
- examples contain a keyword like `"azimuth"` or `"hyperspace"`
- examples are "diverse"

Why this is risky:
- a test can pass while examples remain vague, contradictory, or operationally wrong
- these tests can make us think the dialogue content is validated when it is mostly just token-checked

Diagnostic value:
- **medium-low**

What to do:
- keep structural checks where useful
- do not mistake them for strong semantic validation

### Simple surface-only endpoint tests

Some tests that only assert:
- page loads
- status code is 200
- response starts with `RIFF`

These are fine as smoke tests, but they should stay in their lane.

Why this is risky:
- lots of shallow endpoint tests can make a subsystem look "well tested" while real branch behavior is still unexercised

Diagnostic value:
- **low**, but still useful in small numbers

---

## 2. False Security from Partial Coverage

These areas have tests, but the tests do not yet cover the real decision space.

### `tests/test_event_feed.py`

This file does useful work. It protects:
- time gating
- cursor pagination
- metadata round-tripping
- some `audio_ready` behavior

But it still leaves meaningful holes:
- malformed `limit`
- duplicate timestamp tie-break edge cases beyond the basic cursor path
- disagreement between cached-audio state and `audio_file` state
- behavior after destructive reset operations

Intended behavior to encode:
- `limit=0` may reasonably return **200 with an empty event list**
- negative or non-integer limits should be treated as **400-class request errors**
- post-reset tests should account for both feed state and destructive cleanup side effects

Be explicit here:
- tests should not merely document today's slicing quirks
- tests should encode the intended contract
- tests should make it obvious whether `limit=0` is an accepted special case or a rejected request
- tests should make it obvious that negative and non-numeric limits are not acceptable input

Risk:
- looks solid at a glance
- still misses subtle feed-state bugs that would matter in the UI

### `tests/test_audio_worker.py`

This is one of the better test files in the repo. It covers:
- batching
- stale lock cleanup
- grace window behavior
- queue ordering
- integration patterns

But it still does not fully exercise:
- warmup path
- room tone asset resolution
- modem noise branch behavior
- missing audio asset behavior
- actor-less event failure policy

Intended behavior to encode:
- if a room-tone asset referenced by the audio plan is missing, the worker should **log a warning and continue rendering without that layer**
- the worker should not hand a missing room-tone problem off to the frontend
- actor-less events are not normal degraded-state input; they should be treated as a **serious invariant violation**

Also be explicit about modem noise:
- modem noise is **not** asset-backed in the same way room tone is
- modem noise is procedural
- the meaningful degraded-state tests are about bad or missing parameters, not missing WAV files
- if modem parameters are absent or partial, tests should verify whether the worker uses defaults or skips the layer, but should not pretend this is the same category of failure as missing room tone on disk

Risk:
- strong queue/locking coverage
- weaker media-integration coverage than the file’s size suggests

### `tests/test_audio_views.py`

This file covers status transitions and worker/web handoff well:
- 200 when audio exists
- 202 when pending
- worker-generated audio served back correctly

But it still misses:
- stale `audio_file` references
- cache vs file precedence in more combinations
- behavior after clearing events/files/cache
- voice resolution branches

Intended behavior to encode:
- if an event row exists but its `audio_file` path points to a deleted file, the endpoint should behave like **audio pending / unavailable** rather than “hard missing”
- `404` should mean **event does not exist**
- `202` should mean **event exists but audio is not currently available**
- if cached mixed audio exists, the **cache should win**
- if cache says audio is available, the endpoint should serve it even if `audio_file` is blank or stale
- if both file and cache are absent, the endpoint should return `202`, not `404`

This needs to be repetitive on purpose:
- `404` is for **missing event rows**
- `202` is for **existing events whose audio is not currently available**
- cached audio is still audio
- therefore cached audio should be served even if file state is stale or absent

Risk:
- strong for the main happy path
- weaker than it looks around cleanup and degraded states

### `tests/test_dialogue_particles.py`

This is broad coverage, but not deep semantic coverage.

Examples of what it still does not protect well:
- controllers being too vague when physics params are available
- readbacks inventing units or parameters
- request/response examples subtly contradicting maneuver logic
- content sounding operationally wrong despite containing the right keywords

Risk:
- strong breadth
- modest depth

---

## 3. Glaring Gaps in Untested Code

The earlier major gaps in `dialogue_server.py`, `controller_physics.py`, `events`-view edge behavior, and `audio_plans.py` have already had targeted test work.

That is good. It should be stated plainly because this document is meant to guide the *current* next step, not preserve outdated urgency.

The remaining glaring gaps are narrower now. They mostly look like this:

### Warmup / startup behavior in the audio worker

The worker now has real startup behavior:
- stale lock cleanup
- warmup render
- file round-trip verification
- readiness signaling

This is exactly the kind of code that can be exercised less in normal tests than people assume.

Risk:
- the worker may look well-covered while startup-specific regressions slip through

### Degraded-state behavior in event/audio serving

The important question is no longer "does the endpoint return audio on the happy path?"

The important questions are:
- what happens when file state and cache state disagree?
- what happens when an event exists but its audio file is gone?
- what happens after destructive reset?

Risk:
- lots of real-user bugs live in these seam conditions

### Semantic correctness of generated dialogue examples

The code that builds examples may be tested structurally while still allowing:
- vague controller instructions
- contradictory readbacks
- operational nonsense that contains the "right" keywords

Risk:
- tests pass
- simulation sounds wrong

This is a real gap even if line coverage looks respectable.

---

## Recommended Priorities

If the goal is **better diagnostics**, not just more green bars, the next passes should focus on the remaining risk seams:

### Priority 1: event/audio degraded states
Reason:
- these are user-visible
- these are subtle
- these are easy to get wrong while happy-path tests still pass

Examples:
- stale `audio_file` + cache hit
- stale `audio_file` + cache miss
- clear/reset after audio generation
- cache/file precedence policy

### Priority 2: worker startup and warmup policy
Reason:
- startup behavior is operationally important
- it is easy to assume it is covered when only steady-state logic is covered

Examples:
- warmup success path
- warmup failure path
- startup after stale locks
- missing room-tone asset during render

### Priority 3: semantic dialogue correctness
Reason:
- the project is not only code-correctness-sensitive, it is also *simulation-quality-sensitive*
- tests that only look for keywords can miss the real failures

Examples:
- controller examples should give concrete parameters when available
- readbacks should not invent units or values
- maneuver-specific examples should not collapse into vague generic traffic-control filler

---

## Recommended Pruning / Reclassification

### Reclassify as environment smoke, not core regression protection
- much of `tests/test_LLM.py`

### Keep, but do not over-credit as semantic coverage
- many keyword/diversity checks in `tests/test_dialogue_particles.py`

### Do not chase
- migrations
- `manage.py`
- `wsgi.py`
- infinite-loop command runners as loops
- dev-only logging endpoints beyond minimal smoke coverage

---

## Summary

The suite is already strong in the project's backbone:
- world model
- route planning
- simulation timing
- actor/event bookkeeping
- audio worker queue behavior

That means the remaining risk is not mostly "we forgot to test core systems."

The remaining risk is:

1. **tests that mostly validate environment rather than application behavior**
2. **tests that make a subsystem look covered while the interesting branches remain weakly exercised**
3. **seam conditions and degraded states where policy matters more than line count**

The next good tests should therefore be:
- explicit about intended behavior
- explicit about degraded-state policy
- willing to check semantics, not just structure

That is how we reduce false confidence instead of merely improving the percentage.
