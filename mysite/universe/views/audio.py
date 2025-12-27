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

from mysite.universe.services.audio_synth import SineBeep, render_wav_bytes

logger = logging.getLogger(__name__)


_PRESET_DEFINITIONS = {
    # Quindar tones (NASA comm beeps)
    # Intro: 2525 Hz ~250ms
    "quindar_start": [SineBeep(frequency_hz=2525.0, duration_seconds=0.25, gain=0.9)],
    # Outro: 2475 Hz ~250ms
    "quindar_end": [SineBeep(frequency_hz=2475.0, duration_seconds=0.25, gain=0.9)],
}


@require_GET
def audio_preset(request, preset: str):
    """
    Return a pre-rendered audio clip for a named preset as WAV.

    This is deliberately Python-defined synthesis: the browser only plays.
    """
    components = _PRESET_DEFINITIONS.get(preset)
    if components is None:
        return JsonResponse(
            {"status": "error", "message": f"Unknown audio preset: {preset!r}"},
            status=404,
        )

    wav_bytes = render_wav_bytes(components)
    resp = HttpResponse(wav_bytes, content_type="audio/wav")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp

