"""
Nav broadcast slot reservation (issue #39).

The nav broadcast scheduler must pick on-the-hour time slots that no other
satellite's broadcast cadence already uses. Scanning existing events and then
writing new ones is a TOCTOU race: two concurrent missions can scan the same
occupancy snapshot and pick the same slots, because dialogue generation holds
the gap between check and use open for seconds to minutes.

This module closes the race with a durable reservation ledger
(`NavBroadcastSlot`): the full broadcast cadence is reserved as rows under a
database uniqueness constraint *before* any dialogue is generated. Losing a
race surfaces as an `IntegrityError` on INSERT, and the loser simply moves to
the next hourly offset.
"""

import logging
import math
from typing import List, Optional

from django.db import IntegrityError, transaction

from mysite.universe.models.event import DialogueEventLog, NavBroadcastSlot

logger = logging.getLogger(__name__)

HOUR_S = 3600.0


def next_hour_boundary(sim_time: float) -> float:
    """Return the first on-the-hour simulation timestamp at or after sim_time."""
    return float(int(math.ceil(sim_time / HOUR_S) * HOUR_S))


def reserve_nav_broadcast_slots(
    base_sim_time: float,
    *,
    count: int,
    cadence_s: float,
    satellite_name: str = "",
    max_slot_offset_hours: int = 24,
) -> Optional[List[float]]:
    """
    Reserve a full broadcast cadence of on-the-hour slots.

    Tries each hourly offset from the next hour boundary. A candidate schedule
    is rejected if any of its timestamps is already claimed by an existing
    nav_broadcast event or a reservation row; the surviving candidate is then
    committed as `NavBroadcastSlot` rows in one atomic INSERT. If a concurrent
    reservation wins the same slots between the scan and the INSERT, the
    uniqueness constraint raises `IntegrityError` and the next offset is tried.

    Returns the reserved timestamps, or None if every offset within
    `max_slot_offset_hours` is taken (callers fall back to the legacy
    collision-accepting schedule).
    """
    first_candidate = next_hour_boundary(base_sim_time)

    occupied = set(
        DialogueEventLog.objects.filter(metadata__type="nav_broadcast").values_list(
            "timestamp", flat=True
        )
    )
    occupied |= set(NavBroadcastSlot.objects.values_list("timestamp", flat=True))

    for slot_offset_hours in range(max_slot_offset_hours):
        candidate = first_candidate + (slot_offset_hours * HOUR_S)
        scheduled = [candidate + (i * cadence_s) for i in range(count)]
        if any(ts in occupied for ts in scheduled):
            continue
        try:
            with transaction.atomic():
                NavBroadcastSlot.objects.bulk_create(
                    NavBroadcastSlot(timestamp=ts, satellite_name=satellite_name)
                    for ts in scheduled
                )
        except IntegrityError:
            # A concurrent mission reserved one of these slots after our scan.
            logger.info(
                "reserve_nav_broadcast_slots: lost race for slot starting at "
                f"{candidate}; trying next hourly offset"
            )
            continue
        return scheduled

    return None


def release_nav_broadcast_slots(timestamps: List[float]) -> int:
    """
    Release reserved slots after a failed mission.

    Called when dialogue generation or event persistence fails after slots were
    reserved, so abandoned reservations do not permanently block the schedule.
    Returns the number of rows released.
    """
    deleted, _ = NavBroadcastSlot.objects.filter(timestamp__in=timestamps).delete()
    return deleted
