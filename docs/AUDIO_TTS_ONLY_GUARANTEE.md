# TTS-Only Guarantee: How We Ensure No Legacy Beep Path

## Core Principle

**When audio is enabled and not muted, text events MUST have TTS audio. No exceptions. No timeouts. No fallbacks.**

If TTS is stuck, we wait and log. The legacy beep-and-text path is a failure mode, not a success case.

---

## Enforcement Points

### 1. Event Append: `appendEvents()`

**Location:** `event_scroller_wrapper.html` lines 447-456

**Logic:**
```javascript
if (audioPlayer.isEnabled() && !audioPlayer.isMuted()) {
    // Audio is enabled - require both audio_url AND audio_ready
    if (!ev.audio_url || !ev.audio_ready) {
        waitingAudio.set(ev.id, {event: ev, addedAt: Date.now()});
        continue; // Do NOT add to eventQueue - wait for TTS
    }
}
eventQueue.push(ev);
```

**Guarantee:** Events without `audio_url` AND `audio_ready=true` are held in `waitingAudio`, never added to `eventQueue`.

---

### 2. Event Processing: `processNextEvent()`

**Location:** `event_scroller_wrapper.html` lines 393-411

**Logic:**
```javascript
if (audioPlayer.isEnabled() && !audioPlayer.isMuted()) {
    if (!event.audio_url || !event.audio_ready) {
        // Put back in waitingAudio, don't process
        waitingAudio.set(event.id, {event: event, addedAt: Date.now()});
        eventQueue.unshift(event); // Put back for retry
        return; // Do NOT display text without TTS
    }
    // Try to enqueue audio
    const audioEnqueued = await enqueueEventAudio(event, useFastMode);
    if (!audioEnqueued) {
        // Audio was evicted or failed - put back in waitingAudio
        waitingAudio.set(event.id, {event: event, addedAt: Date.now()});
        eventQueue.unshift(event);
        return; // Do NOT display text without TTS
    }
}
```

**Guarantee:** 
- Events without audio are immediately returned (not typed)
- If `enqueueEventAudio()` fails (404 eviction), event is moved back to `waitingAudio`
- Text is only typed if audio was successfully enqueued

---

### 3. Audio Enqueueing: `enqueueEventAudio()`

**Location:** `event_scroller_wrapper.html` lines 128-157

**Logic:**
```javascript
async function enqueueEventAudio(event, useFastMode) {
    if (useFastMode) return true; // Historical events - allow
    if (!audioPlayer.isEnabled() || audioPlayer.isMuted()) return true; // Audio off - allow
    if (!event || !event.audio_url || !event.audio_ready) return false; // No audio - fail
    
    // Check if audio exists (HEAD request)
    const resp = await fetch(event.audio_url, { method: "HEAD" });
    if (resp.status === 404) {
        // Audio evicted - clear flags, trigger re-prefetch
        event.audio_ready = false;
        event.audio_url = null;
        await fetch("{% url 'ensure_audio_worker' %}", { method: "POST" });
        return false; // Do NOT display text
    }
    
    audioPlayer.enqueueWavUrl(event.audio_url);
    return true; // Audio enqueued successfully
}
```

**Guarantee:**
- Returns `false` if audio is missing (404 eviction)
- Returns `false` if audio flags are missing
- Returns `true` only if audio was successfully enqueued
- Caller checks return value and does NOT type text if `false`

---

### 4. Waiting Audio Promotion: `fetchEvents()`

**Location:** `event_scroller_wrapper.html` lines 535-564

**Logic:**
```javascript
// Promote waiting events that are now ready (NO TIMEOUT - we wait for TTS)
if (waitingAudio.size > 0) {
    for (const [id, waitingData] of waitingAudio.entries()) {
        const ev = waitingData.event;
        if (ev.audio_ready && ev.audio_url) {
            // Audio is ready - promote to queue
            eventQueue.push(ev);
            readyIds.push(id);
        } else {
            // Still waiting - log periodically to help debug stuck TTS
            if (waitTime > 10000 && waitTime % 5000 < 100) {
                console.warn(`Event ${id} still waiting for audio after ${waitTime}s`);
            }
        }
    }
}
```

**Guarantee:**
- **NO TIMEOUT** - events wait indefinitely for TTS
- Only promotes events with `audio_ready=true` AND `audio_url` present
- Logs warnings every 5 seconds after 10s to help debug stuck TTS
- Events never promoted without audio

---

## Removed Failure Modes

### ❌ Removed: 30-Second Timeout
**Before:** Events promoted to `eventQueue` after 30 seconds even without audio
**After:** Events wait indefinitely for TTS

### ❌ Removed: Legacy Beep Fallback
**Before:** If audio missing, legacy beeps played
**After:** If audio missing, event stays in `waitingAudio`, text never displayed

### ❌ Removed: Silent Failure on 404
**Before:** If audio evicted (404), event processed without audio
**After:** If audio evicted (404), event moved back to `waitingAudio`, text not displayed

### ❌ Removed: Missing audio_url Bypass
**Before:** If `audio_url` missing, event processed anyway
**After:** If `audio_url` missing, event held in `waitingAudio`

---

## Verification Checklist

To verify TTS-only guarantee:

1. **Enable audio** (unmute)
2. **Check `appendEvents()`** - Events without `audio_url` or `audio_ready=false` go to `waitingAudio`
3. **Check `processNextEvent()`** - Events without audio return immediately (no text typed)
4. **Check `enqueueEventAudio()`** - Returns `false` on 404, caller doesn't type text
5. **Check `fetchEvents()`** - No timeout, only promotes events with audio
6. **Check logs** - Warnings every 5s for events waiting >10s

---

## Debugging Stuck TTS

If events are stuck in `waitingAudio`:

1. **Check worker status:**
   ```bash
   curl http://localhost:8000/api/ensure_audio_worker/ -X POST | jq '.worker'
   ```
   Look for: `tts_available: false`, `jobs_failed > 0`

2. **Check queue status:**
   ```bash
   curl http://localhost:8000/api/events/?limit=1 | jq '.debug.queue'
   ```
   Look for: `rejects_full > 0`, `in_flight` stuck

3. **Check event audio status:**
   ```bash
   curl http://localhost:8000/api/event_audio/123/ | jq '.'
   ```
   Returns 404 with reason: `generating`, `queued`, `possibly_evicted`

4. **Check logs:**
   - "Event X still waiting for audio after Ys" - TTS stuck
   - "Prefetch REJECTED event_id=X (queue full)" - Queue capacity issue
   - "TTS generate failed" - TTS generation failing

---

## Summary

**Guarantee:** When audio is enabled and not muted, text events are NEVER displayed without TTS audio.

**Enforcement:**
- `appendEvents()` - Requires `audio_url` AND `audio_ready=true`
- `processNextEvent()` - Checks audio before typing, returns if missing
- `enqueueEventAudio()` - Returns `false` on failure, caller doesn't type
- `fetchEvents()` - No timeout, only promotes ready events

**No Fallbacks:** Legacy beep path completely removed when audio enabled.

**No Timeouts:** Events wait indefinitely for TTS.

**Debugging:** Logs every 5s for events waiting >10s.

