# Complexity Audit — 2026-03-08

Reviewed as part of the v0.9.0 cleanup (TODO #15). Each hotspot gets a keep/extract/split decision.

---

## `services/location_service.py` — 530 lines, 9 functions

**Decision: Leave as-is.**

Nine focused utility functions for location queries and distance calculations. The longest function, `get_distance_between()`, is ~167 lines of conditional branching for different hierarchy cases (same-parent, orbital, interstellar). The branching is algorithmic and reflects genuine case distinctions — splitting it would scatter related logic without improving clarity. Law-of-cosines math is dense but not confusing in context.

---

## `services/audio_plans.py` — 241 lines, 2 functions

**Decision: Leave as-is.**

One public function `build_audio_plan_for_dialogue_event()` with linear document-construction logic. Low complexity, focused responsibility. The function assembles an audio plan by dispatching on actor type — this reads clearly as-is and doesn't need extraction.

---

## `services/dialogue/particles.py` — 1,593 lines, 17 classes, 75 functions

**Decision: Defer; do not refactor now.**

This is the largest file and the obvious candidate for splitting into subpackages (`pilot_requests.py`, `controller_responses.py`, `satellite_responses.py`). However:

- The current structure is heavily test-covered and working correctly.
- The inheritance hierarchy is shallow and the `TestSemanticInvariants` suite would catch regressions.
- The repetition is mechanical (each particle class implements the same 4-5 methods); it's verbose but not confusing.

**If this file grows past ~2,000 lines or a new particle family is added, split at that point.** The split should be by particle family, keeping the base class in its own file.

---

## `services/route/plan.py` — 345 lines, 9 functions

**Decision: Extract helper for DIRECT_ASCENT branch.**

The `DIRECT_ASCENT` special case (lines 203–245) is a 43-line self-contained block with 3+ levels of nesting. It decides between direct-ascent and Hohmann transfer routing based on physics conditions. This is the one place where the nesting actively hurts readability when debugging.

**Next step:** Extract `_plan_direct_ascent_route()` as a private helper. The function signature, call site, and tests are clear enough to do this without risk. Not blocking for v0.9.0.

---

## `management/commands/audio_worker.py` — 620 lines, 8 methods

**Decision: Leave as-is.**

The main loop is clean. The intricate subsystems (`_render_event()`, `_mix_audio()`) are bounded and well-separated. The warmup, stale-lock cleanup, and batch loop are each isolated enough that they don't interfere. This file is complex by necessity — it orchestrates real-time async audio generation — not by poor design.

---

## Summary

| File | Lines | Decision |
|------|-------|----------|
| `location_service.py` | 530 | Leave as-is |
| `audio_plans.py` | 241 | Leave as-is |
| `dialogue/particles.py` | 1,593 | Defer; split when next family is added |
| `route/plan.py` | 345 | Extract `_plan_direct_ascent_route()` helper (post-v0.9.0) |
| `audio_worker.py` | 620 | Leave as-is |
