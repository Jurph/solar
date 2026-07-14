import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from mysite.universe.models.actor import Controller
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.simulation import SimulationState, get_simulation_time


class TestSimulationViews(TestCase):
    def setUp(self):
        SimulationState.objects.all().delete()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.create(
            pk=1, anchor_sim_time=1000.0, anchor_wall_clock=0.0, time_scale=0.0
        )

    def test_get_simulation_status_shape(self):
        url = reverse("simulation_status")
        resp = self.client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert "simulation_time" in data
        assert "time_scale" in data
        assert "anchor_sim_time" in data
        assert "anchor_wall_clock" in data

    def test_set_time_scale_rejects_invalid_json(self):
        url = reverse("set_time_scale")
        resp = self.client.post(url, data="{not json", content_type="application/json")
        assert resp.status_code == 400
        assert resp.json()["status"] == "error"

    def test_set_time_scale_rejects_non_positive(self):
        url = reverse("set_time_scale")
        resp = self.client.post(
            url, data=json.dumps({"time_scale": 0}), content_type="application/json"
        )
        assert resp.status_code == 400
        assert "must be positive" in resp.json()["message"]

    def test_set_time_scale_rejects_nan(self):
        url = reverse("set_time_scale")
        resp = self.client.post(
            url, data=json.dumps({"time_scale": "nan"}), content_type="application/json"
        )
        assert resp.status_code == 400
        assert "finite" in resp.json()["message"]

    def test_set_time_scale_rejects_infinity(self):
        url = reverse("set_time_scale")
        resp = self.client.post(
            url, data=json.dumps({"time_scale": "inf"}), content_type="application/json"
        )
        assert resp.status_code == 400
        assert "finite" in resp.json()["message"]

    def test_set_time_scale_updates_state(self):
        url = reverse("set_time_scale")
        resp = self.client.post(
            url, data=json.dumps({"time_scale": 5.0}), content_type="application/json"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["time_scale"] == 5.0

    def test_skip_to_next_event_no_events(self):
        url = reverse("skip_to_next_event")
        before = get_simulation_time()
        resp = self.client.post(url, data=b"{}", content_type="application/json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "no_events"
        assert data["simulation_time"] == before

    def test_skip_to_next_event_advances_to_next_pending_event(self):
        # Add a pending event in the future relative to sim time
        actor = Controller.objects.create(name="Tester")
        DialogueEventLog.objects.create(
            timestamp=1500.0,
            actor=actor,
            actor_name="Tester",
            text="Hello",
            metadata={},
        )
        url = reverse("skip_to_next_event")
        resp = self.client.post(url, data=b"{}", content_type="application/json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["simulation_time"] >= 1500.0
        assert data["next_event_actor"] == "Tester"

    def test_skip_to_next_event_wakes_audio_worker(self):
        cache.delete("audio_worker_wake")
        actor = Controller.objects.create(name="Tester")
        DialogueEventLog.objects.create(
            timestamp=1500.0,
            actor=actor,
            actor_name="Tester",
            text="Hello",
            metadata={},
        )

        resp = self.client.post(
            reverse("skip_to_next_event"), data=b"{}", content_type="application/json"
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert cache.get("audio_worker_wake") is True


class TestHealthCheckView(TestCase):
    """Tests for the GET /api/simulation/health/ endpoint.

    The health check probes localhost:11434 (Ollama LLM server), which is
    expected to be unavailable in CI.  All paths through the LLM check are
    reachable via mocking; the audio-worker section uses real DB queries.
    """

    def setUp(self):
        SimulationState.objects.all().delete()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.create(
            pk=1, anchor_sim_time=0.0, anchor_wall_clock=0.0, time_scale=0.0
        )

    def test_health_check_returns_200_json(self):
        """Endpoint always returns 200 with a JSON body."""
        url = reverse("health_check")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("llm", data)
        self.assertIn("audio_worker", data)

    def test_llm_connection_error_yields_error_status(self):
        """When localhost:11434 is unreachable the llm key reports 'error'."""
        import requests as req_module

        url = reverse("health_check")
        with patch(
            "requests.get",
            side_effect=req_module.exceptions.ConnectionError("no server"),
        ):
            resp = self.client.get(url)
        data = resp.json()
        self.assertEqual(data["llm"]["status"], "error")
        self.assertIn("Cannot connect", data["llm"]["message"])

    def test_llm_server_ok_response(self):
        """When /v1/models returns 200 the llm key reports 'ok'."""
        url = reverse("health_check")
        mock_resp = type("R", (), {"status_code": 200})()
        with patch("requests.get", return_value=mock_resp):
            resp = self.client.get(url)
        data = resp.json()
        self.assertEqual(data["llm"]["status"], "ok")

    def test_llm_server_non_200_response(self):
        """When /v1/models returns non-200 the llm key reports 'error'."""
        url = reverse("health_check")
        mock_resp = type("R", (), {"status_code": 503})()
        with patch("requests.get", return_value=mock_resp):
            resp = self.client.get(url)
        data = resp.json()
        self.assertEqual(data["llm"]["status"], "error")

    def test_audio_worker_idle_when_no_pending_events(self):
        """With no events pending audio, audio_worker status is 'idle'."""
        url = reverse("health_check")
        with patch("requests.get", side_effect=Exception("skip llm")):
            resp = self.client.get(url)
        data = resp.json()
        self.assertEqual(data["audio_worker"]["status"], "idle")

    def test_audio_worker_warning_when_pending_but_no_recent_generation(self):
        """Events needing audio but no recent generation → 'warning'."""
        # Create an event within the 1-hour lookahead window but with no audio
        actor = Controller.objects.create(name="Test Pilot")
        DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=actor,
            actor_name="Test Pilot",
            text="Testing audio worker health.",
        )
        url = reverse("health_check")
        with patch("requests.get", side_effect=Exception("skip llm")):
            resp = self.client.get(url)
        data = resp.json()
        self.assertEqual(data["audio_worker"]["status"], "warning")

    def test_audio_worker_ok_when_recent_generation(self):
        """Events with audio_rendered_at within last 2 minutes → 'ok' status (line 201)."""
        from django.utils import timezone

        actor = Controller.objects.create(name="Test Pilot")
        DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=actor,
            actor_name="Test Pilot",
            text="Audio recently generated.",
            audio_rendered_at=timezone.now(),
        )
        url = reverse("health_check")
        with patch("requests.get", side_effect=Exception("skip llm")):
            resp = self.client.get(url)
        data = resp.json()
        self.assertEqual(data["audio_worker"]["status"], "ok")

    def test_health_check_without_worker_heartbeat_reports_unknown_tts_and_vram(self):
        """No heartbeat file should surface explicit unknown statuses for worker-side state."""
        url = reverse("health_check")
        with patch("requests.get", side_effect=Exception("skip llm")):
            with patch(
                "mysite.universe.views.simulation._read_worker_heartbeat",
                return_value=None,
            ):
                resp = self.client.get(url)

        data = resp.json()
        self.assertEqual(data["tts"]["status"], "unknown")
        self.assertEqual(data["vram"]["status"], "unknown")
        self.assertIn("No worker heartbeat file", data["tts"]["message"])

    def test_health_check_with_stale_heartbeat_marks_tts_and_vram_warning(self):
        """A stale heartbeat should warn on TTS and include stale text in VRAM output."""
        url = reverse("health_check")
        heartbeat = {
            "pid": 4242,
            "wall_clock": 50.0,
            "tts": {"status": "ok", "message": "warm"},
            "vram": {"free_mb": 256, "total_mb": 8192, "device": "RTX test"},
        }
        with patch("requests.get", side_effect=Exception("skip llm")):
            with patch(
                "mysite.universe.views.simulation._read_worker_heartbeat",
                return_value=heartbeat,
            ):
                with patch(
                    "mysite.universe.views.simulation.time_module.time",
                    return_value=100.0,
                ):
                    resp = self.client.get(url)

        data = resp.json()
        self.assertEqual(data["tts"]["status"], "warning")
        self.assertIn("Heartbeat stale", data["tts"]["message"])
        self.assertEqual(data["vram"]["status"], "warning")
        self.assertIn("stale: 50s ago", data["vram"]["message"])
        self.assertEqual(data["audio_worker"]["worker_pid"], 4242)

    def test_health_check_with_heartbeat_but_no_vram_data_reports_warning(self):
        """Heartbeat without a vram block should return the explicit warning branch."""
        url = reverse("health_check")
        heartbeat = {
            "pid": 31337,
            "wall_clock": 100.0,
            "tts": {"status": "ok", "message": "ready"},
        }
        with patch("requests.get", side_effect=Exception("skip llm")):
            with patch(
                "mysite.universe.views.simulation._read_worker_heartbeat",
                return_value=heartbeat,
            ):
                with patch(
                    "mysite.universe.views.simulation.time_module.time",
                    return_value=105.0,
                ):
                    resp = self.client.get(url)

        data = resp.json()
        self.assertEqual(data["tts"]["status"], "ok")
        self.assertEqual(data["vram"]["status"], "warning")
        self.assertIn("no VRAM data", data["vram"]["message"])
        self.assertEqual(data["audio_worker"]["worker_pid"], 31337)

    def test_worker_health_endpoint_returns_200_when_idle(self):
        """Dedicated worker health endpoint should be OK when no audio is pending."""
        resp = self.client.get(reverse("worker_health_check"))

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["audio_worker"]["status"], "idle")
        self.assertIn("pipeline_delta", data["audio_worker"])

    def test_worker_health_endpoint_returns_503_when_pending_audio_stalls(self):
        """Dedicated worker health endpoint should alarm on pending unrendered audio."""
        actor = Controller.objects.create(name="Test Pilot")
        DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=actor,
            actor_name="Test Pilot",
            text="Testing audio worker health.",
        )

        resp = self.client.get(reverse("worker_health_check"))

        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["audio_worker"]["status"], "warning")


