import pytest
import os
from django.core.management import call_command
from django.conf import settings

from mysite.universe.management.commands.start_simulation_loop import SimulationQueue
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
    """Fixture to provide a configured ScriptService."""
    return ScriptService()

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

    # Process each navigation event with the ScriptService to generate dialogue events.
    script_events = [script_service.parse_navigation_event(event, test_universe["ship"]) for event in route_events]

    # Print the script events to stdout.
    for event in script_events:
        print(event)

    # Capture stdout output.
    captured = capfd.readouterr().out

    # Check that the output contains expected keywords (e.g., maneuvers "DEORBIT" or "LAND", or the planet names).
    expected_keywords = ["DEORBIT", "LAND", "Mars", "Earth"]
    assert any(keyword in captured for keyword in expected_keywords), "Generated script events do not include any expected keywords."