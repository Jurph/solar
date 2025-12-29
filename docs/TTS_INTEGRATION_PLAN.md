# TTS Integration Plan: Chatterbox Integration

**Status**: Planning Phase  
**Target**: v0.9 → v1.0  
**Last Updated**: 2025-01-XX

## Executive Summary

This document outlines the plan for integrating [Chatterbox TTS](https://github.com/resemble-ai/chatterbox) into the Solar simulation. The goal is to add high-quality text-to-speech generation while maintaining flexibility to swap TTS backends in the future.

**Key Decisions:**
- Use `pip install chatterbox-tts` (not cloning the repository)
- Create an abstraction layer (`TTSService`) to decouple from Chatterbox
- Start with Chatterbox-Turbo (350M, English, low latency)
- Store reference audio clips for voice cloning in `static/universe/voices/`
- Generate TTS audio on-demand with caching
- Integrate into existing audio plan pipeline

---

## 1. Architecture Overview

### 1.1 Current Audio Pipeline

```
DialogueEventLog
    ↓
build_audio_plan_for_dialogue_event()
    ↓
Audio Plan (JSON metadata)
    ↓
views/audio.py render endpoints
    ↓
audio_synth.py render_wav_bytes()
    ↓
WAV bytes → Browser
```

### 1.2 Proposed TTS Integration

```
DialogueEventLog
    ↓
build_audio_plan_for_dialogue_event()
    ↓ (adds TTS action if voice_template exists)
Audio Plan (includes TTS action)
    ↓
views/audio.py render endpoints
    ↓
TTSService.generate() [NEW]
    ↓
audio_synth.py render_wav_bytes() (TTS as WavFileClip component)
    ↓
WAV bytes → Browser
```

### 1.3 Abstraction Layer Design

**Goal**: Keep flexibility to swap TTS backends without changing call sites.

```python
# mysite/universe/services/tts_service.py

class TTSService:
    """Abstract TTS service interface."""
    
    @abstractmethod
    def generate(
        self,
        text: str,
        voice_id: str,
        **kwargs
    ) -> bytes:  # Returns WAV bytes
        """Generate TTS audio from text."""
        pass

class ChatterboxTTSService(TTSService):
    """Chatterbox implementation."""
    pass

# Future: class ElevenLabsTTSService(TTSService), etc.
```

**Benefits:**
- Easy to swap implementations
- Can add fallback/multi-provider logic later
- Testable with mocks
- Clear interface contract

---

## 2. Installation & Dependencies

### 2.1 Package Installation

**Decision**: Use `pip install chatterbox-tts` (official package)

**Rationale:**
- Cleaner than cloning the repo
- Easier dependency management
- Official support and updates
- No need to maintain a fork

**Requirements:**
- Python 3.11+ (Chatterbox requirement)
- PyTorch (for model inference)
- CUDA (optional, for GPU acceleration)
- torchaudio (for audio I/O)

**Add to `requirements.txt`:**
```
chatterbox-tts>=0.1.2
torch>=2.0.0
torchaudio>=2.0.0
```

### 2.2 GPU vs CPU

**Strategy**: Support both, prefer GPU if available.

- **GPU (CUDA)**: Faster generation (~200ms latency)
- **CPU**: Fallback for development/small deployments

**Implementation:**
```python
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
model = ChatterboxTurboTTS.from_pretrained(device=device)
```

---

## 3. Voice Management

### 3.1 Voice Storage

**Location**: `mysite/universe/static/universe/voices/`

**Structure:**
```
voices/
├── pilot_male_01.wav      # 10-second reference clip
├── pilot_female_01.wav
├── controller_male_01.wav
├── controller_female_01.wav
└── satellite_robotic.wav  # Optional: robotic voice for navsats
```

**Requirements for reference clips:**
- 10 seconds minimum (Chatterbox recommendation)
- Clear, single speaker
- Minimal background noise
- WAV format, 16-bit PCM, 48kHz (or resampled)

### 3.2 Voice Assignment

**Phase 1 (MVP)**: Two voices
- `pilot_voice_01`: Generic pilot voice (male)
- `controller_voice_01`: Generic controller voice (female)

**Phase 2 (Future)**: Per-actor voices
- Store `voice_template` in `AudioProfile.params["voiceprint"]["voice_template"]`
- Example: `"pilot_male_01"` → loads `voices/pilot_male_01.wav`
- Can assign unique voices per actor later

### 3.3 Voice Parameter Storage

**Already in place**: `AudioProfile.params["voiceprint"]`

```json
{
  "voiceprint": {
    "voice_template": "pilot_male_01",  // Reference clip filename (without .wav)
    "pitch_shift_cents": 0,             // -1200 to +1200 (semitone adjustment)
    "speed_factor": 1.0                 // 0.5 to 2.0 (speech rate)
  }
}
```

**Chatterbox-specific params** (can add later):
- `cfg_weight`: 0.0 to 1.0 (controls adherence to reference voice)
- `exaggeration`: 0.0 to 1.0 (expressiveness)
- `language_id`: "en" (for multilingual model)

---

## 4. Implementation Phases

### Phase 1: "First Water Through the Pipes" (MVP)

**Goal**: Basic TTS working with 2 voices

**Tasks:**

1. **Installation & Setup**
   - [ ] Add `chatterbox-tts` to `requirements.txt`
   - [ ] Create `mysite/universe/services/tts_service.py` with abstraction layer
   - [ ] Implement `ChatterboxTTSService` class
   - [ ] Add voice storage directory: `static/universe/voices/`

2. **Voice Clips**
   - [ ] Source or generate 2 reference clips (pilot, controller)
   - [ ] Place in `static/universe/voices/`
   - [ ] Verify format (WAV, 48kHz, mono)

3. **TTS Service Integration**
   - [ ] Implement `TTSService.generate(text, voice_id)` → WAV bytes
   - [ ] Add caching layer (hash-based cache key: `hash(text + voice_id)`)
   - [ ] Handle GPU/CPU fallback
   - [ ] Add error handling (fallback to silence if TTS fails)

4. **Audio Plan Integration**
   - [ ] Update `build_audio_plan_for_dialogue_event()` to add TTS action
   - [ ] Add TTS action when `voice_template` exists in profile
   - [ ] Format: `{"trigger": "event_during", "action": "tts", "text": "...", "voice_id": "..."}`

5. **Audio Rendering**
   - [ ] Update `views/audio.py` to handle TTS actions
   - [ ] Call `TTSService.generate()` when TTS action present
   - [ ] Add TTS WAV as `WavFileClip` component to mix
   - [ ] Mix with existing components (Quindar, static, room tone)

6. **Testing**
   - [ ] Unit tests for `TTSService`
   - [ ] Integration test: generate TTS for a dialogue event
   - [ ] Verify audio plays in browser
   - [ ] Test fallback when TTS fails

**Success Criteria:**
- ✅ Can generate TTS audio for dialogue events
- ✅ Two distinct voices (pilot vs controller)
- ✅ TTS audio plays in browser alongside text
- ✅ Graceful fallback if TTS unavailable

**Estimated Time**: 2-3 days

---

### Phase 2: Extensibility & Polish

**Goal**: Easy to add more voices, better quality, performance optimization

**Tasks:**

1. **Voice Management**
   - [ ] Admin UI to upload/manage voice clips
   - [ ] Voice preview endpoint (`/api/audio/voice-preview/?voice_id=...`)
   - [ ] Per-actor voice assignment (store in `AudioProfile`)

2. **Caching & Performance**
   - [ ] Persistent cache (file-based or Redis)
   - [ ] Cache invalidation strategy
   - [ ] Background TTS generation (Celery task queue)
   - [ ] Pre-generate TTS for common phrases

3. **Quality Improvements**
   - [ ] Tune `cfg_weight` and `exaggeration` per voice
   - [ ] Add paralinguistic tags support (`[laugh]`, `[chuckle]`, etc.)
   - [ ] Pitch/speed adjustment from `AudioProfile`
   - [ ] Post-processing (normalize, trim silence)

4. **Advanced Features**
   - [ ] Multilingual support (Chatterbox-Multilingual model)
   - [ ] Voice cloning from actor recordings
   - [ ] Emotion/prosody control
   - [ ] SSML-like markup for emphasis

**Estimated Time**: 1-2 weeks (iterative)

---

## 5. Code Structure

### 5.1 New Files

```
mysite/universe/
├── services/
│   ├── tts_service.py          # NEW: TTS abstraction + Chatterbox impl
│   └── audio_plans.py          # MODIFY: Add TTS action generation
├── models/
│   └── audio_profile.py        # MODIFY: Voice params already exist
├── views/
│   └── audio.py                # MODIFY: Handle TTS in render pipeline
└── static/
    └── universe/
        └── voices/             # NEW: Reference audio clips
            ├── pilot_male_01.wav
            └── controller_female_01.wav
```

### 5.2 TTS Service Interface

```python
# mysite/universe/services/tts_service.py

from abc import ABC, abstractmethod
from typing import Optional
import hashlib
import os
from pathlib import Path

import torch
import torchaudio as ta
from chatterbox.tts_turbo import ChatterboxTurboTTS

from django.conf import settings
from django.core.cache import cache


class TTSService(ABC):
    """Abstract TTS service interface for flexibility."""
    
    @abstractmethod
    def generate(
        self,
        text: str,
        voice_id: str,
        **kwargs
    ) -> bytes:
        """
        Generate TTS audio from text.
        
        Args:
            text: Text to synthesize
            voice_id: Voice identifier (e.g., "pilot_male_01")
            **kwargs: Additional TTS parameters (pitch, speed, etc.)
            
        Returns:
            WAV bytes (16-bit PCM, 48kHz, mono)
        """
        pass


class ChatterboxTTSService(TTSService):
    """Chatterbox TTS implementation."""
    
    def __init__(self, device: Optional[str] = None):
        """
        Initialize Chatterbox TTS service.
        
        Args:
            device: "cuda" or "cpu" (auto-detects if None)
        """
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.device = device
        self.model = None  # Lazy load on first use
        self.sample_rate = 48000
    
    def _load_model(self):
        """Lazy-load the model (expensive operation)."""
        if self.model is None:
            self.model = ChatterboxTurboTTS.from_pretrained(device=self.device)
    
    def _get_voice_path(self, voice_id: str) -> Optional[Path]:
        """Find reference audio clip for voice."""
        from django.contrib.staticfiles import finders
        
        # Try static files first
        static_path = finders.find(f"universe/voices/{voice_id}.wav")
        if static_path:
            return Path(static_path)
        
        # Fallback to project root
        project_root = Path(settings.BASE_DIR)
        fallback_path = project_root / "mysite" / "universe" / "static" / "universe" / "voices" / f"{voice_id}.wav"
        if fallback_path.exists():
            return fallback_path
        
        return None
    
    def generate(
        self,
        text: str,
        voice_id: str,
        cfg_weight: float = 0.5,
        exaggeration: float = 0.5,
        **kwargs
    ) -> bytes:
        """
        Generate TTS audio using Chatterbox.
        
        Args:
            text: Text to synthesize
            voice_id: Voice identifier (e.g., "pilot_male_01")
            cfg_weight: Classifier-free guidance weight (0.0-1.0)
            exaggeration: Expressiveness (0.0-1.0)
            **kwargs: Ignored for now (future: pitch, speed)
            
        Returns:
            WAV bytes (16-bit PCM, 48kHz, mono)
        """
        # Check cache first
        cache_key = self._get_cache_key(text, voice_id, cfg_weight, exaggeration)
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Load model if needed
        self._load_model()
        
        # Find voice reference clip
        voice_path = self._get_voice_path(voice_id)
        if not voice_path:
            raise ValueError(f"Voice clip not found: {voice_id}")
        
        # Generate audio
        try:
            wav = self.model.generate(
                text,
                audio_prompt_path=str(voice_path),
                cfg_weight=cfg_weight,
                exaggeration=exaggeration,
            )
            
            # Convert to bytes (16-bit PCM, mono)
            wav_bytes = self._wav_to_bytes(wav, self.sample_rate)
            
            # Cache result (1 hour TTL)
            cache.set(cache_key, wav_bytes, timeout=3600)
            
            return wav_bytes
            
        except Exception as e:
            # Log error and return silence as fallback
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"TTS generation failed: {e}", exc_info=True)
            
            # Return 1 second of silence as fallback
            return self._generate_silence(1.0)
    
    def _get_cache_key(self, text: str, voice_id: str, *args) -> str:
        """Generate cache key from inputs."""
        key_str = f"tts:{hashlib.sha256(f'{text}:{voice_id}:{args}'.encode()).hexdigest()}"
        return key_str
    
    def _wav_to_bytes(self, wav_tensor, sample_rate: int) -> bytes:
        """Convert PyTorch tensor to WAV bytes."""
        import io
        
        # Ensure mono
        if wav_tensor.dim() > 1:
            wav_tensor = wav_tensor.mean(dim=0)
        
        # Convert to numpy and ensure 16-bit PCM
        wav_np = wav_tensor.cpu().numpy()
        wav_np = (wav_np * 32767).astype('int16')
        
        # Write to WAV bytes
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(wav_np.tobytes())
        
        return buffer.getvalue()
    
    def _generate_silence(self, duration_seconds: float) -> bytes:
        """Generate silence as fallback."""
        import wave
        import io
        
        sample_rate = self.sample_rate
        num_samples = int(duration_seconds * sample_rate)
        silence = b'\x00\x00' * num_samples  # 16-bit silence
        
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(silence)
        
        return buffer.getvalue()


# Singleton instance (lazy-loaded)
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """Get singleton TTS service instance."""
    global _tts_service
    if _tts_service is None:
        _tts_service = ChatterboxTTSService()
    return _tts_service
```

### 5.3 Audio Plan Integration

```python
# mysite/universe/services/audio_plans.py (modify)

def build_audio_plan_for_dialogue_event(event: DialogueEventLog) -> list[dict[str, Any]]:
    # ... existing code ...
    
    # Get voice params
    voice_params = profile.get_voice_params()
    voice_template = voice_params.get("voice_template")
    
    # Add TTS action if voice template exists
    if voice_template:
        plan.append({
            "trigger": "event_during",
            "action": "tts",
            "text": event.text,
            "voice_id": voice_template,
            "params": {
                "pitch_shift_cents": voice_params.get("pitch_shift_cents", 0),
                "speed_factor": voice_params.get("speed_factor", 1.0),
            }
        })
    
    return plan
```

### 5.4 Audio Rendering Integration

```python
# mysite/universe/views/audio.py (modify)

def _render_audio_from_plan(plan: list[dict]) -> bytes:
    """Render audio from an audio plan (includes TTS)."""
    from mysite.universe.services.tts_service import get_tts_service
    
    components = []
    tts_service = get_tts_service()
    
    for action in plan:
        if action.get("action") == "tts":
            # Generate TTS audio
            text = action["text"]
            voice_id = action["voice_id"]
            params = action.get("params", {})
            
            try:
                tts_wav_bytes = tts_service.generate(
                    text=text,
                    voice_id=voice_id,
                    **params
                )
                
                # Save to temp file and add as WavFileClip
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                    tmp.write(tts_wav_bytes)
                    tmp_path = tmp.name
                
                components.append(WavFileClip(
                    start_seconds=action.get("start_seconds", 0.0),
                    path=tmp_path,
                    gain=action.get("gain", 1.0)
                ))
            except Exception as e:
                logger.error(f"TTS generation failed: {e}")
                # Continue without TTS (silent fallback)
        
        elif action.get("preset"):
            # Handle existing presets (Quindar, static, etc.)
            # ... existing code ...
    
    # Render final mix
    return render_wav_bytes(components, sample_rate_hz=48000)
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
# tests/test_tts_service.py

def test_chatterbox_service_initialization():
    """Test TTS service can be initialized."""
    service = ChatterboxTTSService(device="cpu")
    assert service.device in ("cuda", "cpu")

def test_voice_path_resolution():
    """Test voice clip path resolution."""
    service = ChatterboxTTSService()
    path = service._get_voice_path("pilot_male_01")
    assert path is not None
    assert path.exists()

def test_tts_generation():
    """Test TTS audio generation (mocked)."""
    # Mock Chatterbox model
    # Verify WAV bytes are returned
    pass

def test_cache_hit():
    """Test TTS caching."""
    # Generate same text twice
    # Verify second call uses cache
    pass

def test_fallback_on_error():
    """Test fallback to silence on TTS failure."""
    # Mock TTS failure
    # Verify silence is returned
    pass
```

### 6.2 Integration Tests

```python
def test_audio_plan_includes_tts():
    """Test audio plan includes TTS action when voice_template exists."""
    # Create actor with voice_template
    # Generate audio plan
    # Verify TTS action is present
    pass

def test_tts_audio_renders():
    """Test TTS audio is rendered in final mix."""
    # Create dialogue event with TTS
    # Render audio
    # Verify WAV contains speech
    pass
```

---

## 7. Performance Considerations

### 7.1 Latency

**Chatterbox-Turbo**: ~200ms per generation (GPU)  
**Chatterbox**: ~500-1000ms per generation (GPU)

**Strategy:**
- Use Turbo model for low latency
- Cache aggressively (same text + voice = cache hit)
- Pre-generate common phrases
- Consider background generation (Celery) for non-critical events

### 7.2 Memory

**Model Size**: ~350MB (Turbo) or ~500MB (Multilingual)

**Strategy:**
- Lazy-load model (only when first TTS request arrives)
- Singleton pattern (one model instance)
- Consider model unloading if idle for >5 minutes

### 7.3 Storage

**Cache Size**: ~50KB per TTS clip (10 seconds @ 48kHz)

**Strategy:**
- Use Django cache (Redis recommended for production)
- Set TTL (1 hour default)
- Limit cache size (LRU eviction)

---

## 8. Future Enhancements

### 8.1 Multi-Provider Support

```python
class TTSServiceFactory:
    """Factory for TTS services."""
    
    @staticmethod
    def create(provider: str = "chatterbox") -> TTSService:
        if provider == "chatterbox":
            return ChatterboxTTSService()
        elif provider == "elevenlabs":
            return ElevenLabsTTSService()
        # ...
```

### 8.2 Voice Cloning

- Allow users to upload their own voice clips
- Generate voice embeddings
- Store in database with actor

### 8.3 Advanced Features

- Paralinguistic tags: `"Hello [laugh] there"`
- Emotion control: `{"emotion": "urgent"}`
- SSML-like markup: `<emphasis>important</emphasis>`
- Multilingual: Switch language per event

---

## 9. Questions & Decisions

### 9.1 Decisions Made

**Voice Clips**: User will source reference audio clips (action item for user)

**GPU**: Available for local users - optimize for GPU, CPU fallback is nice-to-have but don't over-engineer

**Caching**: Use Django cache framework (harmonious with Django ecosystem)

**Background Processing**: TTS generation MUST be async (Celery) - we know scripts/voices well in advance

**Voice Assignment**: 
- Try to load custom voice file per actor (from `AudioProfile.voice_template`)
- Fallback to default voices (2 defaults: `pilot_default.wav`, `controller_default.wav`)
- Architecture supports per-actor voices from day one

### 9.2 Implementation Decisions

- ✅ Use `pip install chatterbox-tts` (not cloning repo)
- ✅ Create abstraction layer for flexibility
- ✅ Start with Chatterbox-Turbo (low latency, GPU-optimized)
- ✅ Store voices in `static/universe/voices/`
- ✅ Cache TTS results aggressively (Django cache)
- ✅ Async generation with Celery (background tasks)
- ✅ Voice fallback: custom → default → silence
- ✅ Graceful fallback on errors

---

## 10. Next Steps

1. **Review this plan** with team
2. **Answer clarifying questions** (Section 9.1)
3. **Source voice clips** (2 reference clips: pilot, controller)
4. **Begin Phase 1 implementation** (Section 4)
5. **Test & iterate** on MVP
6. **Expand to Phase 2** (more voices, polish)

---

## References

- [Chatterbox GitHub](https://github.com/resemble-ai/chatterbox)
- [Chatterbox Documentation](https://resemble-ai.github.io/chatterbox_demopage/)
- [Chatterbox-Turbo Demo](https://huggingface.co/spaces/ResembleAI/chatterbox-turbo-demo)

---

**Document Status**: Implementation in progress  
**Last Updated**: 2025-01-XX

## Implementation Status

### ✅ Phase 1 - Completed

1. **Dependencies Added**
   - ✅ `chatterbox-tts>=0.1.2` added to `requirements.txt`
   - ✅ `torch>=2.0.0`, `torchaudio>=2.0.0` added
   - ✅ `celery>=5.3.0`, `redis>=5.0.0` added (filesystem broker for dev)

2. **TTS Service Created**
   - ✅ `mysite/universe/services/tts_service.py` with abstraction layer
   - ✅ `ChatterboxTTSService` implementation
   - ✅ Voice fallback logic (custom → pilot_default → controller_default)
   - ✅ GPU/CPU auto-detection (optimized for GPU)
   - ✅ Caching with Django cache framework
   - ✅ Graceful error handling (silence fallback)

3. **Async Processing**
   - ✅ Celery configuration in `mysite/celery_app.py`
   - ✅ Celery tasks in `mysite/universe/tasks.py`
   - ✅ Filesystem broker setup (no Redis required for dev)
   - ✅ Async TTS generation triggered on event creation

4. **Audio Plan Integration**
   - ✅ `build_audio_plan_for_dialogue_event()` updated to add TTS actions
   - ✅ Voice inference from actor type (Pilot → pilot_default, Controller → controller_default)
   - ✅ TTS actions include voice_id and params

5. **Infrastructure**
   - ✅ Voice storage directory: `mysite/universe/static/universe/voices/`
   - ✅ Celery data directory: `celery/data/`
   - ✅ Settings updated with Celery configuration

### 🚧 Phase 1 - Remaining

1. **Audio Rendering**
   - [ ] Update `views/audio.py` to handle TTS actions in audio plans
   - [ ] Retrieve cached TTS audio or generate synchronously if not ready
   - [ ] Mix TTS WAV with other audio components (Quindar, static, room tone)

2. **Voice Clips**
   - [ ] User to source: `pilot_default.wav` (10+ seconds)
   - [ ] User to source: `controller_default.wav` (10+ seconds)
   - [ ] Place in `mysite/universe/static/universe/voices/`

3. **Testing**
   - [ ] Unit tests for `TTSService`
   - [ ] Integration tests for TTS generation
   - [ ] Test voice fallback logic
   - [ ] Test async generation

4. **Documentation**
   - [ ] Update README with TTS setup instructions
   - [ ] Document voice clip requirements
   - [ ] Document Celery worker startup

### 📝 Next Steps

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Start Celery worker**: `celery -A mysite worker --loglevel=info`
3. **Add voice clips**: Place `pilot_default.wav` and `controller_default.wav` in voices directory
4. **Test TTS generation**: Create a dialogue event and verify TTS is generated
5. **Complete audio rendering**: Update `views/audio.py` to mix TTS into final audio

---

**Document Status**: Implementation in progress  
**Next Action**: Complete audio rendering integration, then test end-to-end

