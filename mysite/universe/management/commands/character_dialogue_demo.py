"""
Management command to demonstrate emergent character dialogue between pilots, controllers, and satellites.

This command uses the actual Django models and services to:
1. Create a ship and pilot on Mars
2. Plan a route to Earth
3. Generate dialogue events for the journey
4. Process these events in a simulation queue
5. Include a comms check with a satellite

Usage:
    python manage.py character_dialogue_demo [--temperature TEMP] [--use-json]
"""

import os
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from typing import Optional, Dict

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.navigation import NavigationEvent, UniverseGraph
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.script_server import ScriptService
from mysite.universe.services.llm_service import LLMService
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.management.commands.start_simulation_loop import (
    DemoQueue,
    DIALOGUE_EVENTS_RECEIVED,
    DIALOGUE_EVENTS_RECEIVED_LOCK,
)


class Command(BaseCommand):
    help = "Demonstrate emergent character dialogue between pilots, controllers, and satellites"

    # ANSI color codes for retro terminal aesthetic
    AMBER = "\033[38;5;214m"  # IBM-era amber (Orange3)
    MUTED_GREEN = "\033[38;5;70m"  # Muted green (DarkSeaGreen3)
    RESET = "\033[0m"

    def add_arguments(self, parser):
        parser.add_argument(
            "--temperature",
            type=float,
            default=0.25,
            help="Temperature setting for the LLM (0.0-1.0, default: 0.25)",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Print LLM prompts for debugging",
        )
        parser.add_argument(
            "--use-json",
            action="store_true",
            help="Use JSON-structured dialogue format",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=2.0,
            help="Delay in seconds between dialogue events (default: 2.0)",
        )

    def ensure_controllers_exist(self):
        """Ensure that all control stations have associated Controller actors."""
        from mysite.universe.services.actor_server import ActorService

        # Deploy controllers once using the canonical method
        results = ActorService.deploy_controllers()
        total = sum(len(v) for v in results.values())
        self.stdout.write(self.style.SUCCESS(f"Deployed {total} controllers"))

    def handle(self, *args, **options):
        # Get the temperature setting
        temperature = options["temperature"]
        debug_mode = options["debug"]
        use_json = options["use_json"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Running dialogue demo with temperature {temperature} and {'JSON' if use_json else 'text'} mode"
            )
        )

        # Initialize the universe if needed
        try:
            # Try to get Earth to check if universe is initialized
            Location.objects.get(name="Earth")
        except Location.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    "Universe not initialized. Importing from test_universe.xml..."
                )
            )
            xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
            importer = UniverseImporter(xml_file)
            importer.import_universe()
            UniverseGraph.get_instance().rebuild_graph()
            self.stdout.write(self.style.SUCCESS("Universe initialized successfully"))

        # Create LLM service with debug mode
        # Note: LLMService now handles JSON mode automatically based on prompts
        try:
            llm = LLMService(quiet_mode=not debug_mode)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to initialize LLM service: {e}")
            )
            raise
            use_json = False

        llm.temperature = temperature
        ScriptService.get_instance(llm=llm)

        # Ensure all control stations have controllers
        self.ensure_controllers_exist()

        # Setup the universe objects
        try:
            with transaction.atomic():
                # Get Mars and Earth locations
                try:
                    mars = Location.objects.get(name="Mars")
                    earth = Location.objects.get(name="Earth")
                except Location.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            "Required locations not found in the database. Have you imported the universe data?"
                        )
                    )
                    return

                # Create a ship and pilot
                ship = Ship.create(name="Stellar Horizon", location=mars)
                pilot = Pilot.create(name="Captain Rodriguez", ship=ship)

                # Create a satellite for comms check
                satellite = Satellite.create(name="Relay Satellite Alpha")

                # Get the existing Earth Orbital Control controller
                controller = Controller.objects.get(name="Earth Orbital Control")

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created ship {ship.name} with pilot {pilot.name} at {mars.name}"
                    )
                )
                self.stdout.write(self.style.SUCCESS(f"Destination: {earth.name}"))
                self.stdout.write(self.style.SUCCESS(f"Satellite: {satellite.name}"))
                self.stdout.write(self.style.SUCCESS(f"Controller: {controller.name}"))

            # Plan a route from Mars to Earth
            route_service = RouteService()
            route_events = route_service.plan_route(origin=mars, destination=earth)

            if not route_events:
                self.stdout.write(
                    self.style.ERROR("Failed to generate a route from Mars to Earth")
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"Generated route with {len(route_events)} navigation events"
                )
            )

            # Process the navigation events to generate dialogue events
            # Demo mode: use_physics_delays=False for fast playback
            # Real simulation would use True for realistic timing
            script_events = list(
                ScriptService.get_instance().parse_navigation_events(
                    route_events, ship, use_physics_delays=False
                )
            )

            # Insert a comms check with the satellite after the first few events
            comms_check_position = min(3, len(script_events) - 1)
            comms_check_timestamp = script_events[comms_check_position].timestamp + 5.0

            # Generate comms check chain using the particle system
            comms_check_events = (
                ScriptService.get_instance().generate_comms_check_chain(
                    pilot=pilot,
                    satellite=satellite,
                    ship=ship,
                    base_timestamp=comms_check_timestamp,
                )
            )

            # Insert the comms check events into the script events
            for i, comms_event in enumerate(comms_check_events):
                script_events.insert(comms_check_position + 1 + i, comms_event)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Generated {len(script_events)} script events including comms check"
                )
            )

            # Clear any existing dialogue events
            with DIALOGUE_EVENTS_RECEIVED_LOCK:
                DIALOGUE_EVENTS_RECEIVED.clear()

            # Create a demo queue with configurable delay
            delay_seconds = options["delay"]
            demo_queue = DemoQueue(delay_seconds=delay_seconds)

            # Add all events to the queue
            for event in script_events:
                demo_queue.add_event(event)

            self.stdout.write(self.style.SUCCESS("Starting simulation..."))

            # Define callback to print events as they're processed
            def print_event(event):
                if isinstance(event, DialogueEvent):
                    self._print_message(event.actor.name, event.text)
                elif isinstance(event, NavigationEvent):
                    self._print_message(
                        "NAVIGATION", f"{event.maneuver.name} to {event.target.name}"
                    )

            # Process all events with the demo queue (fast-forward mode)
            try:
                events_processed = demo_queue.process_all_events(callback=print_event)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Simulation interrupted by user"))

            # Print summary
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(self.style.SUCCESS("Simulation complete"))
            self.stdout.write(f"Processed {events_processed} dialogue events")
            self.stdout.write("=" * 80)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))

    def _print_message(self, speaker, message, debug_info: Optional[Dict] = None):
        """
        Print a message with formatting and simulated typing.
        Handles both regular stdout and redirected stdout cases.

        Args:
            speaker: Name of the speaker
            message: The message content (raw text or JSON)
            debug_info: Optional dictionary containing debug info like prompts
        """
        try:
            # If message is JSON, extract the actual message text
            if isinstance(message, str) and message.strip().startswith("{"):
                try:
                    from mysite.universe.schemas.dialogue_schema import DialogueMessage
                    import json

                    msg_obj = DialogueMessage(**json.loads(message))
                    message = msg_obj.message
                except (json.JSONDecodeError, ValueError):
                    # If JSON parsing fails, use the raw message
                    pass

            # If in debug mode and we have debug info, print it first in gray
            if debug_info:
                debug_text = "\n\033[90m=== LLM Prompt ===\n"  # Light gray
                if "system" in debug_info:
                    debug_text += f"System: {debug_info['system']}\n"
                if "user" in debug_info:
                    debug_text += f"User: {debug_info['user']}\n"
                debug_text += "================\033[0m\n"  # Reset color
                self.stdout.write(debug_text)

            # Build formatted message with custom colors
            # Speaker name in amber, message text in muted green for that retro terminal feel
            formatted_message = f"\n{self.AMBER}{speaker}{self.RESET}:\n{self.MUTED_GREEN}{message}{self.RESET}\n"

            # Character-by-character scrolling effect (like a serial/modem feed)
            try:
                for char in formatted_message:
                    self.stdout.write(char, ending="")
                    self.stdout.flush()
                    # Variable delay: faster for spaces, slower for punctuation, medium for letters
                    if char == " ":
                        time.sleep(0.002)  # Quick for spaces
                    elif char in ".,!?;:":
                        time.sleep(0.015)  # Slight pause for punctuation
                    elif char == "\n":
                        time.sleep(0.01)  # Brief pause for newlines
                    else:
                        time.sleep(0.008)  # Medium speed for regular characters
            except (AttributeError, TypeError):
                # If character-by-character fails, write the whole formatted message
                self.stdout.write(formatted_message)

            time.sleep(0.3)  # Brief pause between messages

        except (AttributeError, TypeError):
            # If all formatting fails, fall back to simple print
            if debug_info:
                print("\n=== LLM Prompt ===")
                if "system" in debug_info:
                    print("System:", debug_info["system"])
                if "user" in debug_info:
                    print("User:", debug_info["user"])
                print("================\n")
            print(f"\n{speaker}:\n{message}\n")
            time.sleep(0.3)  # Still pause between messages
