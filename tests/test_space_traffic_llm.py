import pytest
import os
from django.core.management import call_command
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

def test_route_and_script_integration_mars_to_earth(capfd, simulation_queue, script_service, test_universe):
    """
    Integration test that:
    - Uses the route_server to generate a route from Mars to Earth.
    - Processes the generated NavigationEvents via the ScriptService.
    - Prints the resulting script events to stdout.
    - Asserts that the output contains at least one expected keyword.
    """
    route_service = RouteService()
    # Generate a route from Mars (origin) to Earth (destination) using the ship from our test universe.
    route = route_service.plan_route(origin=test_universe["mars"], destination=test_universe["earth"])
    
    # If the route is not already a list of events, assume it's an object with an 'events' attribute.
    if not isinstance(route, list):
        route_events = route.events
    else:
        route_events = route

    # Process the navigation events with the ScriptService to generate dialogue events with sequential timestamps.
    script_events = script_service.parse_navigation_events(route_events, test_universe["ship"])

    # Assert that script events were generated.
    assert script_events, "Script events list is empty."

    # Combine all script events into one string for easier checking.
    script_output = "\n".join(str(event) for event in script_events)

    # Check that the combined script output contains at least one expected keyword.
    expected_keywords = ["DEORBIT", "LAND", "Mars", "Earth"]
    assert any(keyword in script_output for keyword in expected_keywords), "Generated script events do not include any expected keywords."

    # Clear the global dialogue events list
    with DIALOGUE_EVENTS_RECEIVED_LOCK:
        DIALOGUE_EVENTS_RECEIVED.clear()

    # Add each script event to the queue
    for event in script_events:
        simulation_queue.add_event(event)

    # Process events up to just after the first event's timestamp
    simulation_queue.process_due_events(script_events[0].timestamp + 360)

    # Verify that dialogue events were processed
    # Each navigation event generates a complete dialogue chain (3, 4, or 5 steps depending on chain selection)
    # Chain length varies by maneuver type and weighted selection, so we don't assert exact count
    with DIALOGUE_EVENTS_RECEIVED_LOCK:
        assert len(DIALOGUE_EVENTS_RECEIVED) > 0, f"Expected dialogue events to be processed, got {len(DIALOGUE_EVENTS_RECEIVED)}."
        # TODO: With new chain system, each nav event generates variable-length chains
        # Old expectation was 18 (6 nav events × 3 dialogue events), but chains can be 3-5 steps
        # assert len(DIALOGUE_EVENTS_RECEIVED) == 18, f"Expected 18 dialogue events to be processed, got {len(DIALOGUE_EVENTS_RECEIVED)}."
        processed_event = DIALOGUE_EVENTS_RECEIVED[0]

    # Check that the processed event's text matches the first script event's text
    assert processed_event.text == script_events[0].text, "The processed event text does not match the expected first event text."
    