"""
High-signal tests for `spawn_mission` orchestration.

Goal: make failures actionable (diagnostic) and keep the tests deterministic:
- No sleeps
- No background-thread races
- No external LLM/network calls
"""

from dataclasses import dataclass
from typing import Any, List
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from mysite.universe.models.actor import Pilot
from mysite.universe.models.base import Location
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.ship import Ship
from mysite.universe.models.simulation import SimulationState
from mysite.universe.models.scale import Scale


@dataclass(frozen=True)
class _FakeDialogueEvent:
    timestamp: float
    actor: Any
    text: str
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


class _ImmediateThread:
    """
    Replacement for `threading.Thread` that runs the target inline on `start()`.

    This keeps the test deterministic while still exercising the production flow
    (spawn_mission -> thread.start() -> background work).
    """

    def __init__(self, *args, **kwargs):
        self._target = kwargs.get("target")
        self._args = kwargs.get("args", ())
        self._kwargs = kwargs.get("kwargs") or {}
        self.daemon = kwargs.get("daemon")

    def start(self):
        if self._target is not None:
            self._target(*self._args, **self._kwargs)


class SpawnMissionOrchestrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()

        self.origin = Location.objects.create(name="Origin", scale=Scale.STATION)
        self.destination = Location.objects.create(
            name="Destination", scale=Scale.STATION
        )

        self.ship = Ship.objects.create(name="TEST SHIP", current_location=self.origin)
        self.pilot = Pilot.create(name="Test Pilot", ship=self.ship)

        self.base_sim_time = 10_000.0
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=self.base_sim_time,
            anchor_wall_clock=0.0,
            time_scale=0.0,
        )

    def test_spawn_mission_starts_thread_and_returns_started(self):
        """
        If this fails: endpoint is miswired (wrong URL/method), or it stopped
        starting a background worker at all.
        """
        url = reverse("spawn_mission")

        with patch("mysite.universe.views.missions.threading.Thread") as thread_cls:
            thread = thread_cls.return_value
            response = self.client.post(url)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "started")

            thread_cls.assert_called_once()
            self.assertTrue(thread_cls.call_args.kwargs.get("daemon"))
            thread.start.assert_called_once()

    def test_spawn_mission_persists_events_at_sim_time_offsets(self):
        """
        If this fails: the orchestration is broken (wrong timestamp mapping,
        wrong persistence loop, wrong actor/text mapping).
        """
        url = reverse("spawn_mission")

        fake_events: List[_FakeDialogueEvent] = [
            _FakeDialogueEvent(
                timestamp=0.0, actor=self.pilot, text="Requesting clearance."
            ),
            _FakeDialogueEvent(timestamp=5.0, actor=self.pilot, text="Copy."),
        ]
        dest = self.destination

        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None

        class _FakeRouteService:
            def pick_random_destination(
                self, *, excluding, cargo_mission: bool = False
            ):
                return dest

            def plan_route(self, *, origin, destination):
                return ["NAV_EVENT"]

        class _FakeScriptService:
            def __init__(self, llm):
                self.llm = llm

            def iter_navigation_events(
                self, nav_events, ship, use_physics_delays: bool = True
            ):
                return fake_events

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch(
                "mysite.universe.services.route_server.RouteService", _FakeRouteService
            ),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                _FakeScriptService,
            ),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)

        saved = list(DialogueEventLog.objects.order_by("timestamp"))
        self.assertEqual(len(saved), len(fake_events))
        self.assertEqual(saved[0].timestamp, self.base_sim_time + 0.0)
        self.assertEqual(saved[0].actor_name, self.pilot.name)
        self.assertEqual(saved[0].text, "Requesting clearance.")
        self.assertEqual(saved[1].timestamp, self.base_sim_time + 5.0)
        self.assertEqual(saved[1].actor_name, self.pilot.name)
        self.assertEqual(saved[1].text, "Copy.")

    def test_spawn_mission_aborts_when_route_is_empty(self):
        """
        If this fails: spawn_mission might be persisting partial/garbage missions.
        """
        url = reverse("spawn_mission")

        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None

        class _FakeRouteService:
            def pick_random_destination(
                self, *, excluding, cargo_mission: bool = False
            ):
                return self.destination

            def plan_route(self, *, origin, destination):
                return []

        class _FakeScriptService:
            def __init__(self, llm):
                self.llm = llm

            def iter_navigation_events(
                self, nav_events, ship, use_physics_delays: bool = True
            ):
                raise AssertionError("Should not be called when route is empty")

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch(
                "mysite.universe.services.route_server.RouteService", _FakeRouteService
            ),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                _FakeScriptService,
            ),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)

        self.assertEqual(DialogueEventLog.objects.count(), 0)

    def test_spawn_mission_handles_no_destination_gracefully(self):
        """
        If this fails: spawn_mission exceptions are escaping the background worker.
        """
        url = reverse("spawn_mission")

        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None

        class _FakeRouteService:
            def pick_random_destination(
                self, *, excluding, cargo_mission: bool = False
            ):
                raise ValueError("No destinations")

            def plan_route(self, *, origin, destination):
                raise AssertionError(
                    "Should not be called when destination selection fails"
                )

        class _FakeScriptService:
            def __init__(self, llm):
                self.llm = llm

            def iter_navigation_events(
                self, nav_events, ship, use_physics_delays: bool = True
            ):
                raise AssertionError(
                    "Should not be called when destination selection fails"
                )

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch(
                "mysite.universe.services.route_server.RouteService", _FakeRouteService
            ),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                _FakeScriptService,
            ),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)

        self.assertEqual(DialogueEventLog.objects.count(), 0)


