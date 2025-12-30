# Audio Pipeline Gotchas & Hardening Checklist

## Critical Path: Event → Audio → Browser

### 1. **Worker Error Handling: Silent Failures**
**Location:** `mysite/universe/services/audio_cache.py:94-124`

**Problem:** The `AudioWorker.run()` method has no `except` block. If `svc.generate()` throws:
- Exception is swallowed
- Job is marked complete via `finally`
- No error logged
- Event never gets `audio_ready=True`
- Client waits forever for audio that will never come

**Fix:** Add try/except around TTS generation, log errors, and optionally retry or mark job as failed.

---

### 2. **Client-Side Stale Audio State Check**
**Location:** `mysite/universe/templates/universe/event_scroller_wrapper.html:496-506`

**Problem:** In `fetchEvents()`, the code checks `waitingAudio` entries for `ev.audio_ready`, but these are **stale event objects** from previous fetches. The new `data.events` from the current fetch might have updated `audio_ready` flags, but we're checking old objects.

**Fix:** When processing `data.events`, update or remove entries in `waitingAudio` based on the fresh `audio_ready` flags from the server.

---

### 3. **Double TTS Enqueue (Redundant but Harmless)**
**Location:** `mysite/universe/receivers.py:115-121` and `128-139`

**Problem:** Two receivers both call `_prefetch_audio_for_events`:
- `save_dialogue_event_to_db` (signal receiver) - line 119
- `enqueue_tts_on_log_save` (post_save receiver) - line 137

**Impact:** Same event enqueued twice. Queue dedupe prevents duplicates, but it's wasteful and confusing.

