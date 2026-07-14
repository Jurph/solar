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

from mysite.universe.models.actor import Pilot, Satellite
from mysite.universe.models.base import Location
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.ship import Ship
from mysite.universe.models.simulation import SimulationState
from mysite.universe.models.scale import Scale

# Import before route-service monkeypatches below so script_server keeps a real
# RouteService binding for later tests in the same process.
import mysite.universe.services.script_server  # noqa: F401


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
        If this fails: spawn_mission might be persisting a mission whose route
        service could not construct any executable navigation events.
        """
        url = reverse("spawn_mission")
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

    def test_spawn_mission_rolls_back_partial_cargo_mission_on_generation_error(self):
        """A mid-stream dialogue crash must not leave a partial mission in the DB."""
        url = reverse("spawn_mission")
        origin = self.origin
        dest = self.destination
        real_pilot_create = Pilot.create

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
                self.llm = llm

            def iter_navigation_events(self, nav_events, ship, use_physics_delays=True):
                yield _FakeDialogueEvent(
                    timestamp=0.0,
                    actor=ship.pilot,
                    text="This should roll back.",
                )
                raise RuntimeError("LLM crashed mid-mission")

        def create_ship():
            return Ship.objects.create(
                name="ROLLBACK SHIP",
                current_location=origin,
            )

        def create_pilot(*, ship):
            return real_pilot_create(name="Rollback Pilot", ship=ship)

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", side_effect=create_ship),
            patch(
                "mysite.universe.models.actor.Pilot.create", side_effect=create_pilot
            ),
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
        self.assertFalse(Ship.objects.filter(name="ROLLBACK SHIP").exists())
        self.assertFalse(Pilot.objects.filter(name="Rollback Pilot").exists())
        self.assertFalse(
            DialogueEventLog.objects.filter(text="This should roll back.").exists()
        )


class SpawnMissionEdgeCaseTests(TestCase):
    """Edge behavior that protects the HTTP-to-background orchestration boundary."""

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

    def test_empty_mission_type_defaults_to_persisted_cargo_mission(self):
        """Blank mission_type is normalized to the cargo mission behavior."""
        url = reverse("spawn_mission")
        dest = self.destination
        fake_events = [
            _FakeDialogueEvent(
                timestamp=2.5,
                actor=self.pilot,
                text="Default cargo path persisted this event.",
            )
        ]

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
                self.llm = llm

            def iter_navigation_events(self, nav_events, ship, use_physics_delays=True):
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
            response = self.client.post(url, {"mission_type": ""})

        self.assertEqual(response.status_code, 200)
        saved = DialogueEventLog.objects.get()
        self.assertEqual(saved.actor, self.pilot)
        self.assertEqual(saved.text, "Default cargo path persisted this event.")

    def test_zero_dialogue_events_rolls_back_and_records_failure(self):
        """A non-empty route that produces no dialogue is a failed mission."""
        from django.core.cache import cache

        from mysite.universe.views.missions import SPAWN_FAILURE_CACHE_KEY

        url = reverse("spawn_mission")
        origin = self.origin
        dest = self.destination
        real_pilot_create = Pilot.create

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
                self.llm = llm

            def iter_navigation_events(self, nav_events, ship, use_physics_delays=True):
                return iter([])

        def create_ship():
            return Ship.objects.create(name="ZERO EVENT SHIP", current_location=origin)

        def create_pilot(*, ship):
            return real_pilot_create(name="Zero Event Pilot", ship=ship)

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", side_effect=create_ship),
            patch(
                "mysite.universe.models.actor.Pilot.create", side_effect=create_pilot
            ),
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
        self.assertFalse(Ship.objects.filter(name="ZERO EVENT SHIP").exists())
        self.assertFalse(Pilot.objects.filter(name="Zero Event Pilot").exists())
        self.assertEqual(DialogueEventLog.objects.count(), 0)
        failure = cache.get(SPAWN_FAILURE_CACHE_KEY)
        self.assertIsNotNone(failure, "zero-dialogue mission failure must be recorded")
        self.assertEqual(failure["mission_type"], "cargo")
        self.assertIn("no dialogue events generated", failure["error"])

    def test_spawn_mission_returns_500_when_thread_start_raises(self):
        """Thread startup failures are reported synchronously to the caller."""
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
        """Unknown explicit NavSat names do not create partial broadcast events."""
        url = reverse("spawn_mission")

        with patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread):
            response = self.client.post(
                url,
                {"mission_type": "nav_broadcast", "satellite_name": "DOES_NOT_EXIST"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DialogueEventLog.objects.count(), 0)


class DialogueEventLogActorConstraintTests(TestCase):
    """
    The actor FK on DialogueEventLog must always be set at creation time.

    If these fail: the save() guard was removed or weakened, meaning actor-less
    events can silently enter the DB and cause 400 loops in the event scroller.
    """

    def setUp(self):
        self.location = Location.objects.create(name="Test Loc", scale=Scale.STATION)
        self.satellite = Satellite.objects.create(name="Test Navsat")

    def test_create_without_actor_raises(self):
        """DialogueEventLog.objects.create() without actor= must raise ValueError."""
        with self.assertRaises(ValueError):
            DialogueEventLog.objects.create(
                timestamp=0.0,
                actor_name="Ghost",
                text="This should never reach the DB.",
            )

    def test_create_with_actor_succeeds(self):
        """DialogueEventLog.objects.create() with a valid actor must succeed."""
        event = DialogueEventLog.objects.create(
            timestamp=0.0,
            actor=self.satellite,
            actor_name=self.satellite.name,
            text="Sol System Navsat with a navigation update.",
        )
        self.assertIsNotNone(event.pk)
        self.assertEqual(event.actor, self.satellite)

    def test_existing_record_set_null_on_actor_delete_is_allowed(self):
        """
        SET_NULL on actor deletion is the only legitimate path to actor=None.
        Verify that deleting the actor NULLs the FK without deleting the event.
        """
        event = DialogueEventLog.objects.create(
            timestamp=0.0,
            actor=self.satellite,
            actor_name=self.satellite.name,
            text="Broadcast from a satellite that will be deleted.",
        )
        pk = event.pk
        self.satellite.delete()
        event.refresh_from_db()
        self.assertEqual(event.pk, pk)  # event still exists
        self.assertIsNone(event.actor)  # FK nulled by SET_NULL, not our guard


class NavBroadcastPersistenceTests(TestCase):
    """
    Verify that spawn_mission's nav_broadcast path saves DialogueEventLog records
    with actor= set on every event.

    If this fails: the missions view is creating actor-less events, which causes
    400 Bad Request loops when the scroller tries to fetch audio for them.
    """

    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()

        self.satellite = Satellite.objects.create(name="Test System Navsat")
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=10_000.0,
            anchor_wall_clock=0.0,
            time_scale=0.0,
        )

    def test_nav_broadcast_events_always_have_actor_set(self):
        """
        Every DialogueEventLog created by a nav_broadcast mission must have
        actor != None.  This is the regression test for the bug where the
        missions view called DialogueEventLog.objects.create() without actor=.
        """
        url = reverse("spawn_mission")
        satellite = self.satellite

        fake_events = [
            _FakeDialogueEvent(
                timestamp=0.0,
                actor=satellite,
                text="All stations, this is TEST SYSTEM NAVSAT with a navigation update.",
                metadata={"type": "nav_broadcast", "satellite_name": satellite.name},
            ),
        ]

        class _FakeScriptService:
            @staticmethod
            def get_instance():
                return _FakeScriptService()

            def generate_nav_broadcast_chain(self, satellite, base_timestamp=0.0):
                return fake_events

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                _FakeScriptService,
            ),
        ):
            response = self.client.post(
                url,
                {"mission_type": "nav_broadcast", "satellite_name": satellite.name},
            )

        self.assertEqual(response.status_code, 200)
        saved = list(DialogueEventLog.objects.all())
        self.assertGreater(
            len(saved), 0, "No events were saved — check nav_broadcast path"
        )
        for event in saved:
            self.assertIsNotNone(
                event.actor,
                f"Event {event.id} ('{event.text[:40]}') has actor=None — "
                "missions.py is missing actor= in DialogueEventLog.objects.create()",
            )


class SpawnMissionAtomicityTests(TestCase):
    """
    Failed missions must roll back completely and surface a failure marker.

    spawn_mission runs in a background thread and has already returned 200, so
    the only acceptable failure modes are: (a) no partial rows left behind, and
    (b) the failure recorded where health_check can report it.
    """

    def setUp(self):
        from django.core.cache import cache

        self.client = Client()
        cache.clear()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()

        self.origin = Location.objects.create(name="Origin", scale=Scale.STATION)
        self.destination = Location.objects.create(
            name="Destination", scale=Scale.STATION
        )
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=10_000.0,
            anchor_wall_clock=0.0,
            time_scale=0.0,
        )

    def test_empty_route_rolls_back_ship_and_pilot(self):
        """
        A cargo mission whose route planning fails must not leave orphan
        Ship/Pilot rows committed (regression: early `return` inside
        transaction.atomic() used to commit them).
        """
        url = reverse("spawn_mission")
        origin = self.origin
        dest = self.destination
        real_pilot_create = Pilot.create

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
                self.llm = llm

            def iter_navigation_events(self, nav_events, ship, use_physics_delays=True):
                raise AssertionError("Should not be called when route is empty")

        def create_ship():
            return Ship.objects.create(name="ORPHAN SHIP", current_location=origin)

        def create_pilot(*, ship):
            return real_pilot_create(name="Orphan Pilot", ship=ship)

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", side_effect=create_ship),
            patch(
                "mysite.universe.models.actor.Pilot.create", side_effect=create_pilot
            ),
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
        self.assertFalse(Ship.objects.filter(name="ORPHAN SHIP").exists())
        self.assertFalse(Pilot.objects.filter(name="Orphan Pilot").exists())

    def test_failed_mission_records_error_for_health_check(self):
        """A background failure must be visible via the spawn-failure cache key."""
        from django.core.cache import cache

        from mysite.universe.views.missions import SPAWN_FAILURE_CACHE_KEY

        url = reverse("spawn_mission")
        origin = self.origin
        dest = self.destination
        real_pilot_create = Pilot.create

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
                self.llm = llm

        def create_ship():
            return Ship.objects.create(name="FAILURE SHIP", current_location=origin)

        def create_pilot(*, ship):
            return real_pilot_create(name="Failure Pilot", ship=ship)

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch("mysite.universe.models.ship.Ship.create", side_effect=create_ship),
            patch(
                "mysite.universe.models.actor.Pilot.create", side_effect=create_pilot
            ),
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
        failure = cache.get(SPAWN_FAILURE_CACHE_KEY)
        self.assertIsNotNone(failure, "background failure must be recorded")
        self.assertEqual(failure["mission_type"], "cargo")
        self.assertIn("no events", failure["error"])

    def test_nav_broadcast_rolls_back_when_event_lacks_actor(self):
        """
        One actor-less event in a broadcast chain must abort the whole mission:
        no partial broadcast schedule may be committed.
        """
        url = reverse("spawn_mission")
        satellite = Satellite.objects.create(name="Atomicity Navsat")
        good = _FakeDialogueEvent(
            timestamp=0.0,
            actor=satellite,
            text="Good broadcast.",
            metadata={"type": "nav_broadcast"},
        )
        bad = _FakeDialogueEvent(
            timestamp=1.0,
            actor=None,
            text="Actor-less broadcast.",
            metadata={"type": "nav_broadcast"},
        )

        class _FakeScriptService:
            @staticmethod
            def get_instance():
                return _FakeScriptService()

            def generate_nav_broadcast_chain(self, satellite, base_timestamp=0.0):
                return [good, bad]

        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                _FakeScriptService,
            ),
        ):
            response = self.client.post(
                url,
                {"mission_type": "nav_broadcast", "satellite_name": satellite.name},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            DialogueEventLog.objects.count(),
            0,
            "actor-less event must roll back the entire broadcast schedule",
        )
