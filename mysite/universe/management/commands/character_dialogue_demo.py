"""
Management command to demonstrate emergent character dialogue between pilots, controllers, and satellites.

This command uses the actual Django models and services to:
1. Create a ship and pilot on Mars
2. Plan a route to Earth
3. Generate dialogue events for the journey
4. Process these events in a simulation queue
5. Include a comms check with a satellite

Usage:
    python manage.py character_dialogue_demo [--temperature TEMP]
"""
import os
import time
import threading
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from typing import Optional, Dict

from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.event import DialogueEvent, NavigationEvent
from mysite.universe.models.navigation import UniverseGraph
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.script_server import ScriptService
from mysite.universe.services.llm_service import LLMService
from mysite.universe.import_xml import UniverseImporter
from mysite.universe.management.commands.start_simulation_loop import SimulationQueue, DIALOGUE_EVENTS_RECEIVED, DIALOGUE_EVENTS_RECEIVED_LOCK


class Command(BaseCommand):
    help = 'Demonstrate emergent character dialogue between pilots, controllers, and satellites'

    def add_arguments(self, parser):
        parser.add_argument(
            '--temperature',
            type=float,
            default=0.7,
            help='Temperature setting for the LLM (0.0-1.0, default: 0.7)',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print LLM prompts for debugging',
        )

    def ensure_controllers_exist(self):
        """Ensure that all control stations have associated Controller actors."""
        control_stations = Location.objects.filter(name__icontains="Control")
        for station in control_stations:
            controller = Controller.objects.filter(name=station.name).first()
            if not controller:
                self.stdout.write(self.style.WARNING(f"{station.name} controller not found, creating it..."))
                controller = Controller.create(name=station.name, location=station)
                self.stdout.write(self.style.SUCCESS(f"Created controller: {controller.name}"))

    def handle(self, *args, **options):
        # Get the temperature setting
        temperature = options['temperature']
        debug_mode = options['debug']
        self.stdout.write(self.style.SUCCESS(f"Running dialogue demo with temperature {temperature}"))
        
        # Initialize the universe if needed
        try:
            # Try to get Earth to check if universe is initialized
            Location.objects.get(name="Earth")
        except Location.DoesNotExist:
            self.stdout.write(self.style.WARNING("Universe not initialized. Importing from test_universe.xml..."))
            xml_file = os.path.join(settings.BASE_DIR, "xml", "test_universe.xml")
            importer = UniverseImporter(xml_file)
            importer.import_universe()
            UniverseGraph.get_instance().rebuild_graph()
            self.stdout.write(self.style.SUCCESS("Universe initialized successfully"))

        # Create LLM service with debug mode
        llm = LLMService(quiet_mode=not debug_mode)
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
                    earth_control = Location.objects.get(name="Earth Orbital Control")
                except Location.DoesNotExist:
                    self.stdout.write(self.style.ERROR("Required locations not found in the database. Have you imported the universe data?"))
                    return
                
                # Create a ship and pilot
                ship = Ship.create(name="Stellar Horizon", location=mars)
                pilot = Pilot.create(name="Captain Rodriguez", ship=ship)
                
                # Create a satellite for comms check
                satellite = Satellite.create(name="Relay Satellite Alpha")
                
                # Get the existing Earth Orbital Control controller
                controller = Controller.objects.get(name="Earth Orbital Control")
                
                self.stdout.write(self.style.SUCCESS(f"Created ship {ship.name} with pilot {pilot.name} at {mars.name}"))
                self.stdout.write(self.style.SUCCESS(f"Destination: {earth.name}"))
                self.stdout.write(self.style.SUCCESS(f"Satellite: {satellite.name}"))
                self.stdout.write(self.style.SUCCESS(f"Controller: {controller.name}"))
        
            # Plan a route from Mars to Earth
            route_service = RouteService()
            route_events = route_service.plan_route(origin=mars, destination=earth)
            
            if not route_events:
                self.stdout.write(self.style.ERROR("Failed to generate a route from Mars to Earth"))
                return
            
            self.stdout.write(self.style.SUCCESS(f"Generated route with {len(route_events)} navigation events"))
            
            # Process the navigation events to generate dialogue events
            script_events = ScriptService.get_instance().parse_navigation_events(route_events, ship)
            
            # Insert a comms check with the satellite after the first few events
            comms_check_position = min(3, len(script_events) - 1)
            comms_check_timestamp = script_events[comms_check_position].timestamp + 5.0
            
            # Create a dialogue event for the comms check
            comms_check_event = DialogueEvent(
                timestamp=comms_check_timestamp,
                actor=pilot,
                text=f"Relay Satellite Alpha, this is {ship.name}. Performing routine comms check, please respond.",
                expect_reply=True,
                duration=2.0,
                event_type="dialogue",
                metadata={"type": "comms_check", "reply_actor_name": satellite.name}
            )
            
            # Insert the comms check event into the script events
            script_events.insert(comms_check_position + 1, comms_check_event)
            
            self.stdout.write(self.style.SUCCESS(f"Generated {len(script_events)} script events including comms check"))
            
            # Clear any existing dialogue events
            with DIALOGUE_EVENTS_RECEIVED_LOCK:
                DIALOGUE_EVENTS_RECEIVED.clear()
            
            # Create a simulation queue
            sim_queue = SimulationQueue()
            
            # Add all events to the queue
            for event in script_events:
                sim_queue.add_event(event)
            
            # Start the simulation loop in a separate thread
            stop_event = threading.Event()
            
            def run_simulation():
                try:
                    start_time = time.time()
                    
                    while not stop_event.is_set() and sim_queue.peek_next_event():
                        current_time = time.time() - start_time
                        sim_queue.process_due_events(current_time)
                        
                        # Sleep a bit to avoid busy waiting
                        next_event = sim_queue.peek_next_event()
                        if next_event:
                            sleep_time = min(0.1, max(0, next_event.timestamp - current_time))
                            time.sleep(sleep_time)
                        else:
                            break
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error in simulation loop: {e}"))
                finally:
                    stop_event.set()
            
            # Start the simulation thread
            self.stdout.write(self.style.SUCCESS("Starting simulation..."))
            thread = threading.Thread(target=run_simulation)
            thread.daemon = True
            thread.start()
            
            # Print dialogue events as they are processed
            last_event_count = 0
            try:
                while thread.is_alive():
                    with DIALOGUE_EVENTS_RECEIVED_LOCK:
                        current_count = len(DIALOGUE_EVENTS_RECEIVED)
                        
                        # Print any new events
                        for i in range(last_event_count, current_count):
                            event = DIALOGUE_EVENTS_RECEIVED[i]
                            if isinstance(event, DialogueEvent):
                                debug_info = {
                                    'system': event.metadata.get('llm_system_prompt'),
                                    'user': event.metadata.get('llm_user_prompt')
                                } if debug_mode else None
                                self._print_message(event.actor.name, event.text, debug_info)
                            elif isinstance(event, NavigationEvent):
                                self._print_message(
                                    "NAVIGATION",
                                    f"{event.maneuver.name} to {event.target.name}"
                                )
                        
                        last_event_count = current_count
                    
                    # Check if all events have been processed
                    if not sim_queue.peek_next_event():
                        break
                    
                    time.sleep(0.1)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Simulation interrupted by user"))
            finally:
                # Stop the simulation thread
                stop_event.set()
                thread.join(timeout=1.0)
            # Print summary
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("Simulation complete"))
            self.stdout.write(f"Processed {len(DIALOGUE_EVENTS_RECEIVED)} dialogue events")
            self.stdout.write("="*80)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            
    def _print_message(self, speaker, message, debug_info: Optional[Dict] = None):
        """
        Print a message with formatting and simulated typing.
        Handles both regular stdout and redirected stdout cases.
        
        Args:
            speaker: Name of the speaker
            message: The message content
            debug_info: Optional dictionary containing debug info like prompts
        """
        try:
            # If in debug mode and we have debug info, print it first in gray
            if debug_info:
                debug_text = "\n\033[90m=== LLM Prompt ===\n"  # Light gray
                if 'system' in debug_info:
                    debug_text += f"System: {debug_info['system']}\n"
                if 'user' in debug_info:
                    debug_text += f"User: {debug_info['user']}\n"
                debug_text += "================\033[0m\n"  # Reset color
                self.stdout.write(debug_text)
                
            # Regular message printing
            formatted_message = f"\n{self.style.WARNING(speaker)}:\n{message}\n"
            
            # Try to write character by character if possible
            try:
                for char in formatted_message:
                    self.stdout.write(char, ending='')
                    self.stdout.flush()
                    time.sleep(0.005)  # Adjust for typing speed
            except (AttributeError, TypeError):
                # If character-by-character fails, write the whole formatted message
                self.stdout.write(formatted_message)
            
            time.sleep(0.5)  # Pause between messages
            
        except (AttributeError, TypeError):
            # If all formatting fails, fall back to simple print
            if debug_info:
                print("\n=== LLM Prompt ===")
                if 'system' in debug_info:
                    print("System:", debug_info['system'])
                if 'user' in debug_info:
                    print("User:", debug_info['user'])
                print("================\n")
            print(f"\n{speaker}:\n{message}\n")
            time.sleep(0.5)  # Still pause between messages