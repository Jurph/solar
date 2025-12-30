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
            object.__setattr__(self, 'metadata', {})


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
        self.destination = Location.objects.create(name="Destination", scale=Scale.STATION)

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
            _FakeDialogueEvent(timestamp=0.0, actor=self.pilot, text="Requesting clearance."),
            _FakeDialogueEvent(timestamp=5.0, actor=self.pilot, text="Copy."),
        ]
        dest = self.destination

        class _FakeLLM:
            def __init__(self, *args, **kwargs):
                self.temperature = None

        class _FakeRouteService:
            def pick_random_destination(self, *, excluding, cargo_mission: bool = False):
                return dest

            def plan_route(self, *, origin, destination):
                return ["NAV_EVENT"]

        class _FakeScriptService:
            def __init__(self, llm):
                self.llm = llm

            def iter_navigation_events(self, nav_events, ship, use_physics_delays: bool = True):
                return fake_events

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch("mysite.universe.services.route_server.RouteService", _FakeRouteService),
            patch("mysite.universe.services.script_server.ScriptService", _FakeScriptService),
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
            def pick_random_destination(self, *, excluding, cargo_mission: bool = False):
                return self.destination

            def plan_route(self, *, origin, destination):
                return []

        class _FakeScriptService:
            def __init__(self, llm):
                self.llm = llm

            def iter_navigation_events(self, nav_events, ship, use_physics_delays: bool = True):
                raise AssertionError("Should not be called when route is empty")

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch("mysite.universe.services.route_server.RouteService", _FakeRouteService),
            patch("mysite.universe.services.script_server.ScriptService", _FakeScriptService),
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
            def pick_random_destination(self, *, excluding, cargo_mission: bool = False):
                raise ValueError("No destinations")

            def plan_route(self, *, origin, destination):
                raise AssertionError("Should not be called when destination selection fails")

        class _FakeScriptService:
            def __init__(self, llm):
                self.llm = llm

            def iter_navigation_events(self, nav_events, ship, use_physics_delays: bool = True):
                raise AssertionError("Should not be called when destination selection fails")

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", return_value=self.ship),
            patch("mysite.universe.models.actor.Pilot.create", return_value=self.pilot),
            patch("mysite.universe.services.route_server.RouteService", _FakeRouteService),
            patch("mysite.universe.services.script_server.ScriptService", _FakeScriptService),
            patch("mysite.universe.services.llm_service.LLMService", _FakeLLM),
        ):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)

        self.assertEqual(DialogueEventLog.objects.count(), 0)

