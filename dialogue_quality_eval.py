#!/usr/bin/env python
"""
Standalone script for batch dialogue quality evaluation.

This script generates dialogue events multiple times with different settings
to allow empirical evaluation of model parameters (temperature, model choice, etc.).

Features:
1. Runs all events immediately without timing/queue (fast execution)
2. Runs N times as specified at command line
3. Outputs settings header for each run
4. Generates clean output suitable for scoring with external rubric

Usage:
    python dialogue_quality_eval.py --runs 25 --temperature 0.7 --model "Qwen 2.5B"
"""
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List

# Setup Django BEFORE importing any Django models
current_path = Path(__file__).resolve().parent
sys.path.insert(0, str(current_path))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

import django
django.setup()

# Now we can import Django models and services
from django.db import transaction
from django.conf import settings

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.navigation import UniverseGraph
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.script_server import ScriptService
from mysite.universe.services.llm_service import LLMService
from mysite.universe.import_xml import UniverseImporter


def ensure_controllers_exist(quiet=False):
    """Ensure that all control stations have associated Controller actors."""
    control_stations = Location.objects.filter(name__icontains="Control")
    for station in control_stations:
        controller = Controller.objects.filter(name=station.name).first()
        if not controller:
            if not quiet:
                print(f"WARNING: {station.name} controller not found, creating it...")
            controller = Controller.create(name=station.name)
            if not quiet:
                print(f"Created controller: {controller.name}")


def process_dialogue_chain(initial_event: DialogueEvent) -> List[DialogueEvent]:
    """
    Process a dialogue event.
    
    NOTE: Dialogue chains are generated COMPLETE upfront by parse_navigation_events().
    This function just wraps the event in a list for API compatibility.
    """
    return [initial_event]


def print_run_header(run_number: int, total_runs: int, temperature: float, model: str = None):
    """Print header with run settings."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model_str = f", model = {model}" if model else ""
    
    print("\n" + "="*80)
    print(f"RUN {run_number} of {total_runs}")
    print(f"Settings: {total_runs} runs, temperature = {temperature}{model_str}, run at {timestamp}")
    print("="*80 + "\n")


def print_dialogue_event(event: DialogueEvent, event_number: int):
    """Print a dialogue event in a clean format for evaluation."""
    # Extract message text if it's JSON
    message_text = event.text
    if isinstance(message_text, str) and message_text.strip().startswith('{'):
        try:
            from mysite.universe.schemas.dialogue_schema import DialogueMessage
            import json
            msg_obj = DialogueMessage(**json.loads(message_text))
            message_text = msg_obj.message
        except (json.JSONDecodeError, ValueError):
            pass  # Use raw message if JSON parsing fails
    
    # Print in format: [Event N] SPEAKER: message
    print(f"[Event {event_number}] {event.actor.name}: {message_text}")


def main():
    parser = argparse.ArgumentParser(description='Batch dialogue quality evaluation for empirical model testing')
    parser.add_argument(
        '--runs',
        type=int,
        default=25,
        help='Number of runs to execute (default: 25)',
    )
    parser.add_argument(
        '--temperature',
        type=float,
        default=0.7,
        help='Temperature setting for the LLM (0.0-1.0, default: 0.7)',
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Model name for display purposes (e.g., "Qwen 2.5B")',
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress messages (only output dialogue)',
    )
    
    args = parser.parse_args()
    
    runs = args.runs
    temperature = args.temperature
    model = args.model
    quiet = args.quiet
    
    if not quiet:
        print(f"Starting dialogue quality evaluation: {runs} runs at temperature {temperature}")
    
    # Initialize the universe if needed
    try:
        Location.objects.get(name="Earth")
    except Location.DoesNotExist:
        if not quiet:
            print("WARNING: Universe not initialized. Importing from test_universe.xml...")
        xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
        importer = UniverseImporter(xml_file)
        importer.import_universe()
        UniverseGraph.get_instance().rebuild_graph()
        if not quiet:
            print("Universe initialized successfully")

    # Create LLM service
    try:
        llm = LLMService(quiet_mode=True)  # Always quiet for batch runs
    except Exception as e:
        print(f"ERROR: Failed to initialize LLM service: {e}")
        sys.exit(1)

    llm.temperature = temperature
    script_service = ScriptService.get_instance(llm=llm)
    
    # Ensure all control stations have controllers
    ensure_controllers_exist(quiet=quiet)
    
    # Get locations (reused across runs)
    try:
        mars = Location.objects.get(name="Mars")
        earth = Location.objects.get(name="Earth")
    except Location.DoesNotExist:
        print("ERROR: Required locations not found in the database. Have you imported the universe data?")
        sys.exit(1)
    
    # Plan route once (reused across runs)
    route_service = RouteService()
    route_events = route_service.plan_route(origin=mars, destination=earth)
    
    if not route_events:
        print("ERROR: Failed to generate a route from Mars to Earth")
        sys.exit(1)
    
    if not quiet:
        print(f"Route planned with {len(route_events)} navigation events")
    
    # Run N times
    for run_num in range(1, runs + 1):
        try:
            # Print run header
            print_run_header(run_num, runs, temperature, model)
            
            # Create fresh ship and pilot for each run
            with transaction.atomic():
                ship = Ship.create(name="Stellar Horizon", location=mars)
                pilot = Pilot.create(name="Captain Rodriguez", ship=ship)
            
            # Generate initial dialogue events from navigation events
            script_events = script_service.parse_navigation_events(route_events, ship)
            
            # Insert comms check chain using the particle system
            if len(script_events) > 0:
                comms_check_position = min(3, len(script_events) - 1)
                comms_check_timestamp = script_events[comms_check_position].timestamp + 5.0
                
                # Get or create satellite (reuse if exists)
                satellite_name = "Relay Satellite Alpha"
                satellite = Satellite.objects.filter(name=satellite_name).first()
                if not satellite:
                    satellite = Satellite.create(name=satellite_name)
                
                # Generate complete comms check chain using the particle system
                comms_check_events = script_service.generate_comms_check_chain(
                    pilot=pilot,
                    satellite=satellite,
                    ship=ship,
                    base_timestamp=comms_check_timestamp,
                )
                
                # Insert the comms check events into the script events
                for i, comms_event in enumerate(comms_check_events):
                    script_events.insert(comms_check_position + 1 + i, comms_event)
            
            # All dialogue events are already complete chains
            all_dialogue_events = script_events
            event_counter = 1
            
            # Print all dialogue events for this run
            for event in all_dialogue_events:
                print_dialogue_event(event, event_counter)
                event_counter += 1
            
            # Print run separator
            print("\n" + "-"*80 + "\n")
            
        except Exception as e:
            print(f"ERROR: Error in run {run_num}: {e}")
            if not quiet:
                import traceback
                traceback.print_exc()
            continue
    
    if not quiet:
        print(f"\nCompleted {runs} runs")


if __name__ == "__main__":
    main()

