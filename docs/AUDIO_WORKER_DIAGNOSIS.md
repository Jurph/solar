# Audio Worker Diagnosis & Fixes

## Problem Identified

Logs show:
- Events being enqueued repeatedly (same event_ids: 2183, 2184, 2185)
- **NO "TTS generate start" logs** - worker is not processing jobs
- Worker thread likely crashing silently on startup

## Root Cause

The `AudioWorker.run()` method calls `get_tts_service()` at the start. If this fails (TTS service unavailable, model loading error, etc.), the exception is uncaught and the worker thread dies silently before processing any jobs.

Since the worker is a daemon thread, it dies without visible error - jobs pile up in the queue but never get processed.

## Fixes Applied

### 1. Worker Error Handling
**File:** `mysite/universe/services/audio_cache.py`

- Wrapped `get_tts_service()` in try/except
- If TTS service fails to load, worker logs error but continues running
- Jobs will fail gracefully with error logs instead of worker crashing
- Added startup logging: "AudioWorker thread starting" and "TTS service loaded successfully"

### 2. Worker Startup Verification
**File:** `mysite/universe/views/events.py`

- Added detailed logging in `_ensure_worker()`:
  - Logs if worker was dead vs unhealthy
  - Verifies thread is alive after start
  - Logs error if thread dies immediately
- Added 0.1s sleep after start to verify thread actually started

### 3. Queue Dedupe Logging
**File:** `mysite/universe/views/events.py`

- Added check before enqueueing to see if job is already queued/in-flight
- Logs DEBUG if skipping duplicate, INFO if actually enqueuing
- Helps diagnose if dedupe is working or if jobs are being re-enqueued unnecessarily

### 4. Worker Status in Event Feed
**File:** `mysite/universe/views/events.py`

- Added `worker`, `queue`, and `cache` status to event_feed debug output
- Shows:
  - Worker exists/alive/healthy
  - Queue size and in-flight count
  - Cache size and capacity
- Accessible via `/api/events/?limit=1` - check `debug.worker`, `debug.queue`, `debug.cache`

## How to Diagnose

1. **Check worker status:**
   ```bash
   curl http://localhost:8000/api/events/?limit=1 | jq '.debug.worker'
   ```
   Should show `{"exists": true, "alive": true, "healthy": true}`

2. **Check queue status:**
   ```bash
   curl http://localhost:8000/api/events/?limit=1 | jq '.debug.queue'
   ```
   If `queued` > 0 but worker is alive, jobs aren't being processed
   If `in_flight` stays high, jobs are stuck

3. **Check logs for:**
   - "AudioWorker thread starting" - worker started
   - "TTS service loaded successfully" - TTS available
   - "TTS generate start" - jobs being processed
   - "AudioWorker failed to load TTS service" - TTS unavailable (root cause)

## Next Steps

If worker still isn't processing:
1. Check if TTS service is available (CUDA, model files, etc.)
2. Check if worker thread is actually starting (look for "AudioWorker thread starting")
3. Check if jobs are stuck in `_inflight` (worker crashed mid-job)
4. Check if queue is being recreated (singleton broken)

## Expected Behavior After Fix

- Worker logs "AudioWorker thread starting" on startup
- Worker logs "TTS service loaded successfully" or error if unavailable
- Each job logs "TTS generate start" when processing begins
- Jobs complete and log "TTS generate done" or error if failed
- Event feed debug shows worker alive and processing jobs

