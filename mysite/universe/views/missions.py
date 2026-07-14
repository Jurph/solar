"""
Views for mission spawning and orchestration.

Contains:
- spawn_mission: Create a complete mission (ship, pilot, cargo, route, dialogue)

Future additions:
- spawn_anomaly: Inject anomaly events
- spawn_chatter: Trigger small talk between ships
- Mission type parameter for unified spawning
"""

import logging
import threading
import time

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.db import transaction

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.views.dev_guard import state_changing_dev_only

logger = logging.getLogger(__name__)

# spawn_mission returns 200 before its background thread runs, so background
# failures are recorded here for health_check to surface to pollers.
SPAWN_FAILURE_CACHE_KEY = "spawn_mission:last_error"


@state_changing_dev_only
@require_http_methods(["POST"])
def spawn_mission(request):
    """
    API endpoint to spawn a complete mission: ship, pilot, cargo, route, and dialogue.

    Creates a new ship with pilot and cargo, picks a random destination,
    plans the route, generates dialogue events with physics-based timing,
    and schedules them for display based on simulation time.

    Query parameters:
        mission_type: (optional str) Mission type - "cargo" (default) or "nav_broadcast"
        satellite_name: (optional str) For nav_broadcast missions, specific satellite name

    Events are saved directly to DialogueEventLog with timestamps in simulation
    time. They will appear in the event feed when simulation time reaches them.

    Returns:
        JSON with status and message indicating mission processing has started
    """
    # Import here to avoid circular imports
    from mysite.universe.models.ship import Ship
    from mysite.universe.models.actor import Pilot, Satellite
    from mysite.universe.services.route_server import RouteService
    from mysite.universe.services.script_server import ScriptService
    from mysite.universe.services.llm_service import LLMService
    from mysite.universe.models.simulation import get_simulation_time

    # Get mission type from query parameters (capture before thread)
    # Support both GET (query params) and POST (form data) for flexibility
    mission_type = request.GET.get("mission_type") or request.POST.get(
        "mission_type", "cargo"
    )
    if mission_type:
        mission_type = mission_type.lower()
    else:
        mission_type = "cargo"
    satellite_name = request.GET.get("satellite_name") or request.POST.get(
        "satellite_name"
    )

    def process_mission_in_background():
        """Process the mission in a background thread to avoid blocking the request."""
        try:
            logger.info(f"spawn_mission: Starting {mission_type} mission generation...")

            base_sim_time = get_simulation_time()

            if mission_type == "nav_broadcast":
                # Nav broadcast mission: generate broadcast from satellite(s)
                script_service = ScriptService.get_instance()

                import random
                from mysite.universe.services.location_service import (
                    find_star_system_for_location,
                )
                from mysite.universe.services.nav_slots import (
                    next_hour_boundary,
                    release_nav_broadcast_slots,
                    reserve_nav_broadcast_slots,
                )

                # Get satellite to broadcast from
                if satellite_name:
                    try:
                        satellite = Satellite.objects.get(name=satellite_name)
                        satellites = [satellite]
                    except Satellite.DoesNotExist:
                        logger.error(
                            f"spawn_mission: Satellite '{satellite_name}' not found"
                        )
                        return
                    target_system = (
                        find_star_system_for_location(satellite.location)
                        if getattr(satellite, "location", None) is not None
                        else None
                    )
                else:
                    # NavSats epic:
                    # - Choose a *random* star system that currently has ships in it
                    # - Ensure a NavSat exists for that system (create if missing)
                    # - Schedule 14 broadcasts, 12h apart, exactly on the hour,
                    #   avoiding collisions with other satellites' nav broadcasts.
                    from mysite.universe.models.celestial import StarSystem

                    # 1) Choose a star system that has ships active in it.
                    ships = list(Ship.objects.select_related("current_location").all())
                    systems_with_ships = []
                    seen_ids = set()
                    for ship in ships:
                        if not ship.current_location:
                            continue
                        system = find_star_system_for_location(ship.current_location)
                        if system and system.id not in seen_ids:
                            seen_ids.add(system.id)
                            systems_with_ships.append(system)

                    if systems_with_ships:
                        target_system = random.choice(systems_with_ships)
                    else:
                        # Fallback: if we can't derive a system from ship locations, pick any system.
                        all_systems = list(StarSystem.objects.all())
                        if all_systems:
                            target_system = random.choice(all_systems)
                        else:
                            # Minimal-DB fallback: allow nav broadcasts even with no imported universe.
                            logger.warning(
                                "spawn_mission: No star systems found; creating a generic navigation satellite"
                            )
                            satellite = Satellite.create(name="Navigation Satellite")
                            satellites = [satellite]
                            target_system = None

                    # 2) Choose or create a navigation satellite for that system.
                    if target_system is not None:
                        nav_sats = list(
                            Satellite.objects.filter(location=target_system)
                        )
                        if nav_sats:
                            satellite = random.choice(nav_sats)
                        else:
                            satellite = Satellite.create_navigation_satellite(
                                location=target_system
                            )
                            logger.info(
                                f"spawn_mission: Created navigation satellite '{satellite.name}' for {target_system.name}"
                            )
                        satellites = [satellite]

                # 3) Reserve on-the-hour time slots not already used by another
                #    NavSat broadcast. Broadcast cadence: 14 updates, 12 hours apart.
                #    Reserving slots as rows under a uniqueness constraint before
                #    generating dialogue closes the check-to-use race with
                #    concurrent nav broadcast missions (issue #39).
                hours = 3600.0
                cadence = 12.0 * hours
                count = 14

                reserved_slots = reserve_nav_broadcast_slots(
                    base_sim_time,
                    count=count,
                    cadence_s=cadence,
                    satellite_name=satellites[0].name,
                )
                if reserved_slots is not None:
                    start_time = reserved_slots[0]
                else:
                    # If the next 24 hourly slots are all blocked, fall back to the
                    # earliest hour boundary and accept collisions (extremely rare).
                    start_time = next_hour_boundary(base_sim_time)
                    logger.warning(
                        "spawn_mission: all hourly nav broadcast slots occupied; "
                        f"accepting collisions from {start_time}"
                    )

                # 4) Generate and persist all scheduled broadcasts (and optional
                #    gratitude replies). If anything fails, release the reserved
                #    slots so an abandoned reservation cannot block the schedule.
                events_saved = 0
                try:
                    with transaction.atomic():
                        for i in range(count):
                            broadcast_timestamp = start_time + (i * cadence)
                            broadcast_chain = (
                                script_service.generate_nav_broadcast_chain(
                                    satellite=satellites[0],
                                    base_timestamp=broadcast_timestamp,
                                )
                            )
                            for event in broadcast_chain:
                                # Long-term: allow the last scheduled NavSat broadcast to
                                # carry a "next cycle" marker so a future scheduler can
                                # re-enqueue another NavSat mission on the same per-hour
                                # cadence without having to re-derive the schedule.
                                if (
                                    i == count - 1
                                    and event.metadata
                                    and event.metadata.get("type") == "nav_broadcast"
                                ):
                                    event.metadata["navsat_next_cycle_anchor_ts"] = (
                                        start_time + (count * cadence)
                                    )
                                    event.metadata["navsat_cycle_count"] = count
                                    event.metadata["navsat_cycle_cadence_hours"] = (
                                        cadence / hours
                                    )
                                    event.metadata["navsat_cycle_anchor_ts"] = (
                                        start_time
                                    )
                                    if target_system is not None:
                                        event.metadata["navsat_star_system_name"] = (
                                            target_system.name
                                        )
                                        event.metadata["navsat_star_system_id"] = (
                                            target_system.id
                                        )
                                # CRITICAL: every dialogue event must carry a persisted
                                # actor. A missing actor is a script-service bug; abort
                                # the mission so the transaction rolls back instead of
                                # persisting a partial broadcast schedule.
                                actor = getattr(event, "actor", None)
                                if actor is None or not hasattr(actor, "id"):
                                    raise ValueError(
                                        f"Nav broadcast event at t={event.timestamp} has "
                                        f"no persisted actor (got {type(actor).__name__});"
                                        " aborting mission."
                                    )
                                # Store actor_id in metadata - never use name lookups
                                metadata = (
                                    dict(event.metadata) if event.metadata else {}
                                )
                                metadata["actor_id"] = actor.id

                                DialogueEventLog.objects.create(
                                    timestamp=event.timestamp,
                                    actor=actor,
                                    actor_name=actor.name,
                                    text=event.text,
                                    metadata=metadata,
                                )
                                events_saved += 1
                except Exception:
                    if reserved_slots:
                        released = release_nav_broadcast_slots(reserved_slots)
                        logger.info(
                            f"spawn_mission: released {released} reserved nav "
                            "broadcast slot(s) after mission failure"
                        )
                    raise

                logger.info(
                    f"spawn_mission: Generated {events_saved} nav broadcast event(s) "
                    f"({count} broadcasts scheduled)"
                )

            else:
                with transaction.atomic():
                    # Cargo mission (default): ship, pilot, route, dialogue
                    # Create ship and pilot (controllers should already exist from XML import)
                    ship = Ship.create()
                    logger.info(
                        f"spawn_mission: Created ship {ship.name} at {ship.current_location.name}"
                    )

                    pilot = Pilot.create(ship=ship)
                    logger.debug(f"spawn_mission: Created pilot {pilot.name}")

                    # Pick a random destination (different from origin)
                    # For cargo missions, only valid endpoints (planets, moons, stations with berths)
                    route_service = RouteService()
                    destination = route_service.pick_random_destination(
                        excluding=ship.current_location, cargo_mission=True
                    )
                    logger.info(f"spawn_mission: Destination {destination.name}")

                    # Plan the route
                    route_events = route_service.plan_route(
                        origin=ship.current_location, destination=destination
                    )

                    if not route_events:
                        raise ValueError(
                            f"spawn_mission: route planning returned no events for "
                            f"{ship.name} -> {destination.name}; rolling back mission."
                        )

                    logger.debug(
                        f"spawn_mission: Planned route with {len(route_events)} navigation events"
                    )

                    # Initialize LLM with low temperature for consistent dialogue
                    llm = LLMService(quiet_mode=True)
                    llm.temperature = 0.25

                    # Create a fresh ScriptService instance for this mission
                    script_service = ScriptService(llm=llm)

                    # Generate dialogue events from navigation events
                    # Use physics_delays=True for realistic timing between maneuvers
                    logger.debug(
                        "spawn_mission: Generating dialogue events with physics delays..."
                    )

                    dialogue_events_iter = script_service.iter_navigation_events(
                        route_events, ship, use_physics_delays=True
                    )

                    # Save events directly to DialogueEventLog as they are generated.
                    # Each yielded event.timestamp is mission-relative (0.0, 45.0, 2700.0, etc.)
                    # We add base_sim_time to schedule them in absolute simulation time.
                    events_saved = 0
                    last_relative_timestamp = 0.0
                    for event in dialogue_events_iter:
                        scheduled_time = base_sim_time + event.timestamp

                        # Every dialogue event must carry an actor; abort (and roll
                        # back) rather than persist an actor-less event, which the
                        # model-level guard would reject anyway.
                        actor = getattr(event, "actor", None)
                        if actor is None:
                            raise ValueError(
                                f"Dialogue event at t={event.timestamp} has no actor;"
                                " aborting mission."
                            )

                        # Store event with actor ForeignKey reference
                        DialogueEventLog.objects.create(
                            timestamp=scheduled_time,
                            actor=actor,
                            actor_name=actor.name,
                            text=event.text,
                            metadata=dict(event.metadata) if event.metadata else {},
                        )
                        events_saved += 1
                        last_relative_timestamp = event.timestamp

                    if events_saved == 0:
                        raise ValueError(
                            f"spawn_mission: no dialogue events generated for "
                            f"{ship.name}; rolling back mission."
                        )

                    logger.debug(
                        f"spawn_mission: Generated {events_saved} dialogue events"
                    )

                    # Calculate mission duration for logging (in mission-relative seconds)
                    mission_duration = last_relative_timestamp
                    hours = int(mission_duration // 3600)
                    minutes = int((mission_duration % 3600) // 60)
                    seconds = int(mission_duration % 60)
                    duration_str = f"{hours}h {minutes}m {seconds}s"

                    logger.info(
                        f"spawn_mission: {ship.name} from {ship.current_location.name} "
                        f"to {destination.name}, {events_saved} events spanning {duration_str}"
                    )

            # Mission completed; clear any stale failure marker.
            cache.delete(SPAWN_FAILURE_CACHE_KEY)

        except Exception as e:
            logger.exception(f"spawn_mission: Error - {e}")
            # The HTTP response already reported "started", so record the
            # failure where health_check can surface it to pollers.
            cache.set(
                SPAWN_FAILURE_CACHE_KEY,
                {
                    "mission_type": mission_type,
                    "error": str(e),
                    "wall_clock": time.time(),
                },
                timeout=600,
            )

    try:
        # Start mission processing in background thread
        thread = threading.Thread(target=process_mission_in_background, daemon=True)
        thread.start()

        return JsonResponse(
            {
                "status": "started",
                "message": "Mission spawned and processing in background",
            }
        )
    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": f"Failed to spawn mission: {str(e)}"},
            status=500,
        )
