# Audio Pipeline Hardening - Items 1-5

## Summary

All 5 remaining critical issues from the gotchas list have been hardened. The audio pipeline is now production-ready with robust error handling, timeouts, retries, and collision avoidance.

---

## 1. ✅ Worker Health Check & Restart

**Files Modified:**
- `mysite/universe/services/audio_cache.py`
- `mysite/universe/views/events.py`

**Changes:**
- Added `is_alive_and_healthy()` method to `AudioWorker` that checks if thread is alive and has been active recently (max 5 minutes idle)
- Added `_last_activity` tracking to monitor worker processing
- Updated `_ensure_worker()` to check health and automatically restart dead or stuck workers
- Worker now tracks activity on both success and failure (to detect stuck vs dead)

**Impact:** Worker automatically recovers from crashes or hangs. No manual intervention needed.

---

## 2. ✅ Client-Side Timeout for Waiting Audio

**Files Modified:**
- `mysite/universe/templates/universe/event_scroller_wrapper.html`

**Changes:**
- Added `AUDIO_WAIT_TIMEOUT_MS = 30000` (30 seconds)
- Changed `waitingAudio` Map to store `{event: Event, addedAt: number}` instead of just event
- Updated `fetchEvents()` finally block to check timeout and promote timed-out events
- Timed-out events display without audio (fall back to legacy audio path)

**Impact:** Events no longer wait forever for audio. After 30 seconds, text displays anyway (with legacy audio if available).

---

## 3. ✅ Cache Eviction Retry

**Files Modified:**
- `mysite/universe/templates/universe/event_scroller_wrapper.html`

**Changes:**
- Updated `enqueueEventAudio()` to check audio URL with HEAD request before enqueueing
- If 404 detected, clears `audio_ready` and `audio_url` flags, triggers worker restart, and falls back to legacy audio
- Prevents client from trying to play evicted audio

**Impact:** Client gracefully handles evicted audio and falls back to legacy path instead of failing silently.

---

## 4. ✅ Prefetch Prioritization

**Files Modified:**
- `mysite/universe/views/events.py`

**Changes:**
- Updated `_select_upcoming_events()` to use two-tier horizon:
  - First: Get events within 5 minutes (or 1/6 of full horizon) - prioritizes near-term
  - Second: If room, expand to full horizon for far-future events
- Ensures nearest events are always prefetched first

**Impact:** Near-term events get audio generated first, reducing latency for events about to appear.

---

## 5. ✅ Actor Name Collision Avoidance

**Files Modified:**
- `mysite/universe/receivers.py`
- `mysite/universe/views/events.py`
- `mysite/universe/services/audio_plans.py`

**Changes:**
- Store `actor_id` in `DialogueEventLog.metadata` when event is created
- Updated `_prefetch_audio_for_events()` to prefer `actor_id` from metadata over name lookup
- Updated `build_audio_plan_for_dialogue_event()` to prefer `actor_id` from metadata
- Added warning logs when multiple actors share a name (fallback case)
- Name lookup now explicitly checks for collisions and logs warnings

**Impact:** Events always get the correct actor's voice, even if multiple actors share a name. Future-proof for when we add `actor_id` field to model.

---

## Testing Status

✅ All existing tests pass:
- `test_audio_pipeline_integration.py` - Full end-to-end
- `test_audio_profiles.py` - Actor profile assignment
- `test_audio_worker_errors.py` - Error handling
- `test_audio_cache_eviction.py` - Cache eviction

---

## Core Path Verification

The complete path from event creation to audio playback:

1. ✅ **Event Created** → `DialogueEventLog` saved with `actor_id` in metadata
2. ✅ **Signal Fires** → `post_save` receiver enqueues TTS job
3. ✅ **Worker Processes** → TTS generates audio, stores in cache (or logs error)
4. ✅ **Worker Health** → Auto-restarts if dead/stuck
5. ✅ **Event Feed** → Returns `audio_ready` and `audio_url` from cache
6. ✅ **Client Polls** → Gets events with audio status
7. ✅ **Client Waits** → Holds events in `waitingAudio` until ready or timeout
8. ✅ **Timeout Handling** → After 30s, displays text anyway (legacy audio fallback)
9. ✅ **Audio Playback** → Fetches WAV from `/api/event_audio/<id>/`
10. ✅ **404 Handling** → Detects evicted audio, falls back to legacy path

---

## Production Readiness

**All Critical Issues Resolved:**
- ✅ Worker error handling
- ✅ Worker health monitoring & restart
- ✅ Client timeout for waiting audio
- ✅ Cache eviction retry
- ✅ Prefetch prioritization
- ✅ Actor name collision avoidance
- ✅ Actor profile lookup exception handling
- ✅ Client stale audio state updates

**Remaining (Low Priority):**
- Text normalization edge cases (cosmetic)
- Client error backoff (nice-to-have)
- Audio plan vs TTS disconnect (cosmetic - client uses audio_url, not plan)

---

## Ready for Production Testing

The audio pipeline is now hardened and ready for real-world testing. All critical failure modes are handled gracefully with fallbacks, timeouts, and automatic recovery.

