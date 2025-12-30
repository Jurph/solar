# Audio Pipeline Quality Pass - Eliminating "Magical Thinking"

## Problem Identified

The codebase had numerous "best-effort" and "silently fail" patterns:
- Operations returned None/False with no indication of *why* they failed
- Fallbacks happened without tracking which path was taken
- "Hope it works" assumptions throughout
- No empirical evidence of what was actually happening

## Solution: Explicit Failure Tracking

Every operation now:
1. **Returns explicit success/failure indicators** (enums, booleans with meaning)
2. **Tracks statistics** for all failure modes
3. **Logs with context** about why something failed
4. **Surfaces failures** in API responses and debug output

---

## Changes Made

### 1. AudioJobQueue.enqueue() - Explicit Return Values

**Before:**
```python
def enqueue(self, job: AudioJob) -> None:
    # Returns None - caller can't tell if succeeded, duplicate, or full
    if duplicate: return
    if full: return
    self._queue.append(job)
```

**After:**
```python
def enqueue(self, job: AudioJob) -> EnqueueResult:
    # Returns explicit enum: SUCCESS, DUPLICATE, or QUEUE_FULL
    # Tracks statistics: rejects_duplicate, rejects_full
    # Accessible via queue.get_stats()
```

**Impact:** Caller knows exactly why enqueueing failed, can track queue health.

---

### 2. AudioCache.put() - Explicit Return Value

**Before:**
```python
def put(self, entry: AudioEntry) -> None:
    if entry.event_id in self._entries:
        return  # Silent no-op
    # ...
```

**After:**
```python
def put(self, entry: AudioEntry) -> bool:
    # Returns True if stored, False if already exists
    # Tracks evictions count
    # Accessible via cache.get_stats()
```

**Impact:** Caller knows if entry was new or already existed, can track evictions.

---

### 3. AudioWorker - Comprehensive Statistics

**Before:**
- Worker ran silently
- No visibility into TTS availability
- No tracking of success/failure rates

**After:**
- `get_stats()` returns:
  - `tts_available` - Did TTS service load?
  - `jobs_processed` - Success count
  - `jobs_failed` - Failure count
  - `jobs_skipped_no_tts` - Skipped because TTS unavailable
  - `last_activity` - When was last job completed?
  - `alive` / `healthy` - Thread status

**Impact:** Can see exactly what worker is doing, why jobs fail, if TTS is available.

---

### 4. _prefetch_audio_for_events() - Detailed Statistics

**Before:**
```python
def _prefetch_audio_for_events(events):
    """Best-effort prefetch: enqueue events..."""
    # Silently skips events, no tracking
    for ev in events:
        if cached: continue
        if no_text: continue
        # ... enqueue
```

**After:**
```python
def _prefetch_audio_for_events(events):
    """Prefetch audio for events. Explicitly tracks and logs all failure modes."""
    # Returns statistics dict:
    # - enqueued, skipped_cached, skipped_no_text, skipped_no_actor,
    #   skipped_no_voice, rejected_duplicate, rejected_full
    # Logs specific reason for each skip/rejection
```

**Impact:** Know exactly why each event was or wasn't enqueued.

---

### 5. event_audio() Endpoint - Explicit 404 Reasons

**Before:**
```python
if not entry:
    return JsonResponse({"status": "error", "message": "Audio not ready"}, status=404)
```

**After:**
```python
if not entry:
    # Checks queue status, cache evictions
    return JsonResponse({
        "status": "error",
        "message": "Audio not ready for event X",
        "reason": "not_found" | "generating" | "queued" | "possibly_evicted",
        "in_queue": bool,
        "in_flight": bool
    }, status=404)
```

**Impact:** Client knows exactly why audio isn't available.

---

### 6. ensure_audio_worker() - Detailed Status

**Before:**
```python
try:
    _ensure_worker()
    return JsonResponse({"status": "ok"})
except:
    return JsonResponse({"status": "error"}, status=500)
```

**After:**
```python
# Returns full worker stats:
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

**Impact:** Can see worker health, TTS availability, processing rates.

---

### 7. event_feed() Debug Output - Comprehensive Status

**Before:**
```python
'debug': {
    'sim_time': ...,
    'total_events': ...,
}
```

**After:**
```python
'debug': {
    'sim_time': ...,
    'worker': {full stats},
    'queue': {full stats including rejects},
    'cache': {full stats including evictions},
}
```

**Impact:** Single API call shows entire audio pipeline health.

---

### 8. enqueue_tts_on_log_save() - Explicit Failure Tracking

**Before:**
```python
try:
    _prefetch_audio_for_events([instance])
