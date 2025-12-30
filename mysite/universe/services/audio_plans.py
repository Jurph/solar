"""
Audio plan construction (Python-side).

An "audio plan" is metadata attached to each dialogue event describing what
audio should play as that event is displayed. The browser should treat this as
an audio queue to stream alongside the text feed.

Uses Actor.audio_profile to get parametric audio configuration (room tone,
static, voiceprint, etc.) so that (Actor + Text) is sufficient to generate
tailored audio clips.
"""

from __future__ import annotations

from typing import Any
import re

from mysite.universe.models.actor import Actor 
from mysite.universe.models.audio_profile import AudioProfile
from mysite.universe.models.event import DialogueEventLog


def build_audio_plan_for_dialogue_event(event: DialogueEventLog) -> list[dict[str, Any]]:
    """
    Build an audio plan for a single DialogueEventLog using the Actor's AudioProfile.

    Plan contract (v0):
    - List of actions, each action includes:
      - trigger: "event_start" | "event_end" | "event_during"
      - preset:  name of a Python-defined WAV preset (see views/audio.py)
      - params:  optional dict of preset-specific parameters
    
    The Actor's AudioProfile provides:
    - Room tone parameters (engine rumble, reverb) - used for "event_during" actions
    - Static/radio noise parameters
    - Quindar tone customization
    - Voiceprint parameters (TODO: TTS not implemented yet)
    
    TODO: TTS Integration
    - When TTS is implemented, add "tts" action type with voice_params from profile
    - TTS will use: voice_template, pitch_shift_cents, speed_factor from AudioProfile
    - For now, no TTS actions are generated - only tones, static, and room tone
    """
    # Look up Actor by name (DialogueEventLog stores actor_name as string)
    # Try to get from concrete models first (Satellite, Pilot, Controller) to get proper type
    from mysite.universe.models.actor import Satellite, Pilot, Controller
    
    actor = None
    is_satellite = False
    
    # Names are not unique; always use filter().first() to avoid MultipleObjectsReturned.
    # Prefer concrete subclasses in a stable order so audio behavior is deterministic.

    # Try Satellite first (for nav broadcasts)
    actor = Satellite.objects.filter(name=event.actor_name).order_by("-id").first()
    if actor is not None:
        is_satellite = True
    
    # Try Pilot if not found
    if actor is None:
        actor = Pilot.objects.filter(name=event.actor_name).order_by("-id").first()
    
    # Try Controller if not found
    if actor is None:
        actor = Controller.objects.filter(name=event.actor_name).order_by("-id").first()
    
    # Fallback to base Actor model
    if actor is None:
        actor = Actor.objects.filter(name=event.actor_name).order_by("-id").first()
        if actor is None:
            # Fallback: use default presets if actor not found
            return [
                {"trigger": "event_start", "preset": "quindar_start"},
                {"trigger": "event_end", "preset": "quindar_end"},
            ]
    
    # Get or create AudioProfile for this actor
    profile, _ = AudioProfile.objects.get_or_create(
        actor=actor,
        defaults={}
    )
    # If profile was just created, initialize with defaults
    if not profile.actor:
        profile = AudioProfile.create_default_for_actor(actor)
    
    plan: list[dict[str, Any]] = []
    
    # Get parameter sections from JSON
    quindar_params = profile.get_quindar_params()
    room_tone_params = profile.get_room_tone_params()
    static_params = profile.get_static_params()
    
    # Shared quindars for all actors
    plan.append({
        "trigger": "event_start",
        "preset": "quindar_start",
        "params": {
            "frequency_hz": quindar_params.get("start_freq_hz", 2525.0),
            "gain": quindar_params.get("gain", 0.9),
        }
    })

    if is_satellite:
        # Satellites: TTS voice plus modem tail
        # modem_data: payload; default to event.text
        modem_data = event.metadata.get("modem_data") if event.metadata else event.text
        # Room tone disabled for satellites
    else:
        # Pilots/Controllers: room tone + static
        if room_tone_params.get("enabled", True):
            plan.append({
                "trigger": "event_during",
                "preset": room_tone_params.get("preset", "room_tone_placeholder"),
                "params": room_tone_params,
            })
        if static_params.get("intensity", 0) > 0:
            plan.append({
                "trigger": "event_during",
                "preset": "static_medium",  # TODO: derive preset dynamically
                "params": static_params,
            })

    # Quindar end tone (customized from profile)
    plan.append({
        "trigger": "event_end",
        "preset": "quindar_end",
        "params": {
            "frequency_hz": quindar_params.get("end_freq_hz", 2475.0),
            "gain": quindar_params.get("gain", 0.9),
        }
    })
    
    # Add TTS action if voice template exists
    voice_params = profile.get_voice_params()
    voice_template = voice_params.get("voice_template")
    
    # If no explicit voice_template, try to infer from actor type
    if not voice_template:
        from mysite.universe.models.actor import Pilot, Controller
        if isinstance(actor, Pilot):
            voice_template = "pilot_default"
        elif isinstance(actor, Controller):
            voice_template = "controller_default"
        # Satellites don't get TTS (they use modem noise)
    
    if voice_template:
        tts_text = _sentence_case(event.text or "")
        plan.append({
            "trigger": "event_during",
            "action": "tts",
            "text": tts_text,
            "voice_id": voice_template,
            "params": {
                "pitch_shift_cents": voice_params.get("pitch_shift_cents", 0),
                "speed_factor": voice_params.get("speed_factor", 1.0),
                "cfg_weight": 0.5,  # Chatterbox default
                "exaggeration": 0.5,  # Chatterbox default
            }
        })
        if is_satellite:
            plan.append({
                "trigger": "event_end",
                "preset": "modem_noise_example",
                "params": {
                    "text": modem_data,
                    "gain": 0.8,
                    "baud_rate": 300,
                    "carrier_frequency_hz": 1800.0,
                    "carrier_gain": 0.15,
                    "mark_frequency_hz": 1200.0,
                    "space_frequency_hz": 2200.0,
                },
            })
    
    return plan


def _sentence_case(text: str) -> str:
    """
    Basic sentence case: if all-caps, lower then capitalize first alpha.
    """
    if not text:
        return text
    t = text.strip()
    if not t:
        return text
    if t.isupper():
        t = t.lower()
    for i, ch in enumerate(t):
        if ch.isalpha():
            return t[:i] + ch.upper() + t[i + 1 :]
    return t


