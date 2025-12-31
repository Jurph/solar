"""
Integration test for end-to-end audio pipeline.

Tests the simplified synchronous audio generation:
1. Create dialogue events
2. Request audio via /api/event_audio/{id}/
3. Audio is generated on-demand if not cached
4. Event feed includes audio URLs
5. Output audio contains quindars + TTS + room tone
"""
import struct
import wave
import io
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.audio_profile import AudioProfile
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale


def _dummy_wav_bytes(payload: dict) -> bytes:
    """Generate a minimal valid 16-bit PCM WAV for testing."""
    # Generate a short 0.01 second clip of silence as 16-bit PCM
    sample_rate = 24000
    duration_seconds = 0.01
    num_samples = int(sample_rate * duration_seconds)
    
    # Create 16-bit signed integer samples (silence = 0)
    samples = struct.pack(f"<{num_samples}h", *([0] * num_samples))
    
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(samples)
    return buf.getvalue()


def _get_real_voice_wav_bytes() -> bytes:
    """Load a real voice WAV file to use as realistic TTS mock output."""
    voices_dir = Path(settings.BASE_DIR) / "mysite" / "universe" / "static" / "universe" / "voices"
    
    candidates = ["actor-013.wav", "pilot-M-002_canonical_all.wav", "controller-001.wav"]
    for candidate in candidates:
        path = voices_dir / candidate
        if path.exists():
            return path.read_bytes()
    
    wav_files = list(voices_dir.glob("*.wav"))
    if wav_files:
        return wav_files[0].read_bytes()
    
    pytest.skip("No voice WAV files found")


@pytest.fixture
def client():
    return Client()


@pytest.fixture(autouse=True)
def _patch_assign_audio_profile(monkeypatch):
    """Ensure actors always get a deterministic voice_template without filesystem dependency."""
    def _assign(actor_cls, actor, voice_template="test_voice"):
        # actor_cls is the class (Pilot/Controller/Satellite) because monkeypatching classmethod
        profile_obj = getattr(actor, "audio_profile", None)
        if not isinstance(profile_obj, AudioProfile):
            profile_obj = AudioProfile.create_default_for_actor(actor)
        profile_obj.set_voice_template(voice_template)
        return profile_obj

    monkeypatch.setattr(Pilot, "assign_audio_profile", classmethod(_assign))
    monkeypatch.setattr(Controller, "assign_audio_profile", classmethod(_assign))
    monkeypatch.setattr(Satellite, "assign_audio_profile", classmethod(_assign))


@pytest.fixture
def dummy_tts(monkeypatch):
    """Patch TTSService.generate to return a tiny WAV embedding JSON of the inputs."""
    from mysite.universe.services import tts_service

    def generate(text: str, voice_id: str, **kwargs):
        return _dummy_wav_bytes({"text": text, "voice_id": voice_id})

    # Patch the service singleton to return a mock
    class DummySvc:
        def generate(self, text: str, voice_id: str, **kwargs):
            return generate(text, voice_id, **kwargs)

    monkeypatch.setattr(tts_service, "_tts_service", DummySvc())
    return generate


@pytest.fixture(autouse=True)
def _patch_sim_time(monkeypatch):
    """Make simulation time far in the future so freshly created events are included."""
    from mysite.universe.models import simulation
    from mysite.universe.models.event import DialogueEventLog

    monkeypatch.setattr(simulation, "get_simulation_time", lambda: 4e9)

    # Clear any prior events for isolation
    DialogueEventLog.objects.all().delete()


@pytest.mark.django_db(transaction=True)
def test_event_to_audio_endpoint_happy_path(client, dummy_tts):
    """
    Test end-to-end audio generation for dialogue events.
    
    With synchronous generation:
    1. Create events
    2. Request audio endpoint
    3. Audio is generated on-demand (first request slower, subsequent cached)
    4. Event feed includes audio URLs
    """
    # Prepare minimal location and actors with deterministic voices
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    pilot = Pilot.create(ship=None)
    controller = Controller.create(location=loc)
    sat = Satellite.create(name="NAVSAT ALPHA")

    # Create three events (one per actor type)
    now_ts = timezone.now().timestamp()
    ev_pilot = DialogueEventLog.objects.create(actor=pilot, text="PILOT TEXT", timestamp=now_ts)
    ev_ctrl = DialogueEventLog.objects.create(actor=controller, text="CTRL TEXT", timestamp=now_ts + 1)
    ev_sat = DialogueEventLog.objects.create(actor=sat, text="SAT TEXT", timestamp=now_ts + 2)

    # Request audio for each event (should generate on-demand)
    for ev_id in [ev_pilot.id, ev_ctrl.id, ev_sat.id]:
        resp = client.get(f"/api/event_audio/{ev_id}/")
        assert resp.status_code == 200, f"Failed to get audio for event {ev_id}: {resp.content}"
        
        # Verify it's a valid WAV file (mixed audio: quindars + TTS + room tone)
        assert resp["Content-Type"] == "audio/wav"
        with wave.open(io.BytesIO(resp.content), "rb") as wf:
            assert wf.getnchannels() == 1  # Mono
            assert wf.getsampwidth() == 2  # 16-bit
            assert wf.getframerate() == 48000  # 48kHz (audio mixer default)
            assert wf.getnframes() > 0  # Has audio data

    # Event feed should report audio_ready and include URLs
    feed_resp = client.get("/api/events/?limit=10&after_ts=0")
    assert feed_resp.status_code == 200, feed_resp.content
    feed = feed_resp.json()
    assert "events" in feed
    
    ready = {e["id"]: e for e in feed["events"]}
    assert ready[ev_pilot.id]["audio_ready"] is True
    assert ready[ev_ctrl.id]["audio_ready"] is True
    assert ready[ev_sat.id]["audio_ready"] is True
    assert ready[ev_pilot.id]["audio_url"]
    assert ready[ev_ctrl.id]["audio_url"]
    assert ready[ev_sat.id]["audio_url"]


