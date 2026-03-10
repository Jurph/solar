import json
from unittest.mock import patch

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
