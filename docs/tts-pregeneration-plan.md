# TTS Pre-Generation Worker Plan

## Problem Statement

The TTS engine (Chatterbox) is slow (~10-30 seconds per clip). Currently, when events arrive in the browser, we trigger TTS generation on-demand, which causes:
1. Multiple concurrent TTS requests (5-6 at once)
2. GPU contention and slower overall throughput
3. Events waiting in `waitingAudio` queue until TTS completes

## Proposed Solution

A single-threaded background worker that pre-generates TTS audio ahead of time, one clip at a time.

## Algorithm

```
while True:
    1. Get all DialogueEventLog entries where:
       - timestamp is within the next 1 hour (sim_time + 3600)
       - audio_file is NULL (not yet rendered)
       
    2. Group events by actor
    
    3. Pick the actor whose first uncached event is soonest
    
    4. For that actor, render up to 3 events:
       - Generate TTS WAV
       - Mix with room tone + quindars (full audio pipeline)
       - Save to disk
       - Update event.audio_file and event.audio_rendered_at
       
    5. Sleep 5 seconds, then repeat
```

## Model Changes

Add to `DialogueEventLog`:

```python
audio_file = models.FilePathField(
    path='media/rendered_audio/',
    null=True, 
    blank=True,
    help_text="Path to pre-rendered mixed audio file"
)
audio_rendered_at = models.DateTimeField(
    null=True, 
    blank=True,
    help_text="When the audio was pre-rendered"
)
```

## File Structure

```
media/
  rendered_audio/
    event_2482.wav
    event_2483.wav
    ...
```

## Modified Endpoints

### `event_audio` endpoint

```python
def event_audio(request, event_id):
    event = get_object_or_404(DialogueEventLog, pk=event_id)
    
    # If pre-rendered, serve immediately
    if event.audio_file and os.path.exists(event.audio_file):
        with open(event.audio_file, 'rb') as f:
            return HttpResponse(f.read(), content_type='audio/wav')
    
    # Otherwise, generate on-demand (existing logic)
    # But acquire a lock to prevent concurrent TTS
    ...
```

### `event_feed` endpoint

```python
# In serialize_event:
audio_ready = bool(event.audio_file and os.path.exists(event.audio_file))
```

## Concurrency Control

Add a threading lock to prevent multiple simultaneous TTS generations:

```python
# In tts_service.py or a new audio_worker.py
import threading

_tts_lock = threading.Lock()

def generate_with_lock(text, voice_id):
    with _tts_lock:
        return tts_service.generate(text, voice_id)
```

## Worker Implementation Options

### Option A: Django Management Command (Recommended for now)

```python
# mysite/universe/management/commands/audio_worker.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            process_next_batch()
            time.sleep(5)
```

Run with: `python manage.py audio_worker`

### Option B: Django AppConfig ready() 

Start a background thread when Django boots. Simpler but harder to control.

### Option C: Celery

Overkill for a single worker, but would be the "proper" async solution.

## Rollback Plan

If this breaks things:
```
git checkout v0.1-audio-working
```

## Implementation Order

1. Add model fields + migration
2. Create `media/rendered_audio/` directory
3. Implement worker as management command
4. Modify `event_audio` to check for pre-rendered files
5. Modify `event_feed` to report `audio_ready=True` for pre-rendered events
6. Test with a few events
7. Add lock to prevent concurrent TTS

## Success Criteria

- [ ] TTS generates one clip at a time
- [ ] Events with pre-rendered audio play immediately
- [ ] No regression in audio quality or mixing
- [ ] Worker can be stopped/started independently

