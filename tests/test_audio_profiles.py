import glob
from pathlib import Path

import pytest
from django.utils import timezone

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale


def _has_generated_voices():
    root = Path(__file__).resolve().parent.parent
    return bool(glob.glob(str(root / "audio" / "voices" / "generated" / "*.wav")))

def _room_tone_candidates():
    root = Path(__file__).resolve().parent.parent
    return list((root / "audio" / "voices" / "raw").glob("**/combined*.wav"))


@pytest.mark.skipif(not _has_generated_voices(), reason="No generated voices found under audio/voices/generated")
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
    # Room tone preset based on ship size
    rt = profile.get_room_tone_params()
    assert rt.get("preset") is not None
    # Voice file should exist
    root = Path(__file__).resolve().parent.parent
    voice_path = root / "audio" / "voices" / "generated" / f"{voice}.wav"
    assert voice_path.exists()


@pytest.mark.skipif(not _has_generated_voices(), reason="No generated voices found under audio/voices/generated")
@pytest.mark.django_db(transaction=True)
def test_controller_audio_profile_has_voice_and_room_tone():
    loc = Location.objects.create(name="Mars Control", scale=Scale.STATION)
    ctrl = Controller.create(location=loc)
    profile = ctrl.audio_profile
    assert profile is not None
    voice = profile.get_voice_params().get("voice_template")
    assert voice, "Controller should have a voice_template assigned"
    rt = profile.get_room_tone_params()
    assert rt.get("preset") == "room_tone_controller"
    root = Path(__file__).resolve().parent.parent
    voice_path = root / "audio" / "voices" / "generated" / f"{voice}.wav"
    assert voice_path.exists()


@pytest.mark.skipif(not _has_generated_voices(), reason="No generated voices found under audio/voices/generated")
@pytest.mark.django_db(transaction=True)
def test_satellite_audio_profile_has_voice_and_no_room_tone():
    sat = Satellite.create(name="NAVSAT ALPHA")
    profile = sat.audio_profile
    assert profile is not None
    voice = profile.get_voice_params().get("voice_template")
    assert voice, "Satellite should have a voice_template assigned"
    rt = profile.get_room_tone_params()
    assert not rt.get("enabled", False)
    root = Path(__file__).resolve().parent.parent
    voice_path = root / "audio" / "voices" / "generated" / f"{voice}.wav"
    assert voice_path.exists()


@pytest.mark.django_db(transaction=True)
def test_audio_assets_available_for_profiles():
    """
    Basic presence checks for assets used by audio profiles.

    - Generated voice WAVs are required for assigning voice_template.
    - Room tone uses presets (not files), but we keep a sanity check that
      combined raw WAVs exist for potential room-tone sources.
    """
    root = Path(__file__).resolve().parent.parent
    voices_dir = root / "audio" / "voices" / "generated"
    voice_files = sorted(voices_dir.glob("*.wav"))
    assert voices_dir.exists(), "voices dir missing: audio/voices/generated"
    assert voice_files, "No generated voice WAVs found under audio/voices/generated"

    raw_dir = root / "audio" / "voices" / "raw"
    room_tone_candidates = _room_tone_candidates()
    assert raw_dir.exists(), "raw voices dir missing: audio/voices/raw"
    assert room_tone_candidates, "No room-tone candidate WAVs found under audio/voices/raw (combined*.wav)"