class SpawnMissionEdgeCaseTests(TestCase):
    """Cover uncovered branches in spawn_mission (lines 60, 83-85, 241-242, 281-282, 310-311)."""

    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()

        self.origin = Location.objects.create(name="Origin", scale=Scale.STATION)
        self.destination = Location.objects.create(
            name="Destination", scale=Scale.STATION
        )
        self.ship = Ship.objects.create(name="EDGE SHIP", current_location=self.origin)
        self.pilot = Pilot.create(name="Edge Pilot", ship=self.ship)

        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=0.0,
            anchor_wall_clock=0.0,
            time_scale=0.0,
        )

    def test_empty_mission_type_defaults_to_cargo_path(self):
        """POST with mission_type='' falls through else branch (line 60) → cargo path."""
        url = reverse("spawn_mission")
        dest = self.destination

        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None

        class _FakeRouteService:
            def pick_random_destination(self, *, excluding, cargo_mission=False):
                return dest

            def plan_route(self, *, origin, destination):
                return ["NAV_EVENT"]

        cargo_path_called = []

        class _FakeScriptService:
            def __init__(self, llm):
                cargo_path_called.append(True)

            def iter_navigation_events(self, nav_events, ship, use_physics_delays=True):
                return []

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch(
                "mysite.universe.services.route_server.RouteService", _FakeRouteService
            ),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                _FakeScriptService,
            ),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url, {"mission_type": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            cargo_path_called, "cargo ScriptService should have been instantiated"
        )

    def test_empty_route_aborts_without_saving_events(self):
        """plan_route returns [] → lines 241-242 log error and return; no events saved."""
        url = reverse("spawn_mission")
        dest = self.destination

        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None

        class _FakeRouteService:
            def pick_random_destination(self, *, excluding, cargo_mission=False):
                return dest

            def plan_route(self, *, origin, destination):
                return []

        class _FakeScriptService:
            def __init__(self, llm):
                pass

            def iter_navigation_events(self, nav_events, ship, use_physics_delays=True):
                raise AssertionError("Should not be called when route is empty")

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch(
                "mysite.universe.services.route_server.RouteService", _FakeRouteService
            ),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                _FakeScriptService,
            ),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DialogueEventLog.objects.count(), 0)

    def test_zero_dialogue_events_aborts_without_saving(self):
        """iter_navigation_events yields nothing → lines 281-282 log error; no events saved."""
        url = reverse("spawn_mission")
        dest = self.destination

        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None

        class _FakeRouteService:
            def pick_random_destination(self, *, excluding, cargo_mission=False):
                return dest

            def plan_route(self, *, origin, destination):
                return ["NAV_EVENT"]

        class _FakeScriptService:
            def __init__(self, llm):
                pass

            def iter_navigation_events(self, nav_events, ship, use_physics_delays=True):
                return iter([])  # yields nothing

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch(
                "mysite.universe.services.route_server.RouteService", _FakeRouteService
            ),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                _FakeScriptService,
            ),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DialogueEventLog.objects.count(), 0)

    def test_spawn_mission_returns_500_when_thread_start_raises(self):
        """threading.Thread.start() raises → lines 310-311: 500 response with error status."""
        url = reverse("spawn_mission")

        with patch("mysite.universe.views.missions.threading.Thread") as thread_cls:
            thread_cls.return_value.start.side_effect = RuntimeError(
                "thread start failed"
            )
            response = self.client.post(url)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["status"], "error")
        self.assertIn("Failed to spawn mission", response.json()["message"])

    def test_nav_broadcast_unknown_satellite_name_logs_error_and_exits(self):
        """satellite_name given but not found → lines 83-85: thread exits, no events saved."""
        url = reverse("spawn_mission")

        with patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread):
            response = self.client.post(
                url,
                {"mission_type": "nav_broadcast", "satellite_name": "DOES_NOT_EXIST"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DialogueEventLog.objects.count(), 0)


class RunDemoTests(TestCase):
    """Cover views/missions.py run_demo endpoint (lines 326-338)."""

    def setUp(self):
        self.client = Client()

    def test_run_demo_starts_thread_and_returns_started(self):
        """POST /api/run-demo/ starts a background thread and returns status=started."""
        url = reverse("run_demo")

        with patch("mysite.universe.views.missions.threading.Thread") as thread_cls:
            response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "started")
        thread_cls.assert_called_once()
        thread_cls.return_value.start.assert_called_once()

    def test_run_demo_calls_character_dialogue_demo_command(self):
        """run_demo background thread invokes the management command with correct args."""
        url = reverse("run_demo")

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.views.missions.call_command") as mock_cmd,
        ):
            response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        mock_cmd.assert_called_once_with(
            "character_dialogue_demo", temperature=0.25, use_json=True
        )

    def test_run_demo_get_request_rejected(self):
        """run_demo only accepts POST; GET should return 405."""
        url = reverse("run_demo")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
