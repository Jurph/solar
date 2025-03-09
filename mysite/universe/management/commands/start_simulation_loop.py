from django.core.management.base import BaseCommand
import time

# Import our simulation queue and signals
from mysite.universe.simulation_queue import SimulationQueue
from mysite.universe.signals import simulation_event

# We'll need these to create dummy events
from mysite.universe.models.navigation import NavigationEvent, ManeuverType
from mysite.universe.models.base import Location
from mysite.universe.models.ship import Ship

def event_listener(sender, **kwargs):
    """
    A demonstration receiver for simulation events.
    This function will be called when a simulation event is published.
    """
    item = kwargs.get("item")
    if item:
        # For example, the dialogue scroller could convert the actor's identifier to uppercase,
        # then dispatch the finalized dialogue to the UI or TTS engine.
        print(f"[Listener] {item.ship.name.upper()} says: (Event: {item.nav_event.maneuver})")

class Command(BaseCommand):
    help = "Starts the simulation game loop that processes events based on timestamps and publishes them via Django Signals."

    def handle(self, *args, **options):
        self.stdout.write("Starting simulation loop...")

        # Connect our receiver to the simulation_event signal.
        simulation_event.connect(event_listener, sender=SimulationQueue)

        simulation_queue = SimulationQueue()

        # Preload a demo mission for a satellite that beeps every 10 seconds.
        # Create a dummy location for the satellite (would normally be saved in the DB)
        dummy_location = Location(name="Orbit")
        dummy_location.save()

        # Create a dummy satellite ship
        satellite_ship = Ship(name="Satellite", current_location=dummy_location, cargo="N/A", status="TRAN")
        satellite_ship.save()

        # Create a series of dummy NavigationEvent objects with timestamps every 10 seconds
        beep_events = []
        for i in range(1, 7):  # This will create events at 10s, 20s, …, 60s
            event = NavigationEvent(
                origin=dummy_location,
                current=dummy_location,
                next=dummy_location,
                destination=dummy_location,
                maneuver=ManeuverType.SUBLIGHT,  # Using SUBLIGHT as a placeholder maneuver
                controller=None,
                duration=i * 10,
                description="BEEP BOOP"
            )
            beep_events.append(event)

        simulation_queue.load_mission(satellite_ship, beep_events)

        # Capture the simulation start time.
        simulation_start = time.monotonic()

        try:
            while True:
                # Determine the elapsed simulation time.
                elapsed = time.monotonic() - simulation_start

                # Check if the next event (if any) is due.
                if not simulation_queue.is_empty():
                    next_item = simulation_queue.queue[0]
                    if next_item.timestamp <= elapsed:
                        # Process the event by removing it from the queue.
                        processed_item = simulation_queue.pop_item()
                        # Notify subscribers via Django Signals.
                        simulation_queue.notify_subscribers(processed_item)
                        # Also, log to stdout for debugging.
                        self.stdout.write(
                            f"[{elapsed:.2f}s] Processing event for {processed_item.ship.name}: {processed_item.nav_event.maneuver} -- {processed_item.nav_event.description}"
                        )
                # Sleep briefly to avoid a tight loop.
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("Simulation loop terminated by user.")
