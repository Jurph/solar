# Audio Worker Design & Architecture

## Overview

The audio pre-generation worker is a background process that generates TTS audio for dialogue events ahead of time, ensuring smooth playback without on-demand generation delays.

---

## Startup & Warmup

### Health Check on Startup
**Design Decision:** Worker runs a warmup test before accepting real work.

**Warmup Test:**
1. Generates test audio: "Audio worker ready" (satellite voice)
2. Writes to database via Django's storage backend
3. Reads back to verify file I/O
4. Cleans up test event and file
5. Reports `[READY]` only after successful warmup

**Benefits:**
- Fails fast if TTS model missing/broken
- Validates file I/O before processing real events
- Confirms database connectivity
- Warms up TTS model for faster first real event
- Clear signal when worker is truly ready

**Trade-off:** Longer startup time (~5-10 seconds), but worth it for confidence.

---

## Core Design Principles

### Separation of Concerns: Observer Pattern
**Design Decision:** The web server ("event server") is fundamentally a **view/observer** of the simulation.

- Web server's job: Display simulation state, serve pre-generated content
- Web server's non-job: Generate audio, run simulation logic
- UI controls are primarily for testing; production simulation will be self-generating
- This separation keeps the web server fast, stateless, and easily scalable

### Audio is Non-Negotiable
**Design Decision:** Events ALWAYS wait for audio. No silent failover.

- We wait for audio before displaying events
- We do NOT emit text-only events as a fallback
- Previous attempts at "silent failover" led to broken states where code gives up on audio
- **Audio completeness > strict timing**
- If needed, we can "fudge" timestamps to make events appear later rather than skip audio

### Only the Worker Knows Failure
**Design Decision:** Never assume/infer TTS failure from external evidence.

- The worker is slow and simulation is fiddly
- External observers cannot distinguish "still processing" from "failed"
- Only the worker itself should report TTS generation failure
- Don't implement timeout-based failover logic in web server

---

## Technical Design Decisions

### Actor-Based Batching
**Why:** TTS model efficiency through voice model warmth.

**Problem:** Our dialogue model alternates between speakers (ABA pattern), which would cause constant voice model swapping.

**Solution:** Process all of one actor's lines in a batch before moving to the next actor. This keeps the voice model "warm" and improves TTS generation speed.

**Trade-off:** Events may not be strictly processed in timestamp order, but the soonest actor's events are always processed first.

### Timing Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| **Lookahead Window** | 1 hour | Arbitrary initial guess; can be tuned based on mission length |
| **Grace Period** | 60 seconds | Allows worker to catch events at/near current time on startup (added during bugfix) |
| **Cleanup Threshold** | 10 minutes past | Regular cleanup prevents disk sprawl from played audio files |
| **Batch Size** | 3 events | Small enough for responsive processing, large enough for efficiency |
| **Sleep Interval** | 5 seconds | Balances responsiveness with CPU usage |

**Note:** These values are tunable and should be adjusted based on production experience.

### Grace Period Explanation
The 60-second grace period was added to handle worker cold starts. When the worker starts:
- Simulation may already be running at time T
- Events at exactly time T would be excluded by query `timestamp >= T`
- Grace period `timestamp >= T - 60` catches events that just became "due"
- Prevents events from being orphaned during worker restarts

---

## Failure Modes & Recovery

### Worker Crash Recovery
**Expected Behavior:** Worker should clear stale locks on startup and resume processing.

**Implementation Status:** ✅ **IMPLEMENTED**

**Behavior:** On startup, worker automatically:
1. Finds events with `audio_generating=True` AND `audio_file` is empty
2. Clears the lock (`audio_generating=False`)
3. Logs: "Cleared {N} stale locks from previous crash"

This runs before the main processing loop begins.

### Historical Event Handling
**Design Decision:** Events created before worker started can be dropped.

**Rationale:** Worker focuses on upcoming events. Very old events (beyond grace period) are skipped.

**Optional Enhancement:** Worker could flush/cleanup very old pending events on startup to prevent queue buildup.

