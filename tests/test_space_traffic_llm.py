import pytest
import os
import time
from django.conf import settings

from mysite.universe.management.commands.start_simulation_loop import SimulationQueue, DIALOGUE_EVENTS_RECEIVED, DIALOGUE_EVENTS_RECEIVED_LOCK
from mysite.universe.services.script_server import ScriptService
from mysite.universe.services.route_server import RouteService
from mysite.universe.models.actor import Pilot, Controller 
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.import_xml import UniverseImporter


@pytest.fixture
def simulation_queue(db):
    """Fixture to provide a simulation queue."""
    return SimulationQueue()

@pytest.fixture
def script_service():
    """Fixture to provide a configured ScriptService with quiet LLM."""
    # Create a ScriptService with a quiet LLM using unified LLMService
    from mysite.universe.services.llm_service import LLMService
    quiet_llm = LLMService(quiet_mode=True)
    return ScriptService(llm=quiet_llm)

@pytest.fixture
def test_universe(db):
    """
    Loads test universe data from test_universe.xml using UniverseImporter.

    Expects the following test data:
    - Two Locations: "Mars" and "Earth".
    - Generates one random Pilot actor using the production procedural method.
    - Generates one random Ship using the production procedural method, with its current_location set to Mars.
    """
    xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
    importer = UniverseImporter(xml_file)
    importer.import_universe()

    mars = Location.objects.get(name="Mars")
    earth = Location.objects.get(name="Earth")
    # Generate support data exactly as in your existing tests:
    ship = Ship.create() 
    pilot = Pilot.create(ship=ship)       
    controller = Controller.create()
    return {"mars": mars, "earth": earth, "pilot": pilot, "ship": ship, "controller": controller}

@pytest.mark.slow
def test_script_service_generates_dialogue_events(script_service, test_universe, request):
    """
    Integration smoke test: Verifies ScriptService can convert navigation events to dialogue events.
    
    This test exercises the full pipeline:
    - Route planning (NavigationEvents)
    - Dialogue chain generation (DialogueEvents)
    - Basic structural validation
    
    NOTE: This test calls the LLM and typically takes 40-90 seconds.
    Marked as slow - skip with: pytest -m "not slow"
    
    In verbose mode (-v), shows generated dialogue lines.
    In very verbose mode (-vv), shows additional timing details.
    """
    start_time = time.time()
    
    route_service = RouteService()
    route = route_service.plan_route(origin=test_universe["mars"], destination=test_universe["earth"])
    
    if not isinstance(route, list):
        route_events = route.events
    else:
        route_events = route
    
    nav_event_count = len(route_events)
    
    # Process navigation events to generate dialogue events
    script_events = script_service.parse_navigation_events(route_events, test_universe["ship"])
    
    elapsed_time = time.time() - start_time
    
    # Basic structural validation only
    assert len(script_events) > 0, "Should generate at least one dialogue event."
    for event in script_events:
        assert hasattr(event, 'timestamp'), "Dialogue event should have timestamp."
        assert hasattr(event, 'text'), "Dialogue event should have text."
        assert hasattr(event, 'actor'), "Dialogue event should have actor."
        assert event.text, "Dialogue event text should not be empty."
    
    # Verbose output: show dialogue lines
    verbosity = getattr(request.config.option, 'verbose', 0)
    if verbosity >= 1:
        print(f"\n=== Generated Dialogue ({len(script_events)} events from {nav_event_count} nav events) ===")
        for i, event in enumerate(script_events, 1):
            actor_name = event.actor.name if hasattr(event.actor, 'name') else str(event.actor)
            print(f"{i:2d}. [{actor_name:20s}] {event.text}")
        print()
    
    # Very verbose output: show timing details
    if verbosity >= 2:
        avg_time_per_event = elapsed_time / len(script_events) if script_events else 0
        print(f"Timing: {elapsed_time:.1f}s total, {avg_time_per_event:.2f}s per dialogue event")
        print(f"Navigation events: {nav_event_count}, Dialogue events: {len(script_events)}")
        print()


@pytest.mark.slow
def test_simulation_queue_processes_dialogue_events(simulation_queue, script_service, test_universe):
    """
    Integration smoke test: Verifies SimulationQueue can process dialogue events.
    
    NOTE: This test calls the LLM and typically takes 40-90 seconds.
    Marked as slow - skip with: pytest -m "not slow"
    """
    route_service = RouteService()
    route = route_service.plan_route(origin=test_universe["mars"], destination=test_universe["earth"])
    
    if not isinstance(route, list):
        route_events = route.events
    else:
        route_events = route
    
    script_events = script_service.parse_navigation_events(route_events, test_universe["ship"])
    
    # Clear the global dialogue events list
    with DIALOGUE_EVENTS_RECEIVED_LOCK:
        DIALOGUE_EVENTS_RECEIVED.clear()
    
    # Add each script event to the queue
    for event in script_events:
        simulation_queue.add_event(event)
    
    # Process events up to just after the first event's timestamp
    if script_events:
        simulation_queue.process_due_events(script_events[0].timestamp + 360)
        
        # Verify that dialogue events were processed
        with DIALOGUE_EVENTS_RECEIVED_LOCK:
            assert len(DIALOGUE_EVENTS_RECEIVED) > 0, \
                f"Expected dialogue events to be processed, got {len(DIALOGUE_EVENTS_RECEIVED)}."
