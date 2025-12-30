"""
Basic presence checks for audio assets.

We must have:
1) At least one generated voice WAV under audio/voices/generated
2) At least one room-tone candidate WAV under audio/voices/raw (combined*.wav)
"""
from pathlib import Path


def test_audio_assets_present():
    repo_root = Path(__file__).resolve().parent.parent

    voices_dir = repo_root / "audio" / "voices" / "generated"
    voice_files = sorted(voices_dir.glob("*.wav"))
    assert voices_dir.exists(), "voices dir missing: audio/voices/generated"
    assert voice_files, "No generated voice WAVs found under audio/voices/generated"

    raw_dir = repo_root / "audio" / "voices" / "raw"
    room_tone_candidates = sorted(raw_dir.glob("**/combined*.wav"))
    assert raw_dir.exists(), "raw voices dir missing: audio/voices/raw"
    assert room_tone_candidates, "No room-tone candidate WAVs found under audio/voices/raw (combined*.wav)"

