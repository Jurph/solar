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
    # Look up Actor by actor_id (preferred) or name (fallback)
    # DialogueEventLog stores actor_name as string, but metadata may have actor_id
    from mysite.universe.models.actor import Satellite, Pilot, Controller
    import logging
    log = logging.getLogger(__name__)
    
    actor = None
    is_satellite = False
    
    # CRITICAL: Always use actor_id from metadata - never use name lookups
    # Actors are uniquely identified by ID, not name
    metadata = getattr(event, "metadata", None) or {}
    actor_id = metadata.get("actor_id")
    
    if not actor_id:
        log.error("Event %s missing actor_id in metadata (name='%s') - cannot build audio plan. "
                 "Event should have actor_id stored in metadata.", event.id, event.actor_name)
        # Return minimal plan with just Quindars - no TTS, no room tone
        return [
            {"action": "quindar_start"},
            {"action": "quindar_end"},
        ]
    
    try:
        actor = Actor.objects.get(id=actor_id)
        if isinstance(actor, Satellite):
            is_satellite = True
    except Actor.DoesNotExist:
        log.error("Event %s references non-existent actor_id=%s (name='%s') - cannot build audio plan", 
                 event.id, actor_id, event.actor_name)
        # Return minimal plan with just Quindars - no TTS, no room tone
        return [
            {"action": "quindar_start"},
            {"action": "quindar_end"},
        ]
    
    if actor is None:
                # Fallback: use default presets if actor not found
                return [
                    {"trigger": "event_start", "preset": "quindar_start"},
                    {"trigger": "event_end", "preset": "quindar_end"},
                ]
    
    # Get or create AudioProfile for this actor
    # If missing or incomplete, assign it on-demand
    try:
        profile = actor.audio_profile
        # Check if profile is incomplete (no voice_template)
        vp = profile.get_voice_params() or {}
        if not vp.get("voice_template"):
            # Profile exists but incomplete - assign it
            from mysite.universe.models.actor import Pilot, Controller, Satellite
            if isinstance(actor, Pilot):
                Pilot.assign_audio_profile(actor)
            elif isinstance(actor, Controller):
                Controller.assign_audio_profile(actor)
            elif isinstance(actor, Satellite):
                Satellite.assign_audio_profile(actor)
            profile = actor.audio_profile  # Reload after assignment
    except AudioProfile.DoesNotExist:
        # Profile missing - assign it on-demand
        from mysite.universe.models.actor import Pilot, Controller, Satellite
        if isinstance(actor, Pilot):
            Pilot.assign_audio_profile(actor)
        elif isinstance(actor, Controller):
            Controller.assign_audio_profile(actor)
        elif isinstance(actor, Satellite):
            Satellite.assign_audio_profile(actor)
        else:
            # Fallback for base Actor - create default profile
            profile = AudioProfile.create_default_for_actor(actor)
        profile = actor.audio_profile  # Reload after assignment
    
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


