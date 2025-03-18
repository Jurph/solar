import heapq
import threading
import time

from django.core.management.base import BaseCommand
from django.dispatch import receiver

from mysite.universe.signals import dialogue_event_processed, navigation_event_processed
from mysite.universe.models.event import DialogueEvent, NavigationEvent


# Global list to store processed dialogue events (used in tests)
DIALOGUE_EVENTS_RECEIVED = []
DIALOGUE_EVENTS_RECEIVED_LOCK = threading.Lock()


@receiver(dialogue_event_processed)
def dialogue_event_listener(sender, event, **kwargs):
    """Handle dialogue events by appending to a global list."""
    global DIALOGUE_EVENTS_RECEIVED
    with DIALOGUE_EVENTS_RECEIVED_LOCK:
        DIALOGUE_EVENTS_RECEIVED.append(event)


@receiver(navigation_event_processed)
def navigation_event_listener(sender, event, **kwargs):
    """Handle navigation events by appending to the global list."""
    global DIALOGUE_EVENTS_RECEIVED
    with DIALOGUE_EVENTS_RECEIVED_LOCK:
        DIALOGUE_EVENTS_RECEIVED.append(event)


class Command(BaseCommand):
    """Django management command to run the simulation loop."""
    help = "Runs the simulation loop"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def dialogue_events_received(self):
        return DIALOGUE_EVENTS_RECEIVED

    def handle(self, *args, **options):
        """Run the simulation loop."""
        queue = SimulationQueue()
        self.load_test_events(queue)
        self.stdout.write("Starting simulation loop...")
        self.start_simulation_loop(queue)

    def load_initial_events(self, queue):
        """Load initial events into the queue (to be implemented)."""
        pass

    def start_simulation_loop(self, queue, time_fn=None):
        """Start the main simulation loop."""
        if time_fn is None:
            time_fn = time.time
        start_time = time_fn()
        queue._start_time = start_time

        try:
            while True:
                current_time = time_fn() - start_time
                queue._current_time = current_time
                queue.process_due_events(current_time)

                if not queue.peek_next_event():
                    self.stdout.write("Simulation complete")
                    break

                next_event = queue.peek_next_event()
                sleep_time = min(0.1, max(0, next_event.timestamp - current_time))
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            self.stdout.write("Simulation stopped")

    def load_test_events(self, queue):
        """Load some dummy events for testing."""
        from mysite.universe.models.event import DialogueEvent
        from mysite.universe.models.actor import Actor

        try:
            pilot = Actor.objects.get(name="Test Pilot")
        except Actor.DoesNotExist:
            pilot = Actor.objects.create(
                name="Test Pilot",
                role="pilot",
                personality="professional"
            )

        try:
            controller = Actor.objects.get(name="Test Controller")
        except Actor.DoesNotExist:
            controller = Actor.objects.create(
                name="Test Controller",
                role="controller",
                personality="helpful"
            )

        events = [
            DialogueEvent(
                timestamp=5.0,
                actor=pilot,
                text="Control, this is Test Ship requesting clearance for departure.",
                expect_reply=True,
                duration=2.0,
                event_type="dialogue",
            ),
            DialogueEvent(
                timestamp=10.0,
                actor=controller,
                text="Test Ship, you are cleared for departure. Proceed on heading 270.",
                expect_reply=True,
                duration=3.0,
                event_type="dialogue",
            ),
            DialogueEvent(
                timestamp=15.0,
                actor=pilot,
                text="Copy that Control, heading 270. Test Ship out.",
                expect_reply=False,
                duration=2.0,
                event_type="dialogue",
            ),
        ]
        for event in events:
            queue.add_event(event)
        self.stdout.write(f"Loaded {len(events)} test events")


class SimulationQueue:
    """A time-ordered queue of simulation events."""

    def __init__(self):
        self._queue = []  # Priority queue ordered by timestamp
        self._start_time = None
        self._current_time = 0

    def add_event(self, event):
        """Add an event to the queue (using heapq to maintain order by timestamp)."""
        heapq.heappush(self._queue, (event.timestamp, event))

    def peek_next_event(self):
        """Return the next event without removing it, or None if empty."""
        if self._queue:
            return self._queue[0][1]
        return None

    def get_next_event(self):
        """Get and remove the next event, or return None if empty."""
        if self._queue:
            return heapq.heappop(self._queue)[1]
        return None

    def process_due_events(self, current_time: float) -> None:
        """
        Process all events whose timestamp is <= current_time.
        
        For each event:
        1. Remove it from the queue
        2. Call its process() method
        3. If process() returns new events, add them to the queue
        4. Emit appropriate signal based on event type
        """
        while self._queue and self._queue[0][0] <= current_time:
            event = self.get_next_event()
            
            # First process the event and handle any returned events
            try:
                result = event.process()
                if result:
                    # If process() returns a list of events, add them all
                    if isinstance(result, list):
                        for new_event in result:
                            self.add_event(new_event)
                    # If process() returns a single event, add it
                    else:
                        self.add_event(result)
                
                # Then emit the appropriate signal for this event
                if isinstance(event, DialogueEvent):
                    dialogue_event_processed.send(sender=SimulationQueue, event=event)
                elif isinstance(event, NavigationEvent):
                    navigation_event_processed.send(sender=SimulationQueue, event=event)
                    
            except Exception as e:
                print(f"Error processing event: {e}")
                # Continue processing other events even if one fails


# Expose the global dialogue events list as an attribute on the Command class for testing
Command.dialogue_events_received = DIALOGUE_EVENTS_RECEIVED
