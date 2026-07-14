"""
Regression tests for nav broadcast slot reservation (issue #39).

The old scheduler scanned existing nav_broadcast events, picked a free hourly
slot, then wrote events after a long dialogue-generation gap. Two concurrent
missions could scan the same snapshot and commit the same slots (TOCTOU race).
These tests pin the reservation-ledger fix:

1. The full cadence is reserved as rows *before* dialogue generation, so a
   second mission sees the reservation even though no events exist yet.
2. The database uniqueness constraint arbitrates true races that slip past
   the pre-scan.
3. Failed missions release their reservations (no permanently blocked slots).
"""

from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from mysite.universe.models.actor import Satellite
from mysite.universe.models.event import DialogueEventLog, NavBroadcastSlot
from mysite.universe.models.simulation import SimulationState
from mysite.universe.services.nav_slots import (
    next_hour_boundary,
    release_nav_broadcast_slots,
    reserve_nav_broadcast_slots,
)

HOUR = 3600.0
CADENCE = 12.0 * HOUR
COUNT = 14


class NextHourBoundaryTests(TestCase):
    def test_rounds_up_to_next_hour(self):
        self.assertEqual(next_hour_boundary(1.0), HOUR)
        self.assertEqual(next_hour_boundary(HOUR - 0.5), HOUR)
        self.assertEqual(next_hour_boundary(HOUR + 0.5), 2 * HOUR)

    def test_exact_hour_is_kept(self):
        self.assertEqual(next_hour_boundary(0.0), 0.0)
        self.assertEqual(next_hour_boundary(7 * HOUR), 7 * HOUR)


class SlotReservationTests(TestCase):
    def test_reserves_full_cadence_on_the_hour(self):
        scheduled = reserve_nav_broadcast_slots(
            1.0, count=COUNT, cadence_s=CADENCE, satellite_name="SOL NAVSAT"
        )
        self.assertEqual(scheduled, [HOUR + i * CADENCE for i in range(COUNT)])
        self.assertEqual(NavBroadcastSlot.objects.count(), COUNT)
        self.assertTrue(
            all(ts % HOUR == 0 for ts in scheduled),
            "every reserved slot must be exactly on the hour",
        )

    def test_second_mission_cannot_take_reserved_slots_before_events_exist(self):
        """
        The TOCTOU regression: worker A has reserved slots but written NO
        events yet (dialogue generation in progress). Worker B scheduling from
        the same base time must land on a different hourly offset.
        """
        first = reserve_nav_broadcast_slots(
            1.0, count=COUNT, cadence_s=CADENCE, satellite_name="NAVSAT A"
        )
        second = reserve_nav_broadcast_slots(
            1.0, count=COUNT, cadence_s=CADENCE, satellite_name="NAVSAT B"
        )
        self.assertIsNotNone(second)
        self.assertEqual(set(first) & set(second), set())
        self.assertEqual(second[0], first[0] + HOUR)

    def test_existing_broadcast_events_still_block_slots(self):
        """Parity with the legacy scheduler: event occupancy is respected."""
        satellite = Satellite.create(name="LEGACY NAVSAT")
        DialogueEventLog.objects.create(
            timestamp=HOUR,
            actor=satellite,
            text="Legacy broadcast.",
            metadata={"type": "nav_broadcast"},
        )
        scheduled = reserve_nav_broadcast_slots(
            1.0, count=COUNT, cadence_s=CADENCE, satellite_name="NEW NAVSAT"
        )
        self.assertEqual(scheduled[0], 2 * HOUR)

    def test_database_constraint_arbitrates_race_past_the_prescan(self):
        """
        If a competitor commits a reservation between our occupancy scan and
        our INSERT, the uniqueness constraint fires and we take the next
        offset instead of double-booking.
        """
        # Simulate the race: competitor's row lands after our scan by hiding
        # it from the pre-scan (patch the queryset used for the scan).
        NavBroadcastSlot.objects.create(timestamp=HOUR, satellite_name="RACER")

        with patch(
            "mysite.universe.services.nav_slots.NavBroadcastSlot.objects.values_list",
            return_value=[],
        ):
            scheduled = reserve_nav_broadcast_slots(
                1.0, count=COUNT, cadence_s=CADENCE, satellite_name="LOSER"
            )

        self.assertIsNotNone(scheduled)
        self.assertEqual(scheduled[0], 2 * HOUR)
        # The loser's failed attempt must not leave partial rows at offset 0.
        self.assertEqual(
            NavBroadcastSlot.objects.filter(timestamp=HOUR).count(),
            1,
            "only the racer's original reservation may exist at the hour slot",
        )

    def test_duplicate_slot_insert_raises_integrity_error(self):
        NavBroadcastSlot.objects.create(timestamp=HOUR)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NavBroadcastSlot.objects.create(timestamp=HOUR)

    def test_returns_none_when_all_offsets_are_blocked(self):
        for offset in range(24):
            NavBroadcastSlot.objects.create(timestamp=HOUR + offset * HOUR)
        scheduled = reserve_nav_broadcast_slots(
            1.0, count=1, cadence_s=CADENCE, satellite_name="BLOCKED"
        )
        self.assertIsNone(scheduled)

    def test_release_removes_only_named_slots(self):
        mine = reserve_nav_broadcast_slots(
            1.0, count=COUNT, cadence_s=CADENCE, satellite_name="MINE"
        )
        theirs = reserve_nav_broadcast_slots(
            1.0, count=COUNT, cadence_s=CADENCE, satellite_name="THEIRS"
        )
        released = release_nav_broadcast_slots(mine)
        self.assertEqual(released, COUNT)
        remaining = set(NavBroadcastSlot.objects.values_list("timestamp", flat=True))
        self.assertEqual(remaining, set(theirs))


