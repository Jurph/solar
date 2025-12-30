"""
Integration test for end-to-end audio pipeline.

Tests the simplified synchronous audio generation:
1. Create dialogue events
2. Request audio via /api/event_audio/{id}/
3. Audio is generated on-demand if not cached
4. Event feed includes audio URLs
"""
import json
import wave
import io

import pytest
from django.test import Client
from django.utils import timezone

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.audio_profile import AudioProfile
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale


def _dummy_wav_bytes(payload: dict) -> bytes:
    """Generate a minimal valid WAV containing JSON payload as data chunk."""
    data = json.dumps(payload).encode("utf-8")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)  # 8-bit
        wf.setframerate(8000)
        wf.writeframes(data)
    return buf.getvalue()


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
    for ev_id, expected_text in [
        (ev_pilot.id, "PILOT TEXT"),
        (ev_ctrl.id, "CTRL TEXT"),
        (ev_sat.id, "SAT TEXT"),
    ]:
        resp = client.get(f"/api/event_audio/{ev_id}/")
        assert resp.status_code == 200, f"Failed to get audio for event {ev_id}: {resp.content}"
        
        # Decode WAV payload JSON back out
        with wave.open(io.BytesIO(resp.content), "rb") as wf:
            data = wf.readframes(wf.getnframes())
        payload = json.loads(data.decode("utf-8"))
        
        # Audio plan sentence-cases text; allow case-insensitive match
        assert payload["text"].lower() == expected_text.lower()
        assert payload["voice_id"] == "test_voice"

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
    
    # Verify it's in cache
    cache_key = f"tts_audio:{ev.id}"
    cached = cache.get(cache_key)
    assert cached is not None
    assert len(cached) > 0
    
    # Second request - should serve from cache (dummy_tts won't be called again)
    resp2 = client.get(f"/api/event_audio/{ev.id}/")
    assert resp2.status_code == 200
    assert resp2.content == resp1.content
