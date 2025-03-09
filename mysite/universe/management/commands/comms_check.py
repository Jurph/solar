from django.core.management.base import BaseCommand
import time

# Import models and event types
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.actor import Pilot, Satellite
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.simulation_queue import SimulationQueue

class Command(BaseCommand):
    help = "Simulate a comms check: a pilot requests a comms check and a satellite replies."

    def handle(self, *args, **options):
        self.stdout.write("Starting comms check simulation...")

        # Get a random ship. Give up if none exist by creating one.
        ship = Ship.objects.order_by('?').first()
        if not ship:
            self.stdout.write("No ships found. Creating a dummy ship...")
            dummy_location = Location(name="Deep Space")
            dummy_location.save()
            ship = Ship.create(name="TestShip", location=dummy_location)
        
        # Ensure the ship has a pilot.
        if not getattr(ship, "pilot", None):
            self.stdout.write("Ship has no pilot. Creating one...")
            pilot = Pilot.create(ship=ship)
            ship.pilot = pilot
            ship.save()
        else:
            pilot = ship.pilot

        # Create pilot DialogueEvent:
        # "Nav Beacon J5, this is [SHIPNAME], comms check please."
        pilot_message = f"Nav Beacon J5, this is {ship.name}, comms check please."
        pilot_event = DialogueEvent(
            timestamp=0.0,  # Trigger immediately
            actor=pilot,
            text=pilot_message,
            expect_reply=True,
            duration=3.0,
            event_type="dialogue"
        )

        # Create satellite DialogueEvent for reply:
        # The Satellite (named "Nav Beacon J5") replies "BEEP BOOP" 5 seconds later.
        satellite_actor = Satellite.create(name="Nav Beacon J5")
        satellite_reply_event = DialogueEvent(
            timestamp=5.0,  # Occurs 5 seconds after pilot's event
            actor=satellite_actor,
            text="BEEP BOOP",
            expect_reply=False,
            duration=2.0,
            event_type="dialogue"
        )

        # Instantiate SimulationQueue and load the events
        sim_queue = SimulationQueue()
        sim_queue.add_item(pilot_event)
        sim_queue.add_item(satellite_reply_event)
        self.stdout.write("Loaded pilot and satellite dialogue events into simulation queue.")

        # Start a simple simulation loop that processes events as their timestamps expire.
        simulation_start = time.monotonic()
        try:
            while not sim_queue.is_empty():
                elapsed = time.monotonic() - simulation_start
                # Peek at the next event.
                next_item = sim_queue.queue[0]
                if next_item.timestamp <= elapsed:
                    # Pop and process the event.
                    event = sim_queue.pop_item()
                    event.process()  # The event's own process() prints its message and any follow-up action.
                    self.stdout.write(f"[{elapsed:.2f}s] Processed event for {event.actor.name}: {event.text}")
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stdout.write("Comms check simulation terminated by user.") 