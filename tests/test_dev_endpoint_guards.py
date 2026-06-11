from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse

from mysite.universe.models.actor import Controller
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.simulation import SimulationState


class DevEndpointGuardTests(TestCase):
    """Regression tests for destructive dev-only endpoints."""

    def test_state_changing_endpoints_are_rejected_when_disabled(self) -> None:
        """Every destructive endpoint should fail closed outside local development."""
        endpoints = [
            reverse("run_demo"),
            reverse("spawn_mission"),
            reverse("clear_events"),
            reverse("set_time_scale"),
            reverse("skip_to_next_event"),
            reverse("audio_lab_render"),
        ]

        with override_settings(ALLOW_STATE_CHANGING_DEV_ENDPOINTS=False):
            for url in endpoints:
                response = self.client.post(
                    url, data=b"{}", content_type="application/json"
                )
                self.assertEqual(response.status_code, 403, msg=url)
                data = response.json()
                self.assertEqual(data["status"], "error")
                self.assertIn("disabled outside local development", data["message"])

    def test_state_changing_endpoint_still_works_when_enabled(self) -> None:
        """The explicit flag should allow the normal dev workflow when enabled."""
        SimulationState.objects.all().delete()
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=0.0,
            anchor_wall_clock=0.0,
            time_scale=1.0,
        )

        with override_settings(ALLOW_STATE_CHANGING_DEV_ENDPOINTS=True):
            response = self.client.post(
                reverse("set_time_scale"),
                data='{"time_scale": 2.5}',
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["time_scale"], 2.5)

    def test_clear_events_still_deletes_records_when_enabled(self) -> None:
        """The guard should not interfere with the destructive dev workflow itself."""
        actor = Controller.objects.create(name="Test Controller")
        DialogueEventLog.objects.create(
            timestamp=10.0,
            actor=actor,
            actor_name=actor.name,
            text="Delete me",
            metadata={},
        )

        with override_settings(ALLOW_STATE_CHANGING_DEV_ENDPOINTS=True):
            response = self.client.post(
                reverse("clear_events"), data=b"{}", content_type="application/json"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DialogueEventLog.objects.count(), 0)
        self.assertEqual(response.json()["status"], "success")