class _ImmediateThread:
    """Run spawn_mission's background target inline for determinism."""

    def __init__(self, *args, **kwargs):
        self._target = kwargs.get("target")
        self._args = kwargs.get("args", ())
        self._kwargs = kwargs.get("kwargs") or {}
        self.daemon = kwargs.get("daemon")

    def start(self):
        if self._target is not None:
            self._target(*self._args, **self._kwargs)


class SpawnMissionSlotLifecycleTests(TestCase):
    """Reservation lifecycle through the spawn_mission nav_broadcast path."""

    def setUp(self):
        self.client = Client()
        SimulationState.objects.create(
            pk=1, anchor_sim_time=1.0, anchor_wall_clock=0.0, time_scale=0.0
        )
        self.satellite = Satellite.create(name="LIFECYCLE NAVSAT")

    def _spawn(self, script_service_cls):
        url = reverse("spawn_mission")
        with (
            patch("mysite.universe.views.missions.threading.Thread", _ImmediateThread),
            patch(
                "mysite.universe.services.script_server.ScriptService",
                script_service_cls,
            ),
        ):
            return self.client.post(
                url,
                {
                    "mission_type": "nav_broadcast",
                    "satellite_name": self.satellite.name,
                },
            )

    def test_successful_mission_keeps_reserved_slots(self):
        satellite = self.satellite

        class _FakeScriptService:
            @staticmethod
            def get_instance():
                return _FakeScriptService()

            def generate_nav_broadcast_chain(
                self, satellite=satellite, base_timestamp=0.0
            ):
                from mysite.universe.models.event import DialogueEvent

                return [
                    DialogueEvent(
                        timestamp=base_timestamp,
                        actor=satellite,
                        text="Broadcasting.",
                        metadata={"type": "nav_broadcast"},
                    )
                ]

        response = self._spawn(_FakeScriptService)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DialogueEventLog.objects.count(), COUNT)
        self.assertEqual(NavBroadcastSlot.objects.count(), COUNT)

    def test_failed_mission_releases_reserved_slots(self):
        class _FailingScriptService:
            @staticmethod
            def get_instance():
                return _FailingScriptService()

            def generate_nav_broadcast_chain(self, satellite, base_timestamp=0.0):
                raise RuntimeError("dialogue generation failed")

        response = self._spawn(_FailingScriptService)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DialogueEventLog.objects.count(), 0)
        self.assertEqual(
            NavBroadcastSlot.objects.count(),
            0,
            "abandoned reservations must be released so slots are not blocked",
        )
