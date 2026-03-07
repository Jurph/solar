"""
Audio profile tests.

Tests AudioProfile behavior:
- Voice template assignment per actor type
- Default audio profile parameters (room tone, static, etc.)
- Audio profile accessors and string representation
- Filesystem dependencies (voice files, room tone sources)
"""
import glob
from pathlib import Path

import pytest
from django.test import TestCase

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.audio_profile import AudioProfile
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale


def _has_voices():
    """Check if voice files exist in static/universe/voices/"""
    root = Path(__file__).resolve().parent.parent
    voices_dir = root / "mysite" / "universe" / "static" / "universe" / "voices"
    return bool(glob.glob(str(voices_dir / "*.wav")))

def _room_tone_candidates():
    root = Path(__file__).resolve().parent.parent
    return list((root / "audio" / "voices" / "raw").glob("**/combined*.wav"))


@pytest.mark.skipif(not _has_voices(), reason="No voice files found in mysite/universe/static/universe/voices")
@pytest.mark.django_db(transaction=True)
def test_pilot_audio_profile_has_voice_and_room_tone():
    # Minimal location for ship
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    profile = pilot.audio_profile
    assert profile is not None
    voice = profile.get_voice_params().get("voice_template")
    assert voice, "Pilot should have a voice_template assigned"
    # Room tone WAV file based on ship size
    rt = profile.get_room_tone_params()
    assert rt.get("wav_file") is not None
    # Voice file should exist
    root = Path(__file__).resolve().parent.parent
    voices_dir = root / "mysite" / "universe" / "static" / "universe" / "voices"
    voice_path = voices_dir / f"{voice}.wav"
    assert voice_path.exists(), f"Voice file not found: {voice_path}"


@pytest.mark.skipif(not _has_voices(), reason="No voice files found in mysite/universe/static/universe/voices")
@pytest.mark.django_db(transaction=True)
def test_controller_audio_profile_has_voice_and_room_tone():
    loc = Location.objects.create(name="Mars Control", scale=Scale.STATION)
    ctrl = Controller.create(location=loc)
    profile = ctrl.audio_profile
    assert profile is not None
    voice = profile.get_voice_params().get("voice_template")
    assert voice, "Controller should have a voice_template assigned"
    rt = profile.get_room_tone_params()
    assert rt.get("wav_file") == "Control_station_noise.wav"
    root = Path(__file__).resolve().parent.parent
    voices_dir = root / "mysite" / "universe" / "static" / "universe" / "voices"
    voice_path = voices_dir / f"{voice}.wav"
    assert voice_path.exists(), f"Voice file not found: {voice_path}"


@pytest.mark.django_db(transaction=True)
def test_satellite_audio_profile_has_voice_and_no_room_tone():
    """Satellites should have robotic voice but NO room tone."""
    sat = Satellite.create(name="NAVSAT ALPHA")
    profile = sat.audio_profile
    assert profile is not None
    
    # Room tone should be explicitly disabled for satellites
    rt = profile.get_room_tone_params()
    assert rt.get("wav_file") is None, "Satellites should have no room tone WAV file"
    
    # Voice is optional until satellite-*.wav files are added
    # If satellite voices exist, verify one was assigned
    root = Path(__file__).resolve().parent.parent
    voices_dir = root / "mysite" / "universe" / "static" / "universe" / "voices"
    satellite_voices = list(voices_dir.glob("satellite-*.wav"))
    
    voice = profile.get_voice_params().get("voice_template")
    if satellite_voices:
        assert voice, "Satellite should have voice_template when satellite-*.wav files exist"
        voice_path = voices_dir / f"{voice}.wav"
        assert voice_path.exists(), f"Voice file not found: {voice_path}"
    # If no satellite voices exist yet, that's okay - user is adding them


class TestAudioProfileDefaults(TestCase):
    """Test default audio profile creation and parameters."""

    def setUp(self):
        self.loc = Location.objects.create(name="Dock", scale=Scale.STATION)

    def test_create_default_for_satellite(self):
        sat = Satellite.create(name="Test Navsat")
        profile = AudioProfile.create_default_for_actor(sat)
        assert profile.actor == sat
        assert profile.params["static"]["intensity"] == 0.0
        assert profile.params["room_tone"]["enabled"] is False

    def test_create_default_for_controller(self):
        controller = Controller.create(name="Dock Control", location=self.loc)
        profile = AudioProfile.create_default_for_actor(controller)
        assert profile.params["room_tone"]["reverb_room_size_hint"] == "large"
        assert profile.params["room_tone"]["engine_rumble_intensity"] == 0.0
        assert profile.params["static"]["intensity"] == 0.1

    def test_create_default_for_pilot_ship_size_influences_static(self):
        # small ship => lower static, higher rumble freq
        small_ship = Ship.objects.create(name="S", current_location=self.loc, size=Ship.Size.SMALL)
        pilot_small = Pilot.create(name="Pilot S", ship=small_ship)
        profile_small = AudioProfile.create_default_for_actor(pilot_small)
        assert profile_small.params["static"]["intensity"] == 0.03
        assert profile_small.params["room_tone"]["engine_rumble_base_freq_hz"] == 80.0

        # large ship => higher static, lower rumble freq
        large_ship = Ship.objects.create(name="L", current_location=self.loc, size=Ship.Size.LARGE)
        pilot_large = Pilot.create(name="Pilot L", ship=large_ship)
        profile_large = AudioProfile.create_default_for_actor(pilot_large)
        assert profile_large.params["static"]["intensity"] == 0.08
        assert profile_large.params["room_tone"]["engine_rumble_base_freq_hz"] == 40.0

        # medium ship defaults are stable
        medium_ship = Ship.objects.create(name="M", current_location=self.loc, size=Ship.Size.MEDIUM)
        pilot_medium = Pilot.create(name="Pilot M", ship=medium_ship)
        profile_medium = AudioProfile.create_default_for_actor(pilot_medium)
        assert profile_medium.params["static"]["intensity"] == 0.05
        assert profile_medium.params["room_tone"]["engine_rumble_base_freq_hz"] == 60.0

    def test_create_default_for_unknown_actor_type_uses_minimal(self):
        from mysite.universe.models.actor import Actor
        actor = Actor.objects.create(name="Mystery")
        profile = AudioProfile.create_default_for_actor(actor)
        assert profile.params["room_tone"]["enabled"] is False
        assert profile.params["static"]["intensity"] == 0.0

    def test_audio_profile_param_accessors(self):
        sat = Satellite.create(name="Accessor Sat")
        profile = AudioProfile.create_default_for_actor(sat)
        assert isinstance(profile.get_room_tone_params(), dict)
        assert isinstance(profile.get_static_params(), dict)
        assert isinstance(profile.get_quindar_params(), dict)
        assert isinstance(profile.get_voice_params(), dict)

    def test_audio_profile_str_includes_actor_name(self):
        sat = Satellite.create(name="Stringy Sat")
        profile = AudioProfile.create_default_for_actor(sat)
        assert "Stringy Sat" in str(profile)

