"""
Fallback TTS Service - generates silent audio for testing.

This is a temporary solution while we set up a proper free TTS model.
It allows the system to work end-to-end without audio generation.
"""

import io
import logging
import wave
from typing import Optional

logger = logging.getLogger(__name__)


class FallbackTTSService:
    """Fallback TTS that generates silent audio."""

    def __init__(self, device: Optional[str] = None):
        """Initialize fallback TTS service."""
        self.device = device or "cpu"
        self.sample_rate = 22050
        logger.info(f"FallbackTTSService initialized (device={self.device})")

    def generate(
        self,
        text: str,
        voice_id: str,
        cfg_weight: float = 0.5,
        exaggeration: float = 0.5,
        **kwargs,
    ) -> bytes:
        """Generate silent audio (placeholder)."""
        # Duration based on text length (rough estimate: 150 words per minute)
        word_count = len(text.split())
        duration = max(0.5, word_count / 150 * 60)

        logger.info(f"Generating {duration:.1f}s silence for: {text[:50]}...")
        return self._generate_silence(duration=duration)

    def _generate_silence(self, duration: float = 1.0) -> bytes:
        """Generate silent WAV audio."""
        sample_rate = 22050
        num_samples = int(sample_rate * duration)

        # Create silent audio (zeros)
        audio_data = bytes(num_samples * 2)  # 16-bit = 2 bytes per sample

        # Wrap in WAV format
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)

        return output.getvalue()

