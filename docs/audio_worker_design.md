# Audio Worker Design & Architecture

## Overview

The audio pre-generation worker is a background process that generates TTS audio for dialogue events ahead of time, ensuring smooth playback without on-demand generation delays.

---

## Startup & Warmup

### Health Check on Startup
Design decision: the worker runs a warmup test before accepting real work.

Warmup test:
1. Generates test audio: `"Audio worker ready"` (satellite voice)
2. Writes to database-backed storage via Django's storage backend
3. Reads back to verify file I/O
4. Cleans up the test file
5. Reports `[READY]` only after successful warmup

Benefits:
- Fails fast if the TTS model is missing or broken
- Validates file I/O before processing real events
- Confirms database connectivity
- Warms up the TTS model for the first real event
- Gives a clear signal when the worker is truly ready

Trade-off: longer startup time, but better confidence.

---

## Core Design Principles

### Separation Of Concerns
Design decision: the web server is a view/observer of the simulation, not the simulation engine.

- Web server job: display simulation state, serve pre-generated content
- Web server non-job: generate audio, run simulation logic
- UI controls are mainly for testing and operator use
- This keeps the web server fast and easier to reason about

### Audio Is Non-Negotiable
Design decision: events wait for audio instead of silently degrading to text-only output.

- Events should not appear without audio as a fallback mode
- Audio completeness matters more than strict timestamp purity
- If needed, timestamps can drift slightly later rather than skipping audio

### Only The Worker Knows Failure
Design decision: external observers should not infer TTS failure from timeouts alone.

- The worker is slow enough that "still processing" and "failed" can look identical from outside
- Only the worker should decide when generation failed
- Avoid timeout-based failover logic in the web layer

---

## Technical Design Decisions

### Actor-Based Batching
Why: TTS generation is more efficient when the same voice model stays warm.

Problem:
- Dialogue alternates speakers frequently
- Naive processing would cause constant voice-model swapping

Solution:
- Process one actor's queued lines in a batch before moving on
- Prioritize the actor whose first pending event is due soonest

Trade-off:
- Generation order is not perfectly timestamp-ordered
- Playback order still follows event timestamps

### Timing Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| Lookahead window | 1 hour | Initial heuristic; tune with production usage |
| Grace period | 60 seconds | Catches events at or just before current sim time on startup |
| Cleanup threshold | 10 minutes past | Prevents disk sprawl from old rendered audio |
| Batch size | 3 events | Balances responsiveness and batching efficiency |
| Sleep interval | 5 seconds | Balances responsiveness and CPU usage |

### Grace Period Explanation
The 60-second grace period exists to handle worker cold starts.

- Simulation may already be running when the worker starts
- Events at exactly current simulation time would otherwise be missed
- The grace window catches just-due events during restarts and startup transitions

---

## Failure Modes & Recovery

### Worker Crash Recovery
Expected behavior: worker clears stale locks on startup and resumes processing.

Implementation status: implemented.

Current behavior:
1. Finds events with `audio_generating=True` and no `audio_file`
2. Clears the lock by setting `audio_generating=False`
3. Logs how many stale locks were cleared

This runs before the main processing loop.

### Historical Event Handling
Design decision: very old events can be dropped.

Rationale:
- The worker focuses on upcoming events
- Very old events outside the grace window are not useful to recover for playback

Possible future enhancement:
- Explicitly flush very old pending events on startup to avoid queue buildup

### TTS Generation Failure
Current behavior:
- The lock is released
- The event remains without audio
- The worker moves on

This keeps the system simple and allows the event to be retried later if it is still in scope.

Avoid:
- Retry storms
- Exponential backoff complexity
- Permanent failure states unless real operational pressure demands them

---

## Business Rules

### Rule 1: Every Event Must Have An Actor
Severity: critical if violated.

Expected behavior:
- Worker skips actor-less events loudly
- Web layer should fail explicitly if asked to build an audio plan for one
- This should be treated as an upstream event-generation bug

Implementation status:
- Worker-side handling exists
- Web behavior is still only partially enforced

### Rule 2: Audio Files Are Ephemeral
- Generated ahead of time
- Played once
- Cleaned up after playback
- Not intended as a long-term archive

### Rule 3: Worker Throughput Assumption
Current architecture assumes generation stays ahead of playback most of the time.

If that assumption breaks, treat it as an operational issue to solve with measurement rather than speculative complexity.

---

## Monitoring & Troubleshooting

### Primary Health Metric
"Are events processing?"

The key observable difference is between:
- events entering the audio pipeline
- events becoming playable with audio

If that gap grows steadily, something is wrong.

### Red Flags
If events stop scrolling while many past-due events accumulate, treat it as critical.

Likely causes:
- Worker crashed or stalled
- Stale locks blocked progress
- TTS service hung
- Storage backend failed

### Useful Metrics
1. Pipeline delta: events created minus events with audio
2. Events processed per minute
3. Stale lock count
4. TTS generation failure rate

### Health Indicators
- Worker is processing batches
- Events continue scrolling in the UI
- Few or no events remain stuck with `audio_generating=True`
- Audio files exist for events within lookahead

### Common Issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Events stop scrolling | Worker crashed | Restart worker |
| Events appear without audio | Worker not running | Start worker |
| Worker crashes on startup | Missing TTS model files | Check model paths |
| Disk space grows unbounded | Cleanup not running | Check cleanup path and SimulationState |
| "Event without actor" errors | Upstream event-generation bug | Fix event creation logic |

---

## Logging Philosophy

### INFO
- Event entered the pipeline
- Event rendered successfully
- Batch processed
- Stale locks cleared

### DEBUG
- Detailed timestamps
- File paths
- TTS durations
- Actor and voice resolution
- Query filtering details

### WARNING
- Recoverable stale lock cleanup
- Non-critical duration read failures
- Missing SimulationState while waiting

### ERROR
- Actor-less event
- TTS generation failure
- Storage backend failure
- Unexpected rendering exceptions

---

## Open Questions / TODOs

1. Enforce the "event must have actor" invariant more explicitly in the web path
2. Decide whether the worker should flush very old events on startup
3. Tune constants such as lookahead and batch size based on real usage
4. Decide whether a dedicated health endpoint is still worth adding

---

## Related Documentation

- Test coverage: `tests/test_audio_worker.py` (23 tests at last manual count)
- Implementation: `mysite/universe/management/commands/audio_worker.py`
- Integration points: `mysite/universe/views/events.py`

---

**Last Updated:** March 14, 2026
**Version:** 1.1
