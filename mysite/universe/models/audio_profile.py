"""
Audio Profile model for Actors.

Stores parametric audio configuration (room tone, static, voiceprint, reverb)
so that (Actor + Text) is sufficient to generate tailored audio clips.
"""

from __future__ import annotations

from django.db import models


class AudioProfile(models.Model):
    """
    Parametric audio configuration for an Actor.
    
    All parameters are stored as JSON in the database so that audio generation
    can be deterministic and tailored per-actor without hardcoding, and we can
    add new TTS/audio features without requiring migrations.
    
    When an Actor has an AudioProfile, (Actor + Text) is sufficient to
    generate a complete audio clip with room tone, static, voiceprint, etc.
    
    The `params` JSONField structure:
    {
        "room_tone": {
            "enabled": bool,
            "engine_rumble_base_freq_hz": float,
            "engine_rumble_harmonics": int,
            "engine_rumble_intensity": float,
            "reverb_delay_ms": float,
            "reverb_decay_factor": float,
            "reverb_room_size_hint": str,  # "small" | "medium" | "large" | "station"
        },
        "static": {
            "intensity": float,
            "lowpass_hz": float | null,
            "highpass_hz": float | null,
            "bandwidth_hz": float | null,
        },
        "quindar": {
            "start_freq_hz": float,
            "end_freq_hz": float,
            "gain": float,
        },
        "voiceprint": {
            # TODO: TTS not implemented yet - structure reserved for future
            "voice_template": str | null,
            "pitch_shift_cents": int,
            "speed_factor": float,
            # Additional TTS parameters can be added here without migrations
        },
    }
    """
    
    # One-to-one relationship with Actor
    actor = models.OneToOneField(
        'Actor',
        on_delete=models.CASCADE,
        related_name='audio_profile',
        null=True,
        blank=True,
        help_text="The Actor this audio profile belongs to"
    )
    
    # All audio parameters stored as JSON (flexible, no migrations needed for new params)
    params = models.JSONField(
        default=dict,
        blank=True,
        help_text="Audio parameters as JSON: room_tone, static, quindar, voiceprint, etc."
    )
    
    class Meta:
        app_label = 'universe'
        verbose_name = "Audio Profile"
        verbose_name_plural = "Audio Profiles"
    
    def __str__(self):
        actor_name = self.actor.name if self.actor else "Unassigned"
        return f"AudioProfile for {actor_name}"
    
    @classmethod
    def create_default_for_actor(cls, actor: 'Actor') -> 'AudioProfile':
        """
        Create a default audio profile for an actor with sensible defaults.
        
        Defaults by actor type:
        - Satellite: no static, no reverb (clean transmission)
        - Pilot: small-room reverb, engine rumble + static from ship size (default: medium ship)
        - Controller: large-room reverb, no engine rumble (station ambient only)
        
        Args:
            actor: The Actor to create a profile for
            
        Returns:
            A new AudioProfile instance with default params JSON
        """
        from mysite.universe.models.actor import Pilot, Controller, Satellite
        
        # Base structure (will be customized by actor type)
        params = {
            "room_tone": {
                "enabled": True,
                "engine_rumble_base_freq_hz": 60.0,
                "engine_rumble_harmonics": 3,
                "engine_rumble_intensity": 0.3,
                "reverb_delay_ms": 50.0,
                "reverb_decay_factor": 0.5,
                "reverb_room_size_hint": "medium",
            },
            "static": {
                "intensity": 0.05,  # Very faint default (will be adjusted by type)
                "lowpass_hz": 3000.0,
                "highpass_hz": 200.0,
                "bandwidth_hz": None,
            },
            "quindar": {
                "start_freq_hz": 2525.0,
                "end_freq_hz": 2475.0,
                "gain": 0.9,
            },
            "voiceprint": {
                "voice_template": None,
                "pitch_shift_cents": 0,
                "speed_factor": 1.0,
            },
        }
        
        # Customize by actor type
        if isinstance(actor, Satellite):
            # Satellite: no static, no reverb
            params["static"]["intensity"] = 0.0
            params["room_tone"]["enabled"] = False
            params["room_tone"]["engine_rumble_intensity"] = 0.0
            params["room_tone"]["reverb_delay_ms"] = 0.0
        
        elif isinstance(actor, Pilot):
            # Pilot: small-room reverb, engine rumble + static from ship size
            params["room_tone"]["reverb_room_size_hint"] = "small"
            params["room_tone"]["reverb_delay_ms"] = 30.0
            
            # Derive engine rumble and static from ship size (default: medium)
            ship_size = 'medium'  # Default
            if hasattr(actor, 'ship') and actor.ship and actor.ship.size:
                ship_size = actor.ship.size.lower()
            
            if ship_size == 's' or 'small' in ship_size:
                params["room_tone"]["engine_rumble_base_freq_hz"] = 80.0
                params["static"]["intensity"] = 0.03  # Very faint for small ships
            elif ship_size == 'l' or 'large' in ship_size or 'freighter' in ship_size:
                params["room_tone"]["engine_rumble_base_freq_hz"] = 40.0
                params["static"]["intensity"] = 0.08  # Slightly more for large ships
            else:
                # Medium ship (defaults already set)
                params["room_tone"]["engine_rumble_base_freq_hz"] = 60.0
                params["static"]["intensity"] = 0.05  # Very faint for medium ships
        
        elif isinstance(actor, Controller):
            # Controller: large-room reverb, no engine rumble
            params["room_tone"]["reverb_room_size_hint"] = "large"
            params["room_tone"]["reverb_delay_ms"] = 150.0
            params["room_tone"]["engine_rumble_intensity"] = 0.0  # No engine rumble
            params["static"]["intensity"] = 0.1  # Light static for ground stations
        
        else:
            # Unknown actor type - use minimal defaults
            params["room_tone"]["enabled"] = False
            params["static"]["intensity"] = 0.0
        
        profile = cls(actor=actor, params=params)
        profile.save()
        return profile
    
    def get_room_tone_params(self) -> dict:
        """
        Get room tone parameters as a dictionary for audio synthesis.
        
        Returns:
            Dict from params["room_tone"] with all room tone settings
        """
        return self.params.get("room_tone", {})
    
    def get_static_params(self) -> dict:
        """
        Get static/radio noise parameters as a dictionary for audio synthesis.
        
        Returns:
            Dict from params["static"] with all static noise settings
        """
        return self.params.get("static", {})
    
    def get_quindar_params(self) -> dict:
        """
        Get Quindar tone parameters as a dictionary for audio synthesis.
        
        Returns:
            Dict from params["quindar"] with Quindar tone settings
        """
        return self.params.get("quindar", {})
    
    def get_voice_params(self) -> dict:
        """
        Get voiceprint/TTS parameters as a dictionary.
        
        Returns:
            Dict from params["voiceprint"] with TTS settings
            TODO: TTS not implemented yet - this structure is reserved for future use
        """
        return self.params.get("voiceprint", {})

