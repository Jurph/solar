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
    # Look up Actor by name (DialogueEventLog stores actor_name as string)
    # Try to get from concrete models first (Satellite, Pilot, Controller) to get proper type
    from mysite.universe.models.actor import Satellite, Pilot, Controller
    
    actor = None
    is_satellite = False
    
    # Try Satellite first (for nav broadcasts)
    try:
        actor = Satellite.objects.get(name=event.actor_name)
        is_satellite = True
    except Satellite.DoesNotExist:
        pass
    
    # Try Pilot if not found
    if actor is None:
        try:
            actor = Pilot.objects.get(name=event.actor_name)
        except Pilot.DoesNotExist:
            pass
    
    # Try Controller if not found
    if actor is None:
        try:
            actor = Controller.objects.get(name=event.actor_name)
        except Controller.DoesNotExist:
            pass
    
    # Fallback to base Actor model
    if actor is None:
        try:
            actor = Actor.objects.get(name=event.actor_name)
        except Actor.DoesNotExist:
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
    
    if is_satellite:
        # Satellites: modem noise encoding the technical data
        # The human-readable announcement is displayed, and read out loud by a robotic voice, and then the technical data is encoded as modem noise
        # Check metadata for modem_data, fallback to event.text for backward compatibility
        modem_data = event.metadata.get("modem_data") if event.metadata else event.text
        
        plan.append({
            "trigger": "event_during",
            "preset": "modem_noise_example",  # Will be replaced with text-specific preset
            "params": {
                "text": modem_data,  # Technical data to encode as modem noise
                "gain": 0.8,
                "carrier_frequency_hz": 1800.0,
                "carrier_gain": 0.15,
            }
        })
    else:
        # Pilots/Controllers: Quindar tones + room tone + static
        
        # Quindar start tone (customized from profile)
        plan.append({
            "trigger": "event_start",
            "preset": "quindar_start",
            "params": {
                "frequency_hz": quindar_params.get("start_freq_hz", 2525.0),
                "gain": quindar_params.get("gain", 0.9),
            }
        })
        
        # Room tone during event (if enabled)
        # TODO: Room tone synthesis not yet implemented - this is a placeholder
        # When implemented, this will generate engine_rumble + reverb based on profile params
        if room_tone_params.get("enabled", True):
            plan.append({
                "trigger": "event_during",
                "preset": "room_tone_placeholder",  # TODO: Replace with actual room tone synthesis
                "params": room_tone_params,
            })
        
        # Static/radio noise (if configured)
        if static_params.get("intensity", 0) > 0:
            plan.append({
                "trigger": "event_during",
                "preset": "static_medium",  # TODO: Generate from static_params dynamically
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
    
    # TODO: TTS action would go here when TTS is implemented
    # if profile.voice_template:
    #     plan.append({
    #         "trigger": "event_during",
    #         "action": "tts",
    #         "text": event.text,
    #         "params": profile.get_voice_params(),
    #     })
    
    return plan