### TTS Generation Failure
**Current Behavior:** Lock is released, event remains without audio, worker moves on.

**This is correct.** The event will be retried on next batch if still within lookahead window.

**Don't implement:** Retry logic, exponential backoff, permanent failure marking. These add complexity and violate "only worker knows failure" principle.

---

## Business Rules (Invariants)

### Rule 1: Every Event Must Have An Actor
**Severity:** CRITICAL BUG if violated

**Behavior:** If an event without an actor reaches the audio generation system:
- Worker should skip it with loud warning
- Web server should fail explicitly if asked to generate audio plan
- This indicates a serious bug in event creation logic

**Implementation Status:** ⚠️ Partially enforced (worker skips, web server behavior unclear)

### Rule 2: Audio Files Are Ephemeral
Events are temporary; audio files are even more temporary.
- Generated ahead of time
- Played once
- Cleaned up 10 minutes after playback
- No long-term archival

### Rule 3: Worker Never Falls Behind (By Design)
Current architecture assumes worker generates faster than events arrive.

**If this assumption breaks:** Deal with throughput issues when they occur, not preemptively.

**Mitigation:** Actor-based batching already prioritizes soonest events ("alligator closest to the boat").

---

## Monitoring & Troubleshooting

### Primary Health Metric
**"Are events processing?"** - Observable difference between:
- Events passed into audio pipeline
- Audio clips played / events scrolled past

**This is the canary.** If this delta is growing, something is broken.

### Red Flags
**Events no longer scrolling + dozens of events in the past = CRITICAL**

This indicates:
- Worker crashed or stuck
- Stale locks preventing processing
- TTS service hung
- Storage backend failure

**Action:** Check worker logs, restart worker, verify TTS service health.

### Key Metrics (Future)
1. **Pipeline delta** - (Events created) - (Events with audio)
2. **Events processed per minute** - Throughput
3. **Stale lock count** - Potential crashes
4. **TTS generation failure rate** - Voice/text issues

### Health Indicators
- Worker is processing batches (check logs for "Processed N events")
- Events continue scrolling in UI
- No events stuck with `audio_generating=True` for >1 minute
- Audio files exist for events within lookahead window

### Common Issues
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Events stop scrolling | Worker crashed | Restart worker (clears stale locks on startup) |
| Events appear without audio | Worker not running | Start worker process |
| Worker crashes on startup | Missing TTS model files | Check model paths in config |
| Disk space grows unbounded | Cleanup not running | Check SimulationState exists |
| "Event without actor" errors | Bug in event creation | Fix upstream event generation logic |

---

## Logging Philosophy

**INFO Level:** Lifecycle events
- "Event {id} created"
- "Event {id} passed to audio pipeline"
- "Event {id} audio rendered successfully"
- "Processed {N} events, cleaned {N} files"
- "Cleared {N} stale locks on startup"

**DEBUG Level:** Implementation details
- Individual event timestamps
- File paths
- TTS duration measurements
- Actor/voice ID resolution
- Query results and filtering

**WARNING Level:** Recoverable issues
- Stale lock cleared during processing
- Failed to read TTS duration (non-critical)
- SimulationState missing (worker waits)

**ERROR Level:** Critical failures requiring attention
- **Event without actor detected** (serious bug)
- TTS generation failed
- Storage backend failed
- Unexpected errors during rendering

---

## Open Questions / TODOs

1. 🚧 **Implement stale lock cleanup on worker startup**
2. 🚧 **Enforce "event must have actor" invariant in web server**
3. 🤔 **Should worker flush very old events on startup?**
4. 🤔 **Tune constants (lookahead, batch size) based on production usage**
5. 🤔 **Add basic health check endpoint for monitoring?**

---

## Related Documentation
- Test coverage: `tests/test_audio_worker.py` (13 tests)
- Implementation: `mysite/universe/management/commands/audio_worker.py`
- Integration points: `mysite/universe/views/events.py` (event_feed, event_audio)

---

**Last Updated:** Dec 31, 2025  
**Version:** 1.0 (initial architecture capture)