except Exception as e:
    logger.warning("Failed to enqueue TTS prefetch for log %s: %s", instance.id, e)
```

**After:**
```python
stats = _prefetch_audio_for_events([instance])
if stats.get('enqueued', 0) == 0:
    reason = determine_reason_from_stats(stats)
    logger.warning("Event %s TTS prefetch failed: reason=%s stats=%s", 
                  instance.id, reason, stats)
```

**Impact:** Know exactly why event wasn't enqueued, not just "it failed".

---

## Eliminated "Magical Thinking" Patterns

### ❌ Before: Silent Failures
- `queue.enqueue()` returns None - did it work? Who knows!
- `cache.put()` returns None - was it stored? Maybe!
- Worker continues even if TTS unavailable - jobs just fail silently
- Events skipped without tracking why

### ✅ After: Explicit Failures
- `queue.enqueue()` returns `EnqueueResult` enum - know exactly what happened
- `cache.put()` returns `bool` - know if it was stored
- Worker tracks `tts_available` - know if TTS is working
- All skips tracked with specific reasons

### ❌ Before: Wishful Thinking
- "Hope the queue isn't full"
- "Hope the actor exists"
- "Hope the voice file exists"
- "Hope the worker is running"

### ✅ After: Empirical Evidence
- Queue stats show `rejects_full` count
- Actor lookup logs warnings if not found
- Voice fallback logged explicitly
- Worker stats show `alive`, `healthy`, `tts_available`

### ❌ Before: Best-Effort Fallbacks
- Try X, if fails try Y, if fails try Z, if fails... silently give up
- No tracking of which path was taken
- No indication that fallback was used

### ✅ After: Explicit Fallback Tracking
- Each fallback path logged with context
- Statistics track which fallbacks were used
- API responses indicate when fallbacks are active

---

## How to Diagnose Issues Now

### Check Worker Health
```bash
curl http://localhost:8000/api/ensure_audio_worker/ -X POST | jq '.worker'
```
Look for:
- `tts_available: false` → TTS service failed to load
- `jobs_failed > 0` → TTS generation is failing
- `jobs_skipped_no_tts > 0` → Jobs skipped because TTS unavailable
- `healthy: false` → Worker dead or stuck

### Check Queue Health
```bash
curl http://localhost:8000/api/events/?limit=1 | jq '.debug.queue'
```
Look for:
- `rejects_full > 0` → Queue at capacity, events being rejected
- `rejects_duplicate > 0` → Events being re-enqueued (worker not processing)
- `in_flight` stuck high → Jobs stuck in processing

### Check Cache Health
```bash
curl http://localhost:8000/api/events/?limit=1 | jq '.debug.cache'
```
Look for:
- `evictions > 0` → Cache evicting entries (may need larger capacity)
- `cached` vs `capacity` → Cache utilization

### Check Why Audio Isn't Ready
```bash
curl http://localhost:8000/api/event_audio/123/ | jq '.'
```
Returns:
- `reason: "generating"` → Currently being processed
- `reason: "queued"` → Waiting in queue
- `reason: "possibly_evicted"` → May have been evicted
- `in_queue: true` → In queue but not processing (worker issue?)

### Check Prefetch Statistics
Look in logs for:
- `"Prefetch summary: {...}"` → See breakdown of what happened
- `"Prefetch REJECTED event_id=X (queue full)"` → Queue capacity issue
- `"Prefetch skip event_id=X (actor not found)"` → Actor lookup issue
- `"Prefetch event_id=X using fallback voice"` → Voice assignment issue

---

## Benefits

1. **No More Guessing** - Know exactly what's happening
2. **Failure Attribution** - Know *why* something failed
3. **Performance Monitoring** - Track success rates, queue depth, cache hit rates
4. **Debugging** - Clear error messages point to root cause
5. **Production Readiness** - Can monitor and alert on specific failure modes

---

## Test Coverage

All tests updated to verify explicit return values:
- `test_queue_dedup_and_capacity` - Verifies `EnqueueResult` enum
- `test_cache_put_eviction` - Verifies `put()` return value and stats
- `test_prefetch_skips_cached` - Verifies prefetch statistics
- All integration tests pass with new explicit tracking

---

## Migration Notes

- Code using `queue.enqueue()` should check `EnqueueResult` enum
- Code using `cache.put()` should check `bool` return value
- `_prefetch_audio_for_events()` now returns statistics dict
- All `.get_stats()` methods available for monitoring
- All endpoints return detailed error information

