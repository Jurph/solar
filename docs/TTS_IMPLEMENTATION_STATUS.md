# TTS Implementation Status

**Date**: 2025-01-XX  
**Status**: Phase 1 - Core Infrastructure Complete, Audio Rendering Pending

## ✅ Completed

### 1. Core TTS Service
- **File**: `mysite/universe/services/tts_service.py`
- **Features**:
  - Abstract `TTSService` interface for flexibility
  - `ChatterboxTTSService` implementation
  - GPU/CPU auto-detection (optimized for GPU)
  - Voice fallback: custom → pilot_default → controller_default
  - Django cache integration
  - Graceful error handling (silence fallback)

### 2. Async Processing
- **File**: `mysite/universe/tasks.py`
- **Features**:
  - `generate_tts_async` Celery task
  - `pregenerate_tts_for_events` batch task
  - Automatic retry with exponential backoff
  - Event-specific caching

### 3. Celery Configuration
- **File**: `mysite/celery_app.py`
- **Settings**: `mysite/settings.py` (Celery config added)
- **Features**:
  - Filesystem broker (no Redis required for dev)
  - Django cache as result backend
  - Auto-discovery of tasks

### 4. Audio Plan Integration
- **File**: `mysite/universe/services/audio_plans.py`
- **Changes**:
  - TTS actions added to audio plans
  - Voice inference from actor type
  - Fallback to defaults if no custom voice

### 5. Event Receiver Integration
- **File**: `mysite/universe/receivers.py`
- **Changes**:
  - Triggers async TTS generation when events are saved
  - Non-blocking (errors don't prevent event saving)

### 6. Infrastructure
- Voice storage: `mysite/universe/static/universe/voices/`
- Celery data: `celery/data/`
- Dependencies: `requirements.txt` updated

## 🚧 Remaining Work

### 1. Audio Rendering (Critical)
**File**: `mysite/universe/views/audio.py`

**Task**: Update audio rendering to handle TTS actions from audio plans.

**Current State**: Audio plans include TTS actions, but rendering doesn't process them yet.

**Required Changes**:
```python
# In views/audio.py, need to:
# 1. Detect TTS actions in audio plan
# 2. Retrieve cached TTS audio (or generate synchronously if not ready)
# 3. Add TTS as WavFileClip component to mix
# 4. Mix with other components (Quindar, static, room tone)
```

### 2. Voice Clips (User Action Item)
**Location**: `mysite/universe/static/universe/voices/`

**Required Files**:
- `pilot_default.wav` (10+ seconds, single speaker, clear audio, 48kHz mono)
- `controller_default.wav` (10+ seconds, single speaker, clear audio, 48kHz mono)

**Optional** (for custom voices):
- `pilot_male_01.wav`, `pilot_female_01.wav`, etc.
- `controller_male_01.wav`, `controller_female_01.wav`, etc.

### 3. Testing
- [ ] Unit tests for `TTSService`
- [ ] Integration tests for async generation
- [ ] Test voice fallback logic
- [ ] Test error handling

### 4. Documentation
- [ ] Quick start guide for TTS setup
- [ ] Voice clip requirements and sourcing
- [ ] Celery worker startup instructions

## 📋 Next Steps

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Celery Worker** (in separate terminal)
   ```bash
   celery -A mysite worker --loglevel=info
   ```

3. **Add Voice Clips**
   - Place `pilot_default.wav` and `controller_default.wav` in `mysite/universe/static/universe/voices/`

4. **Complete Audio Rendering**
   - Update `views/audio.py` to handle TTS actions
   - Test end-to-end: event → TTS generation → audio playback

5. **Test**
   - Create a dialogue event
   - Verify TTS is generated asynchronously
   - Verify audio plays in browser

## 🔍 How It Works

### Flow Diagram

```
DialogueEvent Created
    ↓
save_dialogue_event_to_db() receiver
    ↓
DialogueEventLog saved to DB
    ↓
generate_tts_async.delay() triggered
    ↓
Celery worker picks up task
    ↓
ChatterboxTTSService.generate()
    ↓
TTS audio cached (Django cache)
    ↓
[Later, when event plays]
    ↓
build_audio_plan_for_dialogue_event()
    ↓
Audio plan includes TTS action
    ↓
views/audio.py renders audio
    ↓
Retrieves cached TTS or generates synchronously
    ↓
Mixes TTS with Quindar/static/room tone
    ↓
WAV bytes → Browser
```

### Voice Fallback Logic

1. Try custom voice: `{voice_template}.wav` (from `AudioProfile`)
2. If not found, infer from actor type:
   - `Pilot` → `pilot_default.wav`
   - `Controller` → `controller_default.wav`
3. If still not found, try generic defaults
4. If all fail, raise `ValueError` (caught, returns silence)

## 🐛 Known Issues

None yet - implementation is fresh.

## 📝 Notes

- Celery uses filesystem broker for development (no Redis needed)
- TTS generation is cached aggressively (1 hour TTL)
- Async generation means TTS is ready before events play
- Synchronous fallback if async generation hasn't completed yet

