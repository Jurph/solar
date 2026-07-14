"""
Audio Profile model for Actors.

Stores audio configuration metadata that determines which pre-generated WAV files
and voice templates to use for each Actor. This enables consistent audio identity
per character without requiring regeneration.

Audio Pipeline:
- Voice: TTS via chatterbox using reference voice WAV files (e.g., pilot-M-002.wav)
- Room tone: Pre-generated engine/ambient WAV files (small/medium/large_engine_noise.wav, Control_station_noise.wav)
- Quindars: Pre-generated tones
- Modem noise: 300-baud FSK encoding (satellites only)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from mysite.universe.models.actor import Actor


class AudioProfile(models.Model):
    """
    Audio configuration metadata for an Actor.

    Stores which pre-generated audio files to use and how to apply them.
    All parameters are stored as JSON to avoid migrations when adding new features.

    The `params` JSONField structure:
    {
        "room_tone": {
            "enabled": bool,
            "wav_file": str | null,  # Pre-generated WAV: "small_engine_noise.wav", "Control_station_noise.wav", etc.
            "engine_rumble_base_freq_hz": float,    # Metadata (not used for synthesis)
            "engine_rumble_harmonics": int,         # Metadata (not used for synthesis)
            "engine_rumble_intensity": float,       # Metadata (not used for synthesis)
            "reverb_delay_ms": float,               # Metadata (not used for synthesis)
            "reverb_decay_factor": float,           # Metadata (not used for synthesis)
            "reverb_room_size_hint": str,           # Metadata: "small" | "medium" | "large" | "station"
        },
        "static": {
            "intensity": float,         # Metadata describing the room tone's static component
            "lowpass_hz": float | null,
            "highpass_hz": float | null,
            "bandwidth_hz": float | null,
        },
        "quindar": {
            "start_freq_hz": float,     # Quindar tone frequencies (for reference)
            "end_freq_hz": float,
            "gain": float,
        },
        "voiceprint": {
            "voice_template": str | null,  # Reference voice file stem for chatterbox TTS (e.g., "pilot-M-002")
            "pitch_shift_cents": int,      # TTS pitch adjustment
            "speed_factor": float,         # TTS speed multiplier
        },
    }

    Note: Most numeric parameters (engine_rumble_*, reverb_*, static.*) are metadata for
    documentation/display purposes. The actual audio comes from pre-generated WAV files.
    """

    # One-to-one relationship with Actor
    actor = models.OneToOneField(
        "Actor",
        on_delete=models.CASCADE,
        related_name="audio_profile",
        null=True,
        blank=True,
        help_text="The Actor this audio profile belongs to",
    )

    # All audio parameters stored as JSON (flexible, no migrations needed for new params)
    params = models.JSONField(
        default=dict,
        blank=True,
        help_text="Audio parameters as JSON: room_tone, static, quindar, voiceprint, etc.",
    )

    class Meta:
        app_label = "universe"
        verbose_name = "Audio Profile"
        verbose_name_plural = "Audio Profiles"

    def __str__(self):
        actor_name = self.actor.name if self.actor else "Unassigned"
        return f"AudioProfile for {actor_name}"

    @classmethod
    def default_params_for_actor(cls, actor: Actor) -> dict:
        """
        Build the default params JSON for an actor without touching the database.

        Used by create_default_for_actor() (which persists the result) and by
        read-only callers (e.g. event_feed's audio-plan builder) that need
        sensible params for an actor whose profile row is missing but must not
        write one.
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
            # Satellite: no static, no reverb, no room tone
            params["static"]["intensity"] = 0.0
            params["room_tone"]["enabled"] = False
            params["room_tone"]["engine_rumble_intensity"] = 0.0
            params["room_tone"]["reverb_delay_ms"] = 0.0
            params["room_tone"]["wav_file"] = None

        elif isinstance(actor, Pilot):
            # Pilot: small-room reverb, engine rumble + static from ship size
            params["room_tone"]["reverb_room_size_hint"] = "small"
            params["room_tone"]["reverb_delay_ms"] = 30.0

            # Derive engine rumble, static, and WAV file from ship size enum
            from mysite.universe.models.ship import Ship

            if hasattr(actor, "ship") and actor.ship and actor.ship.size:
                if actor.ship.size == Ship.Size.SMALL:
                    params["room_tone"]["engine_rumble_base_freq_hz"] = 80.0
                    params["static"]["intensity"] = 0.03
                    params["room_tone"]["wav_file"] = "small_engine_noise.wav"
                elif actor.ship.size == Ship.Size.LARGE:
                    params["room_tone"]["engine_rumble_base_freq_hz"] = 40.0
                    params["static"]["intensity"] = 0.08
                    params["room_tone"]["wav_file"] = "large_engine_noise.wav"
                else:  # Ship.Size.MEDIUM
                    params["room_tone"]["engine_rumble_base_freq_hz"] = 60.0
                    params["static"]["intensity"] = 0.05
                    params["room_tone"]["wav_file"] = "medium_engine_noise.wav"
            else:
                # Default to medium if no ship
                params["room_tone"]["engine_rumble_base_freq_hz"] = 60.0
                params["static"]["intensity"] = 0.05
                params["room_tone"]["wav_file"] = "medium_engine_noise.wav"

        elif isinstance(actor, Controller):
            # Controller: large-room reverb, no engine rumble, station ambient
            params["room_tone"]["reverb_room_size_hint"] = "large"
            params["room_tone"]["reverb_delay_ms"] = 150.0
            params["room_tone"]["engine_rumble_intensity"] = 0.0  # No engine rumble
            params["static"]["intensity"] = 0.1  # Light static for ground stations
            params["room_tone"]["wav_file"] = "Control_station_noise.wav"

        else:
            # Unknown actor type - use minimal defaults
            params["room_tone"]["enabled"] = False
            params["static"]["intensity"] = 0.0
            params["room_tone"]["wav_file"] = None

        return params

    @classmethod
    def create_default_for_actor(cls, actor: Actor) -> AudioProfile:
        """
        Create a default audio profile for an actor, assigning the appropriate
        pre-generated room tone WAV file based on actor type and ship size.

        Room tone assignments:
        - Satellite: None (no room tone, just modem noise)
        - Pilot: Ship-size-dependent engine noise WAV
          - Small ship: small_engine_noise.wav
          - Medium ship: medium_engine_noise.wav
          - Large ship: large_engine_noise.wav
        - Controller: Station ambient (Control_station_noise.wav)

        Args:
            actor: The Actor to create a profile for

        Returns:
            A new AudioProfile instance with params JSON pointing to the appropriate WAV files
        """
        params = cls.default_params_for_actor(actor)

        profile, created = cls.objects.get_or_create(
            actor=actor, defaults={"params": params}
        )

        # Preserve any existing voice_template if already set
        existing_voice_template = None
        if not created:
            existing_voice_template = (profile.get_voice_params() or {}).get(
                "voice_template"
            )

        # Always refresh params based on current actor state (e.g., ship size changes)
        profile.params = params
        if existing_voice_template:
            vp = profile.params.get("voiceprint", {}) or {}
            vp["voice_template"] = existing_voice_template
            profile.params["voiceprint"] = vp

        profile.save()
        return profile

    def get_room_tone_params(self) -> dict:
        """
        Get room tone parameters as a dictionary.

        Returns:
            Dict from params["room_tone"] including:
            - wav_file: Pre-generated room tone WAV filename
            - enabled: Whether room tone should be played
            - Other metadata fields (for documentation/display)
        """
        return self.params.get("room_tone", {})

    def get_static_params(self) -> dict:
        """
        Get static/radio noise parameters as a dictionary.

        Note: These are metadata describing the room tone's static characteristics.
        The actual static is part of the pre-generated room tone WAV file.

        Returns:
            Dict from params["static"] with intensity and filter metadata
        """
        return self.params.get("static", {})

    def get_quindar_params(self) -> dict:
        """
        Get Quindar tone parameters as a dictionary.

        Note: Quindars are pre-generated tones. These params are metadata for reference.

        Returns:
            Dict from params["quindar"] with frequency and gain metadata
        """
        return self.params.get("quindar", {})

    def get_voice_params(self) -> dict:
        """
        Get voiceprint/TTS parameters as a dictionary.

        Returns:
            Dict from params["voiceprint"] with:
            - voice_template: Reference voice file stem (e.g., "pilot-M-002") used by chatterbox
            - pitch_shift_cents: TTS pitch adjustment
            - speed_factor: TTS speed multiplier
        """
        return self.params.get("voiceprint", {})

    def set_voice_template(self, voice_template: str):
        params = self.params or {}
        vp = params.get("voiceprint", {})
        vp["voice_template"] = voice_template
        params["voiceprint"] = vp
        self.params = params
        self.save(update_fields=["params"])

    def set_room_tone_wav(self, wav_file: str | None):
        """Set the room tone WAV file for this actor."""
        params = self.params or {}
        rt = params.get("room_tone", {})
        if wav_file:
            rt["wav_file"] = wav_file
            rt["enabled"] = True
        else:
            rt["wav_file"] = None
            rt["enabled"] = False
        params["room_tone"] = rt
        self.params = params
        self.save(update_fields=["params"])
