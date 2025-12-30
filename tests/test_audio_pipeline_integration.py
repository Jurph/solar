import json
import wave
import io
from pathlib import Path

import pytest
from django.test import Client
from django.utils import timezone

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.audio_profile import AudioProfile
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale
from mysite.universe.services import audio_cache


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

    def generate(text: str, voice_id: str):
        return _dummy_wav_bytes({"text": text, "voice_id": voice_id})

    monkeypatch.setattr(tts_service.TTSService, "generate", staticmethod(generate))
    # also patch the service singleton getter to return an object with generate
    class DummySvc:
        def generate(self, text: str, voice_id: str):
            return generate(text, voice_id)

    monkeypatch.setattr(tts_service, "_tts_service", DummySvc())
    return generate


@pytest.fixture(autouse=True)
def _patch_sim_time(monkeypatch):
    """Make simulation time far in the future so freshly created events are included."""
    from mysite.universe.models import simulation
    from mysite.universe.views import events
    from mysite.universe.models.event import DialogueEventLog

    # Stop any existing worker (if started elsewhere)
    if getattr(events, "_audio_worker", None):
        try:
            events._audio_worker.stop()
            events._audio_worker.join(timeout=1)
        except Exception:
            pass
    events._audio_worker = None
    # Prevent background worker thread; we'll drain manually.
    monkeypatch.setattr(events.AudioWorker, "start", lambda self: None)
    monkeypatch.setattr(events, "_ensure_worker", lambda: None)

    monkeypatch.setattr(simulation, "get_simulation_time", lambda: 4e9)

    # Clear any prior events and caches for isolation
    DialogueEventLog.objects.all().delete()
    cache = events._get_audio_cache()
    queue = events._get_audio_queue()
    # Clear cache and queue
    cache._entries.clear()
    cache._order.clear()
    queue._queue.clear()
    queue._inflight.clear()


def _drain_worker_once():
    """Run one job synchronously (bypass thread scheduling)."""
    from mysite.universe.views import events

    cache = events._get_audio_cache()
    queue = events._get_audio_queue()
    job = queue.pop()
    if not job:
        return None
    # inline generate similar to AudioWorker.run but using current get_tts_service()
    from mysite.universe.services.tts_service import get_tts_service

    svc = get_tts_service()
    wav_bytes = svc.generate(text=job.text, voice_id=job.voice_id)
    import wave as _wave

    with _wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate() or 48000
        duration = frames / float(rate)
    entry = audio_cache.AudioEntry(
        event_id=job.event_id,
        voice_id=job.voice_id,
        duration_s=duration,
        wav_bytes=wav_bytes,
        created_at=timezone.now().timestamp(),
    )
    cache.put(entry)
    queue.complete(job)
    return entry


@pytest.mark.django_db(transaction=True)
def test_event_to_audio_endpoint_happy_path(client, dummy_tts):
    # Prepare minimal location and actors with deterministic voices
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    pilot = Pilot.create(ship=None)
    controller = Controller.create(location=loc)
    sat = Satellite.create(name="NAVSAT ALPHA")

    # Create three events (one per actor type)
    now_ts = timezone.now().timestamp()
    ev_pilot = DialogueEventLog.objects.create(actor_name=pilot.name, text="PILOT TEXT", timestamp=now_ts, metadata={"actor_id": pilot.id})
    ev_ctrl = DialogueEventLog.objects.create(actor_name=controller.name, text="CTRL TEXT", timestamp=now_ts + 1, metadata={"actor_id": controller.id})
    ev_sat = DialogueEventLog.objects.create(actor_name=sat.name, text="SAT TEXT", timestamp=now_ts + 2, metadata={"actor_id": sat.id})

    # Manually run worker once per job to simulate processing
    processed = []
    for _ in range(3):
        entry = _drain_worker_once()
        if entry:
            processed.append(entry.event_id)
    assert set(processed) == {ev_pilot.id, ev_ctrl.id, ev_sat.id}

    # Each event_audio endpoint should now serve bytes
    for ev_id, expected_text in [
        (ev_pilot.id, "PILOT TEXT"),
        (ev_ctrl.id, "CTRL TEXT"),
        (ev_sat.id, "SAT TEXT"),
    ]:
        resp = client.get(f"/api/event_audio/{ev_id}/")
        assert resp.status_code == 200
        # Decode WAV payload JSON back out
        with wave.open(io.BytesIO(resp.content), "rb") as wf:
            data = wf.readframes(wf.getnframes())
        payload = json.loads(data.decode("utf-8"))
        # Audio plan sentence-cases text; allow case-insensitive match
        assert payload["text"].lower() == expected_text.lower()
        assert payload["voice_id"] == "test_voice"

    # event_feed should report audio_ready and include URLs
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

