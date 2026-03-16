"""
TTS FastAPI Server for Chatterbox-TTS.

Runs as a standalone service in Docker, providing a REST API for audio generation.
Handles model loading, caching, and concurrent requests.
"""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import TTS service from Django project
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/mysite')

# Try to import from the project structure
try:
    from universe.services.tts_service import ChatterboxTTSService, get_tts_health
    logger.info("Using Chatterbox TTS service")
except ImportError:
    logger.warning("Chatterbox TTS not available, trying fallback...")
    try:
        from universe.services.simple_tts_service import FallbackTTSService
        logger.info("Using Fallback TTS service (silent audio)")
        ChatterboxTTSService = FallbackTTSService

        def get_tts_health():
            return {"status": "ok", "device": "fallback"}
    except ImportError:
        logger.error("Could not import any TTS service, using mock")

        class ChatterboxTTSService:
            def __init__(self, device="cpu"):
                self.device = device

            def generate(self, text, voice_id, cfg_weight, exaggeration):
                return b"mock audio data"

        def get_tts_health():
            return {"status": "ok", "device": "mock"}

# Initialize FastAPI app
app = FastAPI(
    title="Solar TTS Service",
    description="Chatterbox-TTS audio generation API",
    version="1.0.0"
)

# Global TTS service instance
tts_service: Optional[ChatterboxTTSService] = None


@app.on_event("startup")
async def startup_event():
    """Initialize TTS service on startup."""
    global tts_service
    try:
        device = os.getenv("TTS_DEVICE", "cuda")
        logger.info(f"Initializing TTS service with device={device}")
        tts_service = ChatterboxTTSService(device=device)
        logger.info("TTS service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize TTS service: {e}")
        logger.info("Falling back to error tone TTS service")
        # Use error tone service instead of crashing
        class ErrorToneTTSService:
            def __init__(self, device="cpu"):
                self.device = device
            def generate(self, text, voice_id, cfg_weight, exaggeration):
                # Generate error tone beeps
                import io, wave, math
                sample_rate = 22050
                duration = max(0.5, len(text.split()) / 150 * 60)

                beep_freq = 400  # Hz
                beep_duration = 0.15
                pause_duration = 0.1
                amplitude = 0.15

                audio_data = []

                # 3 error beeps
                for beep_num in range(3):
                    for i in range(int(sample_rate * beep_duration)):
                        sample = amplitude * math.sin(2 * math.pi * beep_freq * i / sample_rate)
                        sample_int = int(sample * 32767)
                        audio_data.append(sample_int & 0xFFFF)

                    if beep_num < 2:
                        for i in range(int(sample_rate * pause_duration)):
                            audio_data.append(0)

                remaining_samples = int(sample_rate * (duration - (3 * beep_duration + 2 * pause_duration)))
                audio_data.extend([0] * remaining_samples)

                audio_bytes_data = b''.join(
                    (sample & 0xFF).to_bytes(1, 'little') + ((sample >> 8) & 0xFF).to_bytes(1, 'little')
                    for sample in audio_data
                )

                output = io.BytesIO()
                with wave.open(output, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_bytes_data)
                return output.getvalue()
        tts_service = ErrorToneTTSService(device=device)


class TTSRequest(BaseModel):
    """Request model for TTS generation."""
    text: str
    voice_id: str = "pilot_default"
    cfg_weight: float = 0.5
    exaggeration: float = 0.5


class TTSResponse(BaseModel):
    """Response model for TTS generation."""
    success: bool
    message: str
    audio_bytes: Optional[bytes] = None


@app.post("/v1/audio")
async def generate_audio(request: TTSRequest) -> dict:
    """
    Generate audio from text using Chatterbox-TTS.

    Args:
        request: TTSRequest with text, voice_id, and TTS parameters

    Returns:
        dict with audio bytes and metadata
    """
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    try:
        logger.info(f"Generating audio: voice={request.voice_id}, text_len={len(request.text)}")

        audio_bytes = tts_service.generate(
            text=request.text,
            voice_id=request.voice_id,
            cfg_weight=request.cfg_weight,
            exaggeration=request.exaggeration
        )

        logger.info(f"Audio generated successfully: {len(audio_bytes)} bytes")

        # Encode audio bytes as base64 for JSON serialization
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {
            "success": True,
            "message": "Audio generated successfully",
            "audio_bytes": audio_b64,
            "size_bytes": len(audio_bytes)
        }
    except Exception as e:
        # Fallback: generate error tone beeps on any error
        logger.warning(f"TTS generation failed ({type(e).__name__}): {e}")
        logger.info("Generating fallback error tone audio")

        try:
            import io, wave, math

            sample_rate = 22050
            duration = max(0.5, len(request.text.split()) / 150 * 60)

            # Generate error tone: 3 beeps (400Hz) with pauses
            # Pattern: beep-pause-beep-pause-beep-silence
            beep_freq = 400  # Hz (recognizable error tone)
            beep_duration = 0.15  # seconds
            pause_duration = 0.1  # seconds
            amplitude = 0.15  # Comfortable volume (0.0-1.0, where 1.0 is max)

            audio_data = []

            # Generate 3 error beeps
            for beep_num in range(3):
                # Beep
                for i in range(int(sample_rate * beep_duration)):
                    sample = amplitude * math.sin(2 * math.pi * beep_freq * i / sample_rate)
                    # Convert to 16-bit signed integer
                    sample_int = int(sample * 32767)
                    audio_data.append(sample_int & 0xFFFF)

                # Pause (except after last beep)
                if beep_num < 2:
                    for i in range(int(sample_rate * pause_duration)):
                        audio_data.append(0)

            # Fill remaining time with silence
            remaining_samples = int(sample_rate * (duration - (3 * beep_duration + 2 * pause_duration)))
            audio_data.extend([0] * remaining_samples)

            # Convert to bytes (16-bit little-endian)
            audio_bytes_data = b''.join(
                (sample & 0xFF).to_bytes(1, 'little') + ((sample >> 8) & 0xFF).to_bytes(1, 'little')
                for sample in audio_data
            )

            # Wrap in WAV format
            output = io.BytesIO()
            with wave.open(output, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes_data)

            audio_bytes = output.getvalue()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

            return {
                "success": True,
                "message": f"Fallback error tone (TTS unavailable: {str(e)[:50]})",
                "audio_bytes": audio_b64,
                "size_bytes": len(audio_bytes)
            }
        except Exception as fallback_error:
            logger.error(f"Even fallback failed: {fallback_error}")
            raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        dict with service health status
    """
    if not tts_service:
        return {"status": "initializing", "message": "TTS service starting up"}
    
    health = get_tts_health()
    return {
        "status": "ok" if health["status"] == "ok" else "degraded",
        "tts_health": health
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint with service info."""
    return {
        "service": "Solar TTS Service",
        "version": "1.0.0",
        "endpoints": {
            "generate": "POST /v1/audio",
            "health": "GET /health"
        }
    }


if __name__ == "__main__":
    port = int(os.getenv("TTS_PORT", "8001"))
    host = os.getenv("TTS_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)

