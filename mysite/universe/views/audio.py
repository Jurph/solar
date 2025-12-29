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

import json
import logging
import os
from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.contrib.staticfiles import finders

from mysite.universe.services.audio_synth import (
    Echo,
    LoopedAudioFragment,
    ModemNoise,
    SineBeep,
    WavFileClip,
    WhiteNoise,
    render_wav_bytes,
)

logger = logging.getLogger(__name__)

AUDIO_LAB_TTS_SAMPLE_STATIC_PATH = "universe/audio/sample_speech_clip.wav"


def _find_audio_lab_tts_sample_path() -> str | None:
    """
    Locate the sample voice clip for Audio Lab "TTS" mode.

    Prefer staticfiles finders (works in dev without collectstatic, and in prod
    when the staticfiles storage is configured), with a fallback to the old
    local `staticfiles/` path for convenience.
    """
    found = finders.find(AUDIO_LAB_TTS_SAMPLE_STATIC_PATH)
    if found:
        return found

    legacy = os.path.join(
        settings.BASE_DIR,
        "staticfiles",
        "audio",
        "sample speech clip.wav",
    )
    if os.path.exists(legacy):
        return legacy

    return None


def _save_last_playback(wav_bytes: bytes) -> None:
    """
    Persist the last rendered audio to a single file for manual inspection.
    Overwrites the same file each time; best-effort only.
    """
    try:
        out_path = Path(settings.BASE_DIR) / "last-playback.wav"
        out_path.write_bytes(wav_bytes)
    except Exception:
        logger.warning("Failed to save last-playback.wav", exc_info=True)

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
    # Placeholder room tone so event_during plans don't 404.
    # This is intentionally simple (filtered noise); later we can replace it with
    # ship-size-dependent rumble + reverb.
    "room_tone_placeholder": [
        WhiteNoise(
            duration_seconds=0.6,
            gain=0.08,
            intensity=0.5,
            lowpass_hz=1200.0,
            highpass_hz=40.0,
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
        mark_freq = float(request.GET.get("mark_frequency_hz", 1200.0))
        space_freq = float(request.GET.get("space_frequency_hz", 2200.0))
        baud_rate = int(request.GET.get("baud_rate", 1200))
        wow_rate = float(request.GET.get("wow_rate_hz", 0.0))
        wow_depth = float(request.GET.get("wow_depth_hz", 0.0))
        
        # Replace any ModemNoise components with text from query
        components = [
            ModemNoise(
                text=text,
                gain=gain,
                baud_rate=baud_rate,
                mark_frequency_hz=mark_freq,
                space_frequency_hz=space_freq,
                carrier_frequency_hz=carrier_freq,
                carrier_gain=carrier_gain,
                wow_rate_hz=wow_rate,
                wow_depth_hz=wow_depth,
            ) if isinstance(comp, ModemNoise) else comp
            for comp in components
        ]

    wav_bytes = render_wav_bytes(components)
    _save_last_playback(wav_bytes)
    resp = HttpResponse(wav_bytes, content_type="audio/wav")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp


def _list_available_voice_templates() -> list[str]:
    """
    Enumerate available voice prompt files (WAV) for chatterbox.
    Looks only in static/universe/voices.
    Returns basenames without extension, sorted.
    """
    import os
    from glob import glob

    candidates = set()

    static_dir = os.path.join(settings.BASE_DIR, "mysite", "universe", "static", "universe", "voices")
    for path in glob(os.path.join(static_dir, "*.wav")):
        candidates.add(os.path.splitext(os.path.basename(path))[0])

    return sorted(candidates)


@require_GET
def audio_lab(request):
    """
    Standalone dev tool UI for audio experimentation (no coupling to event feed).
    """
    voices = _list_available_voice_templates()
    return render(request, "universe/audio_lab.html", {"voices": voices})


@csrf_exempt
@require_http_methods(["POST"])
def audio_lab_render(request):
    """
    Render a mixed WAV for the audio lab based on user-selected settings.

    Contract (v0): POST JSON body.
    This endpoint is a dev tool; it is intentionally simple and does not persist anything.
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

    mode = (payload.get("mode") or "modem").lower()
    text = payload.get("text") or "Sphinx of black quartz, judge my vow."
    include_quindar = bool(payload.get("include_quindar", True))
    include_static = bool(payload.get("include_static", True))
    quindar_gain = float(payload.get("quindar_gain", 0.45))
    engine_bed_gain = float(payload.get("engine_bed_gain", 1.0))

    if mode == "tts":
        tts_gain = float(payload.get("tts_gain", 2.0))
        voice_id = (payload.get("voice_id") or "").strip()
        generated_tmp_path = None

        # Resolve voice clip: if voice_id provided, generate via chatterbox; otherwise use sample clip
        tts_clip_path = None
        try:
            if voice_id:
                from mysite.universe.services.tts_service import get_tts_service
                import tempfile

                tts_service = get_tts_service()
                logger.info("audio_lab TTS generation: voice_id=%s text_len=%d", voice_id, len(text))
                wav_bytes = tts_service.generate(text=text, voice_id=voice_id)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                tmp.write(wav_bytes)
                tmp.flush()
                generated_tmp_path = tmp.name
                tts_clip_path = generated_tmp_path
            else:
                tts_clip_path = _find_audio_lab_tts_sample_path()
        except Exception as e:
            logger.warning(f"TTS generation failed in audio_lab_render: {e}")
            tts_clip_path = _find_audio_lab_tts_sample_path()

        if not tts_clip_path:
            return JsonResponse(
                {
                    "status": "error",
                    "message": (
                        "TTS clip not found or generation failed. "
                        "Provide a valid voice or sample clip."
                    ),
                },
                status=501,
            )

        # Build a mix that treats the WAV as a "voice" clip, then overlays optional
        voice_start = (0.25 + 0.05) if include_quindar else 0.0

        components = []
        if include_quindar:
            components.append(SineBeep(start_seconds=0.0, duration_seconds=0.25, frequency_hz=2525.0, gain=quindar_gain))

        components.append(WavFileClip(start_seconds=voice_start, path=tts_clip_path, gain=tts_gain))

        # Compute voice clip duration for looping the 10 soundscape components.
        voice_duration = 0.5  # fallback
        try:
            import wave

            with wave.open(tts_clip_path, "rb") as wf:
                sr = wf.getframerate() or 0
                frames = wf.getnframes() or 0
            if sr > 0 and frames > 0:
                voice_duration = frames / float(sr)
        except Exception:
            # If header read fails, keep a small non-zero bed duration.
            pass

        # Add 10 looped audio fragments with robust fallback filenames.
        # These loop for the duration of the voice clip.
        from django.contrib.staticfiles import finders

        descriptive_names = [
            "controls-and-quindars",
            "modems-and-teletypes",
            "burbly-sonar",
            "slower-burbles",
            "engine-hum",
            "engine-thrum",
            "engine-rumble",
            "deep-engine-rumble",
            "infra-engine-rumble",
            "staticky-crickets",
        ]

        for i in range(1, 11):
            component_gain = float(payload.get(f"component_{i}_gain", 0.0)) * engine_bed_gain
            if component_gain <= 0.0:
                continue  # Skip components with zero gain

            name = descriptive_names[i - 1]
            candidates = [
                f"universe/audio/audio-{i:02d}-variant-a.wav",
                f"universe/audio/audio-{i:02d}-{name}.wav",
                f"universe/audio/audio-{i:02d}.wav",
            ]

            fragment_path = None
            for candidate in candidates:
                found = finders.find(candidate)
                if found:
                    fragment_path = found
                    break

            if not fragment_path:
                # Fallback to root audio/ folder (source assets location)
                import os
                root_candidates = [
                    os.path.join(settings.BASE_DIR, "audio", f"audio-{i:02d}-variant-a.wav"),
                    os.path.join(settings.BASE_DIR, "audio", f"audio-{i:02d}-{name}.wav"),
                    os.path.join(settings.BASE_DIR, "audio", f"audio-{i:02d}.wav"),
                ]
                for rc in root_candidates:
                    if os.path.exists(rc):
                        fragment_path = rc
                        break

            if not fragment_path:
                logger.warning(f"Audio fragment audio-{i:02d} not found (variant, descriptive, numeric), skipping")
                continue

            components.append(
                LoopedAudioFragment(
                    start_seconds=0.0,
                    path=fragment_path,
                    gain=component_gain,
                    loop_duration_seconds=0.0,  # 0 = loop for full mix duration
                )
            )

        if include_quindar:
            # Place trailing quindar right after the voice clip
            voice_duration = 0.5  # fallback
            try:
                import wave

                with wave.open(tts_clip_path, "rb") as wf:
                    sr = wf.getframerate() or 0
                    frames = wf.getnframes() or 0
                if sr > 0 and frames > 0:
                    voice_duration = frames / float(sr)
            except Exception:
                pass
            end_time = voice_start + voice_duration
            components.append(SineBeep(start_seconds=end_time + 0.05, duration_seconds=0.25, frequency_hz=2475.0, gain=quindar_gain))

        if include_static:
            components.append(
                WhiteNoise(
                    start_seconds=0.0,
                    duration_seconds=max(0.001, end_time),
                    gain=float(payload.get("static_gain", 0.08)),
                    intensity=float(payload.get("static_intensity", 0.6)),
                    lowpass_hz=float(payload.get("static_lowpass_hz", 5000.0)),
                    highpass_hz=float(payload.get("static_highpass_hz", 80.0)),
                )
            )

        if bool(payload.get("include_rumble", False)):
            rumble_gain = float(payload.get("rumble_gain", 0.05))
            rumble_frequency_hz = float(payload.get("rumble_frequency_hz", 55.0))
            components.append(
                SineBeep(
                    start_seconds=0.0,
                    duration_seconds=max(0.001, end_time),
                    frequency_hz=rumble_frequency_hz,
                    gain=rumble_gain,
                    attack_seconds=0.02,
                    release_seconds=0.05,
                )
            )
            components.append(
                SineBeep(
                    start_seconds=0.0,
                    duration_seconds=max(0.001, end_time),
                    frequency_hz=rumble_frequency_hz * 2.0,
                    gain=rumble_gain * 0.25,
                    attack_seconds=0.02,
                    release_seconds=0.05,
                )
            )

        post_effects = []
        if bool(payload.get("include_echo", False)):
            post_effects.append(
                Echo(
                    delay_ms=float(payload.get("echo_delay_ms", 90.0)),
                    decay=float(payload.get("echo_decay", 0.25)),
                    wet=float(payload.get("echo_wet", 0.12)),
                )
            )

        wav_bytes = render_wav_bytes(components, post_effects=post_effects)
        _save_last_playback(wav_bytes)
        return HttpResponse(wav_bytes, content_type="audio/wav")

    # Defaults tuned for audibility without being painfully loud.
    modem_gain = float(payload.get("modem_gain", 0.8))
    carrier_frequency_hz = float(payload.get("carrier_frequency_hz", 1800.0))
    carrier_gain = float(payload.get("carrier_gain", 0.15))
    baud_rate = int(payload.get("baud_rate", 1200))
    mark_frequency_hz = float(payload.get("mark_frequency_hz", 1200.0))
    space_frequency_hz = float(payload.get("space_frequency_hz", 2200.0))
    wow_rate_hz = float(payload.get("wow_rate_hz", 0.0))
    wow_depth_hz = float(payload.get("wow_depth_hz", 0.0))

    # Build components with simple timing:
    # optional quindar_start → modem → optional quindar_end; static overlays full duration.
    quindar_duration = 0.25
    quindar_gap = 0.05
    modem_start = (quindar_duration + quindar_gap) if include_quindar else 0.0

    # Kermit framing is 10 bits/char (start + 7 data + parity + stop).
    bits_per_char = 10
    attack = 0.01
    release = 0.01
    modem_duration = (len(text) * bits_per_char) / float(max(1, baud_rate)) + attack + release

    components = []
    if include_quindar:
        components.append(SineBeep(start_seconds=0.0, duration_seconds=quindar_duration, frequency_hz=2525.0, gain=quindar_gain))

    components.append(
        ModemNoise(
            start_seconds=modem_start,
            text=text,
            gain=modem_gain,
            baud_rate=baud_rate,
            mark_frequency_hz=mark_frequency_hz,
            space_frequency_hz=space_frequency_hz,
            carrier_frequency_hz=carrier_frequency_hz,
            carrier_gain=carrier_gain,
            attack_seconds=attack,
            release_seconds=release,
            wow_rate_hz=wow_rate_hz,
            wow_depth_hz=wow_depth_hz,
        )
    )

    end_time = modem_start + modem_duration
    if include_quindar:
        components.append(
            SineBeep(
                start_seconds=end_time + quindar_gap,
                duration_seconds=quindar_duration,
                frequency_hz=2475.0,
                gain=quindar_gain,
            )
        )
        end_time = end_time + quindar_gap + quindar_duration

    wav_bytes = render_wav_bytes(components, post_effects=[])
    return HttpResponse(wav_bytes, content_type="audio/wav")

