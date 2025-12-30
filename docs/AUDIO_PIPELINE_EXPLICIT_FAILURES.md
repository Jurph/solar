# Audio Pipeline: Explicit Failure Tracking

## Problem Statement

Previous code had many "best-effort" and "silently fail" patterns:
- Operations returned None/False with no indication of *why* they failed
- Fallbacks happened without tracking which path was taken
- Errors were caught and logged but not surfaced to callers
- No empirical evidence of what was actually happening

## Solution: Make All Failures Explicit

Every operation now:
1. **Returns explicit success/failure indicators** (not just None/False)
2. **Tracks statistics** for all failure modes
3. **Logs with context** about why something failed
4. **Surfaces failures** in API responses and debug output

---

## Changes Made

### 1. AudioJobQueue.enqueue() - Explicit Return Values

**Before:** Returned `None`, caller couldn't tell if job was enqueued, duplicate, or queue full.

**After:** Returns `EnqueueResult` enum:
- `SUCCESS` - Job enqueued
- `DUPLICATE` - Already queued or in-flight
- `QUEUE_FULL` - Queue at capacity

**Statistics tracked:**
- `rejects_duplicate` - Count of duplicate rejections
- `rejects_full` - Count of full-queue rejections

**Access:** `queue.get_stats()` returns all metrics

---

### 2. AudioCache.put() - Explicit Return Value

**Before:** Returned `None`, silently did nothing if entry already existed.

**After:** Returns `bool`:
- `True` - Entry stored (new or replaced)
- `False` - Entry already exists (no-op)

**Statistics tracked:**
- `evictions` - Total count of entries evicted

**Access:** `cache.get_stats()` returns cached count, capacity, evictions

---

### 3. AudioWorker - Comprehensive Statistics

**Before:** Worker ran silently, no visibility into what was happening.

**After:** Tracks and exposes:
- `tts_available` - Whether TTS service loaded successfully
- `jobs_processed` - Count of successful TTS generations
- `jobs_failed` - Count of failed TTS generations
- `jobs_skipped_no_tts` - Count of jobs skipped because TTS unavailable
- `last_activity` - Timestamp of last job completion
- `alive` - Thread is running
- `healthy` - Thread is alive and active recently

**Access:** `worker.get_stats()` returns all metrics

**Logging:**
- "AudioWorker thread starting" - Worker started
- "TTS service loaded successfully" - TTS available
- "AudioWorker failed to load TTS service" - TTS unavailable (with exception)
- "Cannot process job X: TTS service not available" - Job skipped
- "TTS generate start event_id=X voice=Y text_len=Z" - Job processing
- "TTS generate done event_id=X duration=Y bytes=Z cached=bool" - Job completed
- "TTS generate failed for event_id=X voice=Y: error" - Job failed (with exception)

---

### 4. _prefetch_audio_for_events() - Detailed Statistics

**Before:** "Best-effort" - silently skipped events, no tracking.

**After:** Returns statistics dict with counts for:
- `enqueued` - Successfully enqueued
- `skipped_cached` - Already in cache
- `skipped_no_text` - Event has no text
- `skipped_no_actor` - Actor not found
- `skipped_no_voice` - Actor has no voice_template (using fallback)
- `rejected_duplicate` - Already queued/in-flight
- `rejected_full` - Queue at capacity

**Logging:**
- "Prefetch skip event_id=X (already cached)" - DEBUG
- "Prefetch skip event_id=X (no text)" - WARNING
- "Prefetch skip event_id=X (actor not found: name='Y', actor_id=Z)" - WARNING
- "Event X actor (id=Y, name='Z', lookup=method) has no audio_profile" - WARNING
- "Prefetch event_id=X using fallback voice='Y' (actor had no voice_template)" - WARNING
- "Prefetch enqueue event_id=X voice=Y actor_lookup=method" - INFO
- "Prefetch skip event_id=X (already queued or in-flight)" - DEBUG
- "Prefetch REJECTED event_id=X (queue full, capacity=Y)" - WARNING
- "Prefetch summary: {stats}" - INFO (if any events processed)

---

### 5. event_audio() Endpoint - Explicit 404 Reasons

**Before:** Returned 404 with generic "Audio not ready" message.

**After:** Returns 404 with detailed error:
```json
{
  "status": "error",
  "message": "Audio not ready for event X",
  "reason": "not_found" | "generating" | "queued" | "possibly_evicted",
  "in_queue": bool,
  "in_flight": bool
}
```

**Reasons:**
- `not_found` - Never generated or not in cache
- `generating` - Currently being processed by worker
- `queued` - Waiting in queue
- `possibly_evicted` - Cache has evictions, may have been evicted

---

### 6. ensure_audio_worker() Endpoint - Detailed Status

**Before:** Returned generic "ok" or "error".

**After:** Returns detailed worker status:
```json
{
  "status": "ok" | "error",
  "worker": {
    "exists": bool,
    "alive": bool,
    "healthy": bool,
    "tts_available": bool,
    "jobs_processed": int,
    "jobs_failed": int,
    "jobs_skipped_no_tts": int,
    "last_activity": float
  }
}
```

---

### 7. event_feed() Debug Output - Comprehensive Status

**Before:** Basic worker/queue/cache counts.

**After:** Full statistics:
```json
{
  "debug": {
    "worker": {
      "exists": bool,
      "alive": bool,
      "healthy": bool,
      "tts_available": bool,
      "jobs_processed": int,
      "jobs_failed": int,
      "jobs_skipped_no_tts": int,
      "last_activity": float
    },
    "queue": {
      "queued": int,
      "in_flight": int,
      "capacity": int,
      "rejects_duplicate": int,
      "rejects_full": int
    },
    "cache": {
      "cached": int,
      "capacity": int,
      "evictions": int
    }
  }
}
```

---

### 8. enqueue_tts_on_log_save() - Explicit Failure Tracking

**Before:** Caught exception and logged warning, no details.

**After:** 
- Calls `_prefetch_audio_for_events()` and gets statistics
- If `enqueued == 0`, logs WARNING with specific reason
- If exception, logs ERROR with full traceback

**Reasons logged:**
- `already_cached` - Audio already generated
- `no_text` - Event has no text
- `no_actor` - Actor not found
- `duplicate` - Already queued
- `queue_full` - Queue at capacity

---

## How to Use

### Check Worker Status
```bash
curl http://localhost:8000/api/ensure_audio_worker/ -X POST | jq '.worker'
```

### Check Event Feed Status
```bash
curl http://localhost:8000/api/events/?limit=1 | jq '.debug'
```

### Check Why Audio Isn't Ready
```bash
curl http://localhost:8000/api/event_audio/123/ | jq '.'
# Returns 404 with reason, in_queue, in_flight
```

### Monitor Logs
Look for:
- "Prefetch summary: {...}" - See breakdown of what happened
- "TTS generate failed" - See why jobs are failing
- "Prefetch REJECTED" - See if queue is full
- "AudioWorker failed to load TTS service" - See if TTS is unavailable

---

## Benefits

1. **Empirical Evidence** - Know exactly what's happening, not guessing
2. **Failure Attribution** - Know *why* something failed, not just that it failed
3. **Performance Monitoring** - Track success rates, queue depth, cache hit rates
4. **Debugging** - Clear error messages point to root cause
5. **No Silent Failures** - Every failure mode is logged and tracked

---

## Migration Notes

- `queue.enqueue()` now returns `EnqueueResult` instead of `None`
- `cache.put()` now returns `bool` instead of `None`
- `_prefetch_audio_for_events()` now returns statistics dict
- All statistics accessible via `.get_stats()` methods
- All endpoints return detailed error information

