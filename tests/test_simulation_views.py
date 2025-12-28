import json

from django.test import TestCase
from django.urls import reverse

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.simulation import SimulationState, get_simulation_time


class TestSimulationViews(TestCase):
    def setUp(self):
        SimulationState.objects.all().delete()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.create(pk=1, anchor_sim_time=1000.0, anchor_wall_clock=0.0, time_scale=0.0)

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
        resp = self.client.post(url, data=json.dumps({"time_scale": 0}), content_type="application/json")
        assert resp.status_code == 400
        assert "must be positive" in resp.json()["message"]

    def test_set_time_scale_updates_state(self):
        url = reverse("set_time_scale")
        resp = self.client.post(url, data=json.dumps({"time_scale": 5.0}), content_type="application/json")
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
        DialogueEventLog.objects.create(
            timestamp=1500.0,
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

