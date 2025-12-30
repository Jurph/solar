"""
TTS Service abstraction and Chatterbox implementation.

Provides a flexible interface for text-to-speech generation that can be
swapped between different TTS backends (Chatterbox, ElevenLabs, etc.).
"""

from __future__ import annotations

import hashlib
import io
import os
import logging
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import torch
import torchaudio as ta

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


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
            voice_id: Voice identifier (e.g., "pilot_male_01" or "pilot_default")
            **kwargs: Additional TTS parameters (pitch, speed, cfg_weight, etc.)
            
        Returns:
            WAV bytes (16-bit PCM, 48kHz, mono)
            
        Raises:
            ValueError: If voice_id not found
            RuntimeError: If TTS generation fails
        """
        pass


class ChatterboxTTSService(TTSService):
    """Chatterbox TTS implementation (Turbo model for low latency)."""
    
    def __init__(self, device: Optional[str] = None):
        """
        Initialize Chatterbox TTS service.
        
        Args:
            device: "cuda" or "cpu" (auto-detects GPU if None)
        """
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.device = device
        self.model = None  # Lazy load on first use
        self.sample_rate = 48000
        
        logger.info(f"ChatterboxTTSService initialized with device={device}")
    
    def _load_model(self):
        """Lazy-load the model (expensive operation, ~350MB)."""
        if self.model is None:
            try:
                from chatterbox.tts_turbo import ChatterboxTurboTTS

                # Prefer local path if provided (no network)
                local_path = os.getenv("CHATTERBOX_LOCAL_PATH")
                if not local_path:
                    # default local path under project root
                    local_path = str(Path(settings.BASE_DIR) / "models" / "chatterbox-turbo")

                if Path(local_path).exists():
                    self.model = ChatterboxTurboTTS.from_local(local_path, device=self.device)
                    logger.info(f"Chatterbox-Turbo model loaded from local path: {local_path}")
                else:
                    self.model = ChatterboxTurboTTS.from_pretrained(device=self.device)
                    logger.info("Chatterbox-Turbo model loaded (remote download)")
            except ImportError:
                logger.error("chatterbox-tts not installed. Run: pip install chatterbox-tts")
                raise
            except Exception as e:
                logger.error(f"Failed to load Chatterbox model: {e}", exc_info=True)
                raise
    
    def _get_voice_path(self, voice_id: str) -> Optional[Path]:
        """
        Find reference audio clip for voice with fallback logic.
        
        Tries in order:
        1. Custom voice: `universe/voices/{voice_id}.wav`
        2. Default pilot: `universe/voices/pilot_default.wav`
        3. Default controller: `universe/voices/controller_default.wav`
        
        Args:
            voice_id: Voice identifier (e.g., "pilot_male_01", "pilot_default")
            
        Returns:
            Path to voice clip, or None if not found
        """
        # Try custom voice first
        custom_path = self._find_voice_file(voice_id)
        if custom_path:
            return custom_path
        
        # Fallback to defaults based on voice_id prefix
        if voice_id.startswith("pilot") or "pilot" in voice_id.lower():
            default_path = self._find_voice_file("pilot_default")
            if default_path:
                logger.info(f"Using default pilot voice for {voice_id}")
                return default_path
        
        if voice_id.startswith("controller") or "controller" in voice_id.lower():
            default_path = self._find_voice_file("controller_default")
            if default_path:
                logger.info(f"Using default controller voice for {voice_id}")
                return default_path
        
        # Last resort: try generic defaults
        for default_name in ["pilot_default", "controller_default"]:
            default_path = self._find_voice_file(default_name)
            if default_path:
                logger.warning(f"Using generic default voice '{default_name}' for {voice_id}")
                return default_path
        
        return None
    
    def _find_voice_file(self, voice_id: str) -> Optional[Path]:
        """
        Find a specific voice file.
        
        Checks only: mysite/universe/static/universe/voices/{voice_id}.wav
        
        Voice ID format: exact basename, e.g., "pilot-M-002_canonical_all"
        """
        project_root = Path(settings.BASE_DIR)

        static_path = project_root / "mysite" / "universe" / "static" / "universe" / "voices" / f"{voice_id}.wav"
        if static_path.exists():
            return static_path

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
        Generate TTS audio using Chatterbox-Turbo.
        
        Args:
            text: Text to synthesize
            voice_id: Voice identifier (with fallback to defaults)
            cfg_weight: Classifier-free guidance weight (0.0-1.0, default 0.5)
            exaggeration: Expressiveness (0.0-1.0, default 0.5)
            **kwargs: Ignored for now (future: pitch_shift_cents, speed_factor)
            
        Returns:
            WAV bytes (16-bit PCM, 48kHz, mono)
            
        Raises:
            ValueError: If voice_id not found (after all fallbacks)
            RuntimeError: If TTS generation fails
        """
        # Check cache first
        cache_key = self._get_cache_key(text, voice_id, cfg_weight, exaggeration)
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"TTS cache hit for voice={voice_id}, text_length={len(text)}")
            return cached
        
        # Load model if needed
        self._load_model()
        
        # Find voice reference clip (with fallback)
        voice_path = self._get_voice_path(voice_id)
        if not voice_path:
            raise ValueError(
                f"Voice clip not found: {voice_id} "
                "(tried custom voice and defaults: pilot_default, controller_default)"
            )
        
        logger.info(f"Generating TTS: voice={voice_id}, text_length={len(text)}, device={self.device}")
        
        # Generate audio
        try:
            wav = self.model.generate(
                text,
                audio_prompt_path=str(voice_path),
                cfg_weight=cfg_weight,
                exaggeration=exaggeration,
            )
            
            # Convert to bytes (16-bit PCM, mono) - use model's actual sample rate
            wav_bytes = self._wav_to_bytes(wav, self.model.sr)
            
            # Cache result (1 hour TTL)
            cache.set(cache_key, wav_bytes, timeout=3600)
            logger.debug(f"TTS generated and cached: {len(wav_bytes)} bytes")
            
            return wav_bytes
            
        except Exception as e:
            logger.error(f"TTS generation failed: {e}", exc_info=True)
            # Return silence as fallback (1 second)
            return self._generate_silence(1.0)
    
    def _get_cache_key(self, text: str, voice_id: str, *args) -> str:
        """Generate cache key from inputs."""
        key_str = f"{text}:{voice_id}:{args}"
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()
        return f"tts:{key_hash}"
    
    def _wav_to_bytes(self, wav_tensor, sample_rate: int) -> bytes:
        """Convert PyTorch tensor to WAV bytes (16-bit PCM, mono, 48kHz)."""
        # Ensure mono
        if wav_tensor.dim() > 1:
            wav_tensor = wav_tensor.mean(dim=0)
        
        # Resample if needed (Chatterbox may output different sample rate)
        if sample_rate != self.sample_rate:
            wav_tensor = ta.transforms.Resample(sample_rate, self.sample_rate)(wav_tensor)
        
        # Convert to numpy and ensure 16-bit PCM
        wav_np = wav_tensor.cpu().numpy()
        # Clamp to [-1, 1] range
        wav_np = wav_np.clip(-1.0, 1.0)
        wav_np = (wav_np * 32767).astype('int16')
        
        # Write to WAV bytes
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(wav_np.tobytes())
        
        return buffer.getvalue()
    
    def _generate_silence(self, duration_seconds: float) -> bytes:
        """Generate silence as fallback (16-bit PCM, mono, 48kHz)."""
        num_samples = int(duration_seconds * self.sample_rate)
        silence = b'\x00\x00' * num_samples  # 16-bit silence
        
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(silence)
        
        return buffer.getvalue()


# Singleton instance (lazy-loaded)
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """
    Get singleton TTS service instance.
    
    Returns:
        TTSService instance (Chatterbox implementation)
    """
    global _tts_service
    if _tts_service is None:
        _tts_service = ChatterboxTTSService()
    return _tts_service


def warm_tts_service(voice_id: str = "pilot_default", text: str = "check"):
    """
    Warm the TTS model once to avoid first-hit latency.
    Best-effort; logs but does not raise.
    """
    try:
        svc = get_tts_service()
        svc.generate(text=text, voice_id=voice_id)
    except Exception as e:
        logger.warning("TTS warmup failed: %s", e)

