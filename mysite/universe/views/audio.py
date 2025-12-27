"""
Views for audio generation and streaming.

FUTURE: This module will handle the audio rendering pipeline:

Audio Components:
- Ship-specific static (ambient cockpit noise loop)
- Pilot-specific voice file (TTS voice model selection)
- Ship-specific Quindar tone (comm beep signature)
- Text-to-speech rendering (dialogue → audio)
- Audio mixing and serving

Architecture:
    Event (from DialogueEventLog)
        │
        ├──► text rendering (event_scroller)
        │
        └──► audio rendering (this module)
                ├── ship static (ambient loop based on ship size/type)
                ├── Quindar tone (ship-specific beep pattern)
                ├── TTS (pilot voice model + dialogue text)
                └── mix & serve audio clip

The audio output needs to sync with the text scroller display,
so events may need metadata about expected audio duration.

Planned endpoints:
- get_event_audio: Generate/retrieve audio clip for a specific event
- get_ambient_stream: Stream ship ambient audio (static, beeps)
- get_voice_preview: Preview a pilot's voice model
"""

from __future__ import annotations

import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from mysite.universe.services.audio_synth import (
    ModemNoise,
    SineBeep,
    WhiteNoise,
    render_wav_bytes,
)

logger = logging.getLogger(__name__)


_PRESET_DEFINITIONS = {
    # Quindar tones (NASA comm beeps)
    # Intro: 2525 Hz ~250ms
    "quindar_start": [SineBeep(frequency_hz=2525.0, duration_seconds=0.25, gain=0.9)],
    # Outro: 2475 Hz ~250ms
    "quindar_end": [SineBeep(frequency_hz=2475.0, duration_seconds=0.25, gain=0.9)],
    # Static/radio noise presets (configurable)
    # TODO: Ship-Specific Room Tone Presets
    # - Add presets like "room_tone_small", "room_tone_medium", "room_tone_large"
    # - Each should mix: engine_rumble (low-freq noise, ship-size-dependent) + reverb
    # - Reverb parameters: delay_ms and decay_factor based on cockpit size
    # - These presets will be referenced by build_audio_plan_for_dialogue_event()
    #   when it queries the event's associated Ship model
    "static_light": [
        WhiteNoise(
            duration_seconds=1.0,
            gain=0.3,
            intensity=0.5,
            lowpass_hz=3000.0,
            highpass_hz=200.0,
        )
    ],
    "static_medium": [
        WhiteNoise(
            duration_seconds=1.0,
            gain=0.5,
            intensity=0.7,
            lowpass_hz=4000.0,
            highpass_hz=100.0,
        )
    ],
    "static_heavy": [
        WhiteNoise(
            duration_seconds=1.0,
            gain=0.7,
            intensity=1.0,
            lowpass_hz=5000.0,
            highpass_hz=50.0,
        )
    ],
    # Modem noise: 1200-baud Kermit encoding
    # Example: encode a short message
    "modem_noise_example": [
        ModemNoise(
            text="IF THIS WERE A REAL NAV UPDATE YOU'D BE ABLE TO READ IT BY NOW // 256 bytes of random hex",
            gain=0.8,
            carrier_frequency_hz=1800.0,
            carrier_gain=0.15,
        )
    ],
}


@require_GET
def audio_preset(request, preset: str):
    """
    Return a pre-rendered audio clip for a named preset as WAV.

    This is deliberately Python-defined synthesis: the browser only plays.
    
    For modem_noise presets, accepts optional ?text=... query parameter.
    """
    components = _PRESET_DEFINITIONS.get(preset)
    if components is None:
        return JsonResponse(
            {"status": "error", "message": f"Unknown audio preset: {preset!r}"},
            status=404,
        )
    
    # Allow params from audio plan (passed as query parameters)
    # For modem_noise presets, use text parameter to encode the actual broadcast message
    if preset.startswith("modem_noise") and "text" in request.GET:
        text = request.GET["text"]
        # Get optional params from query string (with defaults)
        gain = float(request.GET.get("gain", 0.8))
        carrier_freq = float(request.GET.get("carrier_frequency_hz", 1800.0))
        carrier_gain = float(request.GET.get("carrier_gain", 0.15))
        
        # Replace any ModemNoise components with text from query
        components = [
            ModemNoise(
                text=text,
                gain=gain,
                carrier_frequency_hz=carrier_freq,
                carrier_gain=carrier_gain,
            ) if isinstance(comp, ModemNoise) else comp
            for comp in components
        ]

    wav_bytes = render_wav_bytes(components)
    resp = HttpResponse(wav_bytes, content_type="audio/wav")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp

