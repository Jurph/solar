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
        from mysite.universe.models.actor import Pilot, Controller
        from mysite.universe.models.base import Location
        from mysite.universe.models.scale import Scale

        # Use proper .create() methods to ensure audio profiles are assigned
        try:
            pilot = Pilot.objects.get(name="Test Pilot")
        except Pilot.DoesNotExist:
            pilot = Pilot.create(name="Test Pilot")

        try:
            controller = Controller.objects.get(name="Test Controller")
        except Controller.DoesNotExist:
            # Controller needs a location
            loc, _ = Location.objects.get_or_create(
                name="Test Control Station",
                defaults={'scale': Scale.STATION}
            )
            controller = Controller.create(name="Test Controller", location=loc)

        events = [
            DialogueEvent(
                timestamp=5.0,
                actor=pilot,
                text="Control, this is Test Ship requesting clearance for departure.",
                duration=2.0,
                event_type="dialogue",
            ),
            DialogueEvent(
                timestamp=10.0,
                actor=controller,
                text="Test Ship, you are cleared for departure. Proceed on heading 270.",
                duration=3.0,
                event_type="dialogue",
            ),
            DialogueEvent(
                timestamp=15.0,
                actor=pilot,
                text="Copy that Control, heading 270. Test Ship out.",
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
        self._event_counter = 0  # Tie-breaker for events with same timestamp

    def add_event(self, event):
        """Add an event to the queue (using heapq to maintain order by timestamp)."""
        # Use counter as tie-breaker: (timestamp, counter, event)
        # This prevents comparison errors when timestamps are equal
        heapq.heappush(self._queue, (event.timestamp, self._event_counter, event))
        self._event_counter += 1

    def peek_next_event(self):
        """Return the next event without removing it, or None if empty."""
        if self._queue:
            return self._queue[0][2]  # Third element is the event
        return None

    def get_next_event(self):
        """Get and remove the next event, or return None if empty."""
        if self._queue:
            return heapq.heappop(self._queue)[2]  # Third element is the event
        return None

    def process_due_events(self, current_time: float) -> None:
        """
        Process all events whose timestamp is <= current_time.
        
        For each event:
        1. Remove it from the queue
        2. Emit appropriate signal based on event type
        
        Note: Dialogue chains are generated complete upfront, so events don't
        generate follow-up events. The queue just emits signals for each event.
        """
        while self._queue and self._queue[0][0] <= current_time:  # First element is timestamp
            event = self.get_next_event()
            
            try:
                # Emit the appropriate signal for this event
                if isinstance(event, DialogueEvent):
                    dialogue_event_processed.send(sender=SimulationQueue, event=event)
                elif isinstance(event, NavigationEvent):
                    navigation_event_processed.send(sender=SimulationQueue, event=event)
                    
            except Exception as e:
                print(f"Error processing event: {e}")
                # Continue processing other events even if one fails


class DemoQueue(SimulationQueue):
    """
    A queue that fast-forwards through events with a fixed delay between each.
    
    Unlike SimulationQueue which respects actual timestamps, DemoQueue processes
    events sequentially with a configurable delay (default 5 seconds) between each.
    This is useful for demos where you want to see the dialogue flow without waiting
    for realistic physics-based delays.
    
    Usage:
        queue = DemoQueue(delay_seconds=3.0)  # 3 seconds between events
        queue.add_event(event1)
        queue.add_event(event2)
        queue.process_all_events()  # Processes all events with delays
    """
    
    def __init__(self, delay_seconds: float = 5.0):
        """
        Initialize DemoQueue with a fixed delay between events.
        
        Args:
            delay_seconds: Time to wait between processing events (default: 5.0)
        """
        super().__init__()
        self.delay_seconds = delay_seconds
    
    def process_all_events(self, callback=None) -> int:
        """
        Process all events in order with fixed delays between each.
        
        Ignores actual event timestamps and processes events sequentially
        with self.delay_seconds between each event.
        
        Args:
            callback: Optional function to call after each event is processed.
                      Receives the event as its argument.
        
        Returns:
            Number of events processed.
        """
        events_processed = 0
        
        while self._queue:
            event = self.get_next_event()
            
            try:
                # Emit the appropriate signal for this event
                if isinstance(event, DialogueEvent):
                    dialogue_event_processed.send(sender=DemoQueue, event=event)
                elif isinstance(event, NavigationEvent):
                    navigation_event_processed.send(sender=DemoQueue, event=event)
                
                events_processed += 1
                
                # Call optional callback
                if callback:
                    callback(event)
                
                # Wait before processing next event (if there are more)
                if self._queue and self.delay_seconds > 0:
                    time.sleep(self.delay_seconds)
                    
            except Exception as e:
                print(f"Error processing event: {e}")
                # Continue processing other events even if one fails
        
        return events_processed
    
    def process_all_events_instant(self, callback=None) -> int:
        """
        Process all events instantly with no delays (for testing).
        
        Args:
            callback: Optional function to call after each event is processed.
        
        Returns:
            Number of events processed.
        """
        original_delay = self.delay_seconds
        self.delay_seconds = 0
        try:
            return self.process_all_events(callback=callback)
        finally:
            self.delay_seconds = original_delay


# Expose the global dialogue events list as an attribute on the Command class for testing
Command.dialogue_events_received = DIALOGUE_EVENTS_RECEIVED