@pytest.mark.django_db(transaction=True)
def test_audio_caching(client, dummy_tts):
    """
    Test that audio is cached after first generation.
    
    Second request for same event should be fast (served from cache).
    """
    from django.core.cache import cache
    
    # Clear cache
    cache.clear()
    
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    pilot = Pilot.create(ship=None)
    now_ts = timezone.now().timestamp()
    ev = DialogueEventLog.objects.create(actor=pilot, text="CACHED TEXT", timestamp=now_ts)
    
    # First request - generates and caches
    resp1 = client.get(f"/api/event_audio/{ev.id}/")
    assert resp1.status_code == 200
    
    # Verify it's in cache (mixed audio cache key)
    cache_key = f"mixed_audio:{ev.id}"
    cached = cache.get(cache_key)
    assert cached is not None
    assert len(cached) > 0
    
    # Second request - should serve from cache (dummy_tts won't be called again)
    resp2 = client.get(f"/api/event_audio/{ev.id}/")
    assert resp2.status_code == 200
    assert resp2.content == resp1.content


# -----------------------------------------------------------------------------
# Realistic TTS mock tests - use real voice WAV files
# -----------------------------------------------------------------------------

@pytest.fixture
def realistic_tts(monkeypatch):
    """Mock TTS service to return a real voice WAV file (not silence)."""
    from mysite.universe.services import tts_service
    
    real_voice_bytes = _get_real_voice_wav_bytes()
    
    class RealisticMockTTS:
        def generate(self, text: str, voice_id: str, **kwargs):
            return real_voice_bytes
    
    monkeypatch.setattr(tts_service, "_tts_service", RealisticMockTTS())
    return real_voice_bytes


@pytest.mark.django_db(transaction=True)
def test_event_audio_returns_mixed_audio_with_quindars(client, realistic_tts):
    """
    Test that event_audio endpoint returns audio with quindars.
    
    Uses a real voice WAV as TTS mock, verifies output contains:
    - Quindar start tone (2525 Hz) at beginning
    - TTS audio in middle
    - Quindar end tone (2475 Hz) at end
    """
    from django.core.cache import cache
    cache.clear()
    
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    pilot = Pilot.create(ship=None)
    
    event = DialogueEventLog.objects.create(
        actor=pilot,
        text="TEST MESSAGE FOR QUINDAR VERIFICATION",
        timestamp=timezone.now().timestamp()
    )
    
    # Get TTS duration for expected output calculation
    with wave.open(io.BytesIO(realistic_tts), "rb") as wf:
        tts_duration = wf.getnframes() / wf.getframerate()
    
    # Call endpoint
    response = client.get(f"/api/event_audio/{event.id}/")
    assert response.status_code == 200, f"Failed: {response.content[:200]}"
    assert response["Content-Type"] == "audio/wav"
    
    # Read output
    with wave.open(io.BytesIO(response.content), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.getnframes()
        out_duration = frames / sr
        raw = wf.readframes(frames)
        samples = struct.unpack(f"<{frames}h", raw)
    
    # Expected: quindar(0.25) + gap(0.05) + TTS + gap(0.05) + quindar(0.25)
    expected_min = 0.25 + 0.05 + tts_duration + 0.05 + 0.25
    assert out_duration >= expected_min * 0.9, f"Output too short: {out_duration:.2f}s < {expected_min:.2f}s"
    
    # Check quindar amplitudes
    def get_region_amp(start_sec, end_sec):
        start_i = int(start_sec * sr)
        end_i = min(int(end_sec * sr), len(samples))
        region = samples[start_i:end_i]
        return max(abs(s) for s in region) if region else 0
    
    quindar_start_amp = get_region_amp(0.0, 0.25)
    assert quindar_start_amp > 5000, f"Quindar start missing: amplitude {quindar_start_amp}"
    
    quindar_end_start = 0.30 + tts_duration + 0.05
    quindar_end_amp = get_region_amp(quindar_end_start, quindar_end_start + 0.25)
    assert quindar_end_amp > 5000, f"Quindar end missing: amplitude {quindar_end_amp}"


@pytest.mark.django_db(transaction=True)
def test_event_audio_output_duration_matches_expected(client, realistic_tts):
    """
    Test that output duration = quindar + gap + TTS + gap + quindar.
    """
    from django.core.cache import cache
    cache.clear()
    
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    controller = Controller.create(location=loc)
    
    event = DialogueEventLog.objects.create(
        actor=controller,
        text="Clearance granted",
        timestamp=timezone.now().timestamp()
    )
    
    with wave.open(io.BytesIO(realistic_tts), "rb") as wf:
        tts_duration = wf.getnframes() / wf.getframerate()
    
    response = client.get(f"/api/event_audio/{event.id}/")
    assert response.status_code == 200
    
    with wave.open(io.BytesIO(response.content), "rb") as wf:
        out_duration = wf.getnframes() / wf.getframerate()
    
    # Expected: 0.25 + 0.05 + tts + 0.05 + 0.25 = tts + 0.60
    expected = tts_duration + 0.60
    assert abs(out_duration - expected) < 0.1, f"Duration mismatch: {out_duration:.2f}s != {expected:.2f}s"