class TestReadWorkerHeartbeat(TestCase):
    def test_invalid_json_returns_none(self):
        """Malformed heartbeat JSON should be swallowed and treated as unavailable."""
        from mysite.universe.views.simulation import _read_worker_heartbeat

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
            tmp.write("{not valid json")
            heartbeat_path = tmp.name

        try:
            with patch(
                "mysite.universe.views.simulation._HEARTBEAT_PATH",
                Path(heartbeat_path),
            ):
                self.assertIsNone(_read_worker_heartbeat())
        finally:
            import os

            os.unlink(heartbeat_path)

    def test_oserror_returns_none(self):
        """Read errors should not bubble out of the health endpoint helper."""
        from mysite.universe.views.simulation import _read_worker_heartbeat

        class _FakePath:
            def exists(self):
                return True

            def read_text(self):
                raise OSError("disk offline")

        with patch("mysite.universe.views.simulation._HEARTBEAT_PATH", _FakePath()):
            self.assertIsNone(_read_worker_heartbeat())


class TestMissionSpawnerHealth(TestCase):
    """
    health_check must surface background spawn_mission failures — the HTTP
    response already reported "started" by the time the failure happens.
    """

    def setUp(self):
        cache.clear()
        SimulationState.objects.all().delete()
        SimulationState.objects.create(
            pk=1, anchor_sim_time=1000.0, anchor_wall_clock=0.0, time_scale=0.0
        )

    def test_health_reports_ok_without_recent_failure(self):
        """No recorded failure → mission_spawner status is 'ok'."""
        with patch("requests.get", side_effect=Exception("skip llm")):
            resp = self.client.get(reverse("health_check"))

        self.assertEqual(resp.json()["mission_spawner"]["status"], "ok")

    def test_health_reports_error_after_background_spawn_failure(self):
        """A recorded spawn failure must appear in the health payload."""
        from mysite.universe.views.missions import SPAWN_FAILURE_CACHE_KEY

        cache.set(
            SPAWN_FAILURE_CACHE_KEY,
            {"mission_type": "cargo", "error": "boom", "wall_clock": 0.0},
            timeout=60,
        )
        with patch("requests.get", side_effect=Exception("skip llm")):
            resp = self.client.get(reverse("health_check"))

        data = resp.json()["mission_spawner"]
        self.assertEqual(data["status"], "error")
        self.assertIn("boom", data["message"])
        self.assertIn("cargo", data["message"])
