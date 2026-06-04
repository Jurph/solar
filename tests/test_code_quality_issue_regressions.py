"""Regression tests for small code-quality tickets."""

import builtins
import importlib
import time

import pytest
from django.core.cache import cache
from django.test import Client

from mysite.universe.models.actor import Controller
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.simulation import SimulationState


def test_tts_service_imports_without_importing_ml_extras():
    module = importlib.import_module("mysite.universe.services.tts_service")

    assert module.get_tts_health()["status"] in {"unknown", "ok", "warning", "error"}


def test_chatterbox_constructor_reports_missing_torch(monkeypatch):
    from mysite.universe.services.tts_service import ChatterboxTTSService

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="PyTorch is required"):
        ChatterboxTTSService()


@pytest.mark.django_db
def test_event_feed_treats_stale_audio_file_as_not_ready():
    cache.clear()
    client = Client()
    sim_time = 10000.0
    SimulationState.objects.create(
        pk=1,
        anchor_sim_time=sim_time,
        anchor_wall_clock=time.time(),
        time_scale=1.0,
    )
    actor = Controller.objects.create(name="Readiness Control")
    event = DialogueEventLog.objects.create(
        timestamp=sim_time - 10.0,
        actor=actor,
        actor_name=actor.name,
        text="This stored file path is stale.",
    )
    event.audio_file.name = "rendered_audio/does-not-exist.wav"
    event.save(update_fields=["audio_file"])

    response = client.get("/api/events/")
    assert response.status_code == 200
    event_data = next(e for e in response.json()["events"] if e["id"] == event.id)
    assert event_data["audio_ready"] is False

    head_response = client.head(f"/api/event_audio/{event.id}/")
    assert head_response.status_code == 202