**Fix:** Remove one of the enqueue calls (prefer keeping the `post_save` receiver as it's more reliable).

---

### 4. **Actor Profile Lookup: RelatedObjectDoesNotExist Not Handled**
**Location:** `mysite/universe/views/events.py:92`

**Problem:** `getattr(actor, "audio_profile", None)` will **raise** `RelatedObjectDoesNotExist` if no profile exists, not return `None`. The `getattr` default only works if the attribute doesn't exist, not if the related object is missing.

**Fix:** Use try/except or `hasattr` + explicit check:
```python
try:
    profile = actor.audio_profile
    vp = profile.get_voice_params() or {}
    voice_id = vp.get("voice_template")
except Actor.audio_profile.RelatedObjectDoesNotExist:
    voice_id = None
```

---

### 5. **Fallback Voice "pilot_default" May Not Exist**
**Location:** `mysite/universe/views/events.py:95-97`

**Problem:** If no voice_template is found, code falls back to `"pilot_default"`, but:
- This voice file may not exist in `audio/voices/generated/`
- TTS service will fail
- Worker has no error handling (see #1)
- Event never gets audio

**Fix:** 
- Check if voice file exists before enqueueing
- Or handle missing voice gracefully in TTS service
- Or use a guaranteed-to-exist default voice

---

### 6. **Cache Eviction: No Client Notification**
**Location:** `mysite/universe/services/audio_cache.py:36-44`

**Problem:** When cache evicts an old entry, the client still has `audio_url` pointing to it. When client requests `/api/event_audio/<id>/`, it gets 404, but:
- Client doesn't know to re-request audio
- Event stays in `waitingAudio` forever
- Text never displays

**Fix:** 
- Client should handle 404 and retry prefetch
- Or server should re-enqueue evicted events
- Or cache should be large enough to never evict active events

---

### 7. **Worker Thread Lifecycle: No Restart on Crash**
**Location:** `mysite/universe/services/audio_cache.py:82-128`

**Problem:** If the worker thread crashes or is killed:
- No automatic restart
- Jobs pile up in queue
- Events never get audio
- Client waits forever

**Fix:** 
- Add health check/restart mechanism
- Or make worker more robust (catch all exceptions, log, continue)
- Or expose worker status via API

---

### 8. **Text Normalization: Edge Cases**
**Location:** `mysite/universe/views/events.py:114-125` and `audio_plans.py:177-191`

**Problem:** `_sentence_case()` may not handle:
- Mixed case: "MARS CONTROL" → "Mars control" (good) but "NASA" → "Nasa" (bad)
- Numbers: "A1" → "A1" (no change, but should be "A1"?)
- Special chars: "MARS!" → "Mars!" (good) but "MARS." → "Mars." (good)

**Impact:** Minor - TTS will still work, but may sound odd.

**Fix:** More robust sentence casing (preserve acronyms, handle numbers better).

---

### 9. **Prefetch Horizon: May Skip Near-Term Events**
**Location:** `mysite/universe/views/events.py:105-111`

**Problem:** `_select_upcoming_events` selects events within horizon, but:
- If many events exist, it may skip some
- Ordering by `timestamp, id` may not prioritize soonest events
- Cache capacity may be exhausted by far-future events

**Fix:** Prioritize events closer to `sim_time` first, or use a smarter selection algorithm.

---

### 10. **Client Audio Gating: Race Condition**
**Location:** `mysite/universe/templates/universe/event_scroller_wrapper.html:369-376`

**Problem:** In `processNextEvent()`, if `event.audio_url` exists but `!event.audio_ready`, event is put back at front of queue. But:
- If audio never becomes ready (worker failed, see #1), event loops forever
- No timeout or max retries
- Blocks all subsequent events

**Fix:** Add timeout/max retries, or fall back to legacy audio after timeout.

---

### 11. **Actor Name Collision: Wrong Voice Assigned**
**Location:** `mysite/universe/views/events.py:86-91` and `audio_plans.py:54-68`

**Problem:** Actor lookup uses `.filter(name=ev.actor_name).order_by("-id").first()`. If multiple actors have the same name:
- Gets the most recent one (highest ID)
- May assign wrong voice to event
- Audio won't match the intended actor

**Fix:** 
- Use unique actor identifiers (UUID, or actor_id in event metadata)
- Or ensure actor names are unique
- Or store actor_id in DialogueEventLog

---

### 12. **Audio Plan vs. Actual TTS: Disconnect**
**Location:** `mysite/universe/services/audio_plans.py:145-158` vs `mysite/universe/views/events.py:75-102`

**Problem:** 
- `build_audio_plan_for_dialogue_event` adds TTS action to plan (metadata)
- But actual TTS generation happens in `_prefetch_audio_for_events` (separate)
- If plan says "use voice X" but prefetch uses "voice Y", mismatch occurs
- Client may try to play plan-based audio that doesn't exist

**Impact:** Client uses `audio_url` (server-generated WAV), not plan, so this is mostly cosmetic. But confusing.

**Fix:** Ensure plan and prefetch use same voice lookup logic, or remove TTS from plan (it's redundant).

---

### 13. **Worker Startup: Not Guaranteed on First Event**
**Location:** `mysite/universe/views/events.py:56-61` and `mysite/universe/apps.py`

**Problem:** `_ensure_worker()` is called in:
- `event_feed` view (when client polls)
- `_prefetch_audio_for_events` (when event is created)

But if first event is created before any client polls:
- Worker may not be started
- Event enqueued but never processed
- Audio never generated

**Fix:** Ensure worker starts on app ready (unless management command), or make `_ensure_worker()` more robust.

---

### 14. **Cache Capacity vs. Prefetch Horizon Mismatch**
**Location:** `mysite/universe/views/events.py:32-34` and `105-111`

**Problem:** 
- Cache capacity: 24 events (default)
- Prefetch horizon: 30 minutes (1800 seconds)
- If events arrive faster than 24 events per 30 minutes, cache will evict
- But prefetch tries to generate audio for all events in horizon

**Impact:** Cache thrashing, evicted events lose audio.

**Fix:** 
- Increase cache capacity
- Or reduce prefetch horizon
- Or prioritize near-term events in prefetch

---

### 15. **Client Polling: No Backoff on Errors**
**Location:** `mysite/universe/templates/universe/event_scroller_wrapper.html:442-508`

**Problem:** If `/api/events/` returns 500 or network error:
- Client logs error but continues polling at same rate
- No exponential backoff
- Spams server with requests

**Fix:** Add exponential backoff on errors, or circuit breaker pattern.

---

## Testing Gaps

### Missing Tests:
1. **Worker error handling** - What happens when TTS service throws?
2. **Cache eviction** - Does client handle 404 gracefully?
3. **Worker crash/restart** - Can system recover?
4. **Actor name collision** - Does wrong voice get assigned?
5. **No voice file** - Does system degrade gracefully?
6. **Client timeout** - Does event eventually display even if audio never ready?
7. **Prefetch horizon overflow** - Does cache handle too many events?
8. **Double enqueue** - Does dedupe work correctly?

---

## Recommended Fixes (Priority Order)

1. **HIGH:** Add error handling to AudioWorker (#1)
2. **HIGH:** Fix client-side stale audio check (#2)
3. **MEDIUM:** Fix actor profile lookup exception handling (#4)
4. **MEDIUM:** Add worker health check/restart (#7)
5. **MEDIUM:** Handle cache eviction gracefully (#6)
6. **LOW:** Remove double enqueue (#3)
7. **LOW:** Improve text normalization (#8)
8. **LOW:** Add client error backoff (#15)

