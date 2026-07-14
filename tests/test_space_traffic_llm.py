import os
import time

import pytest
from django.conf import settings

from mysite.universe.import_xml import UniverseImporter
from mysite.universe.models.actor import Controller, Pilot
from mysite.universe.models.base import Location
from mysite.universe.models.ship import Ship
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.script_server import ScriptService


@pytest.fixture
def script_service():
    """Fixture to provide a configured ScriptService with quiet LLM."""
    from mysite.universe.services.llm_service import LLMService

    quiet_llm = LLMService(quiet_mode=True)
    return ScriptService(llm=quiet_llm)


@pytest.fixture
def test_universe(db):
    """
    Load test universe data from test_universe.xml using UniverseImporter.
    """
    xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
    importer = UniverseImporter(xml_file)
    importer.import_universe()

    mars = Location.objects.get(name="Mars")
    earth = Location.objects.get(name="Earth")
    ship = Ship.create()
    pilot = Pilot.create(ship=ship)
    controller = Controller.create()
    return {
        "mars": mars,
        "earth": earth,
        "pilot": pilot,
        "ship": ship,
        "controller": controller,
    }


@pytest.mark.slow
def test_script_service_generates_dialogue_events(
    script_service, test_universe, request
):
    """
    Integration smoke test: ScriptService converts navigation events to dialogue.

    NOTE: This test calls the LLM and typically takes 40-90 seconds.
    Marked as slow - skip with: pytest -m "not slow"
    """
    start_time = time.time()

    route_service = RouteService()
    route = route_service.plan_route(
        origin=test_universe["mars"], destination=test_universe["earth"]
    )
    route_events = route.events if not isinstance(route, list) else route
    nav_event_count = len(route_events)
    script_events = script_service.parse_navigation_events(
        route_events, test_universe["ship"]
    )
    elapsed_time = time.time() - start_time

    assert len(script_events) > 0, "Should generate at least one dialogue event."
    for event in script_events:
        assert hasattr(event, "timestamp"), "Dialogue event should have timestamp."
        assert hasattr(event, "text"), "Dialogue event should have text."
        assert hasattr(event, "actor"), "Dialogue event should have actor."
        assert event.text, "Dialogue event text should not be empty."

    verbosity = getattr(request.config.option, "verbose", 0)
    if verbosity >= 1:
        print(
            f"\n=== Generated Dialogue ({len(script_events)} events from {nav_event_count} nav events) ==="
        )
        for i, event in enumerate(script_events, 1):
            actor_name = (
                event.actor.name if hasattr(event.actor, "name") else str(event.actor)
            )
            print(f"{i:2d}. [{actor_name:20s}] {event.text}")
        print()

    if verbosity >= 2:
        avg_time_per_event = elapsed_time / len(script_events) if script_events else 0
        print(
            f"Timing: {elapsed_time:.1f}s total, {avg_time_per_event:.2f}s per dialogue event"
        )
        print(
            f"Navigation events: {nav_event_count}, Dialogue events: {len(script_events)}"
        )
        print()
