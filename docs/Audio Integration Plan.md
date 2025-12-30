# Audio Integration Plan

## Goals
- Deliver event audio alongside text with minimal latency and no disk writes.
- Keep only a small in-memory window (target ~12 events) of ready-to-play audio; evict as we progress.
- Make TTS generation mandatory for broadcast (text+audio travel together), while tolerating generation latency as “in-universe delay.”
- Avoid race conditions and duplicate work when pre-rendering upcoming events.

## Constraints & Decisions
- Storage: in-memory only (no persistent WAV writes); keep a bounded cache of ready clips.
- Ordering: use existing `(timestamp, id)` ordering from `event_feed` to pick the next N events to pre-render.
- Prefetch: allowed, but clips must only play on schedule. Client fetches audio per clip.
- Voice prompts: must exist in `mysite/universe/static/universe/voices/`; missing prompts should fail generation cleanly.
- Model: local chatterbox-turbo; first-load cost is high, so keep service warm.

## Open Questions (to resolve during implementation)
- Cache window size: start with 12 events; calibrate based on measured generation latency and typical event spacing.
- Client delivery: short-lived endpoint + in-memory cache key vs. embedding base64 in `event_feed`. (Leaning endpoint to avoid large payloads.)
- Enqueue trigger: on mission/event creation vs. on poll when upcoming events are known. (Prefer earlier: mission creation/spawn.)

## Proposed Architecture
1) **In-memory audio cache**
   - Bounded (N=12 configurable).
   - Keyed by event id/uuid; stores wav bytes, duration_s, created_at, voice_id.
   - Evicts oldest when over capacity.
2) **Job queue + worker**
   - Small in-process queue of upcoming events (text + voice_id).
   - Worker thread consumes queue, calls TTS, writes to cache.
   - Per-event lock to prevent duplicate generation.
   - On failure, mark audio_failed; no broadcast until fixed.
3) **Prefetch policy**
   - Select next N upcoming events by `(timestamp, id)` (and any newly spawned missions).
   - Enqueue if not already cached/failed and voice prompt exists.
4) **Serving**
   - `event_feed` includes `audio_ready`, `audio_url` (or cache token), `audio_duration_s`.
   - New `get_event_audio(event_id)` endpoint returns WAV from cache; 404 if not ready/evicted.
5) **Lifecycle**
   - When client plays an event, server can optionally drop it immediately or rely on LRU eviction.

## Testing Strategy
### Performance Probes (slow)
- **Chatterbox latency vs length**: measure wall-clock and audio duration for short (~10 words), medium (~30-40), long (~100). Fail only on hang-level time (>60s). Record metrics for planning.
- **Warm cache vs cold**: ensure cache hits are fast and generation is not re-run for identical (text, voice, params).

### Integration (slow)
- **Prefetch window**: create >N events with increasing timestamps; run pre-render; assert only next N are cached, `audio_ready` true, others pending; verify eviction when advancing.
- **Serve endpoint**: when `audio_ready`, `audio_url` yields valid WAV with expected duration range.
- **Concurrency**: enqueue same event twice; ensure single generation; no duplicate cache entries.

### Unit-ish (fast)
- **event_feed payload**: includes `audio_ready`/`audio_url` only when cached; omits otherwise.
- **Voice prompt presence**: generation skips/fails gracefully when prompt missing; marks audio_failed.

## Unknowns to Measure
- Time to generate: ~10 words? ~20 words? ~100 words?
- Typical output duration vs. input length (to help schedule playback).
- Warm vs cold start delta on current hardware.

## Next Steps
- Add performance test (slow) to log timing for short/medium/long texts.
- Implement bounded in-memory cache + worker + endpoint.
- Extend `event_feed` to surface readiness and URL/token.
- Add integration tests for prefetch/serve/eviction and concurrency.

