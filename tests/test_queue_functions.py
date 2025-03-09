import time
from unittest.mock import patch, MagicMock
import heapq
from django.test import TestCase
from django.dispatch import receiver
from collections import namedtuple
import threading

import pytest


from mysite.universe.management.commands.start_simulation_loop import (
    SimulationQueue,
    Command,
    DIALOGUE_EVENTS_RECEIVED,
)
from mysite.universe.models.event import DialogueEvent
from mysite.universe.models.actor import Actor
from mysite.universe.signals import dialogue_event_processed, navigation_event_processed

# Create a simple event class for testing
SimpleEvent = namedtuple('SimpleEvent', ['timestamp', 'message'])

class SimpleQueue:
    """A bare-bones priority queue that processes events in timestamp order"""
    
    def __init__(self):
        self._queue = []  # Priority queue ordered by timestamp
    
    def add_event(self, event):
        """Add an event to the queue"""
        heapq.heappush(self._queue, (event.timestamp, event))
    
    def peek_next_event(self):
        """See the next event without removing it"""
        if self._queue:
            return self._queue[0][1]
        return None
    
    def get_next_event(self):
        """Get and remove the next event"""
        if self._queue:
            return heapq.heappop(self._queue)[1]
        return None
    
    def process_due_events(self, current_time):
        """Process all events that are due by the given time"""
        processed = []
        while self._queue and self._queue[0][0] <= current_time:
            event = self.get_next_event()
            processed.append(event)
            print(f"Processed event at {event.timestamp}: {event.message}")
        return processed

class TestSimulationQueue(TestCase):
    """Test the SimulationQueue functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create test actors
        self.pilot = Actor.objects.create(
            name="Test Pilot",
            role="pilot"
        )
        
        self.controller = Actor.objects.create(
            name="Test Station Control",
            role="controller"
        )
        
        # Create a queue
        self.queue = SimulationQueue()
        
        # Set up signal trackers
        self.dialogue_events_received = []
        self.navigation_events_received = []
        
        # Connect test signal handlers - explicitly set sender=None to receive from any sender
        @receiver(dialogue_event_processed, sender=None)
        def test_dialogue_handler(sender, event, **kwargs):
            self.dialogue_events_received.append(event)
        
        @receiver(navigation_event_processed, sender=None)
        def test_navigation_handler(sender, event, **kwargs):
            self.navigation_events_received.append(event)
        
        # Store the handlers to prevent garbage collection
        self.test_dialogue_handler = test_dialogue_handler
        self.test_navigation_handler = test_navigation_handler
    
    def create_test_events(self):
        """Create a set of test events with different timestamps"""
        events = [
            DialogueEvent(
                timestamp=5.0,
                actor=self.pilot,
                text="Control, this is Test Ship requesting clearance for departure.",
                expect_reply=True,
                duration=2.0,
                event_type="dialogue"
            ),
            DialogueEvent(
                timestamp=10.0,
                actor=self.controller,
                text="Test Ship, you are cleared for departure. Proceed on heading 270.",
                expect_reply=True,
                duration=3.0,
                event_type="dialogue"
            ),
            DialogueEvent(
                timestamp=15.0,
                actor=self.pilot,
                text="Copy that Control, heading 270. Test Ship out.",
                expect_reply=False,
                duration=2.0,
                event_type="dialogue"
            )
        ]
        return events
    
    def test_add_and_peek_event(self):
        """Test that events can be added and peeked at"""
        # Create an event and add it to the queue
        event = DialogueEvent(
            timestamp=5.0,
            actor=self.pilot,
            text="Test message",
            expect_reply=False,
            duration=1.0,
            event_type="dialogue"
        )
        self.queue.add_event(event)
        
        # Peek at the next event
        next_event = self.queue.peek_next_event()
        
        # Check that it's the event we added
        self.assertEqual(next_event, event)
        
        # Check that peeking didn't remove the event
        self.assertEqual(len(self.queue._queue), 1)
    
    def test_get_next_event(self):
        """Test that events can be retrieved and removed from the queue"""
        # Create events with different timestamps
        events = self.create_test_events()
        
        # Add events to the queue (in reverse order to test sorting)
        for event in reversed(events):
            self.queue.add_event(event)
        
        # Get the next event
        next_event = self.queue.get_next_event()
        
        # Check that we got the earliest event
        self.assertEqual(next_event, events[0])
        
        # Check that the event was removed from the queue
        self.assertEqual(len(self.queue._queue), 2)
    
    def test_process_due_events(self):
        """Test that due events are processed in timestamp order"""
        # Create events with different timestamps
        events = self.create_test_events()
        
        # Add events to the queue
        for event in events:
            self.queue.add_event(event)
        
        # Process events up to timestamp 12.0
        current_time = 12.0
        self.queue.process_due_events(current_time)
        
        # Check that events with timestamps <= 12.0 were processed
        self.assertEqual(len(self.dialogue_events_received), 2)
        self.assertEqual(self.dialogue_events_received[0], events[0])
        self.assertEqual(self.dialogue_events_received[1], events[1])
        
        # Check that the event with timestamp > 12.0 is still in the queue
        self.assertEqual(len(self.queue._queue), 1)
        self.assertEqual(self.queue.peek_next_event(), events[2])
    
    @patch('time.time')
    def test_simulation_loop(self, mock_time):
        """Test the full simulation loop with mocked time"""
        from mysite.universe.management.commands.start_simulation_loop import Command, DIALOGUE_EVENTS_RECEIVED
        
        # Clear the global list before starting
        DIALOGUE_EVENTS_RECEIVED.clear()
        
        # Mock time.time() to return controlled values
        start_time = 1000.0  # arbitrary start time
        mock_time.return_value = start_time
        
        # Create events
        events = self.create_test_events()
        
        # Add events to queue
        for event in events:
            self.queue.add_event(event)
        
        # Create command and patch its methods
        command = Command()
        command.stdout = MagicMock()
        command.load_initial_events = MagicMock()
        
        # Start the simulation loop in a separate thread so we can control it
        stop_event = threading.Event()
        
        def run_simulation():
            try:
                command.start_simulation_loop(self.queue)
            except KeyboardInterrupt:
                pass
            stop_event.set()
        
        thread = threading.Thread(target=run_simulation)
        thread.daemon = True
        thread.start()
        
        # Advance time and check that events are processed
        for i, event in enumerate(events):
            # Move time forward to just after this event's timestamp
            mock_time.return_value = start_time + event.timestamp + 0.1
            
            # Give the simulation loop more time to process
            time.sleep(0.5)  # Increased from 0.1 to 0.5
            
            # Check that the event was processed
            self.assertEqual(len(DIALOGUE_EVENTS_RECEIVED), i + 1,
                            f"Expected {i+1} events after processing event with timestamp {event.timestamp}")
            self.assertEqual(DIALOGUE_EVENTS_RECEIVED[i], event,
                            f"Event at index {i} doesn't match expected event")
        
        # Signal the thread to stop
        stop_event.set()
        
        # Wait for the thread to finish
        thread.join(timeout=1.0)
        
        # Check final state
        self.assertEqual(len(DIALOGUE_EVENTS_RECEIVED), 3)

def test_queue_processes_events_in_order():
    """Test that events are processed in timestamp order regardless of addition order"""
    
    # Create a queue
    queue = SimpleQueue()
    
    # Create events with out-of-order timestamps
    events = [
        SimpleEvent(timestamp=30, message="Third event"),
        SimpleEvent(timestamp=10, message="First event"),
        SimpleEvent(timestamp=50, message="Fifth event"),
        SimpleEvent(timestamp=20, message="Second event"),
        SimpleEvent(timestamp=40, message="Fourth event"),
    ]
    
    # Add events to the queue (in their original out-of-order sequence)
    for event in events:
        queue.add_event(event)
    
    # Sort events by timestamp to get expected order
    expected_order = sorted(events, key=lambda e: e.timestamp)
    
    # Process all events
    processed_events = queue.process_due_events(current_time=100)
    
    # Check that events were processed in timestamp order
    assert processed_events == expected_order
    
    # Queue should be empty now
    assert queue.peek_next_event() is None

def test_queue_processes_only_due_events():
    """Test that only events with timestamps <= current_time are processed"""
    
    # Create a queue
    queue = SimpleQueue()
    
    # Create events with different timestamps
    events = [
        SimpleEvent(timestamp=10, message="First event"),
        SimpleEvent(timestamp=20, message="Second event"),
        SimpleEvent(timestamp=30, message="Third event"),
        SimpleEvent(timestamp=40, message="Fourth event"),
        SimpleEvent(timestamp=50, message="Fifth event"),
    ]
    
    # Add all events to the queue
    for event in events:
        queue.add_event(event)
    
    # Process events up to timestamp 35
    processed_events = queue.process_due_events(current_time=35)
    
    # Check that only first three events were processed
    assert processed_events == events[:3]
    
    # Check that remaining events are still in the queue
    assert queue.peek_next_event() == events[3]
    
    # Process remaining events
    remaining_processed = queue.process_due_events(current_time=100)
    
    # Check all remaining events were processed
    assert remaining_processed == events[3:]
    
    # Queue should be empty now
    assert queue.peek_next_event() is None

# Group 1: SimulationQueue Behavior

@pytest.fixture(autouse=True)
def clear_dialogue_events():
    """Ensure the global dialogue events list is empty before and after each test."""
    DIALOGUE_EVENTS_RECEIVED.clear()
    yield
    DIALOGUE_EVENTS_RECEIVED.clear()


class DummyStdout:
    def write(self, message):
        pass  # Ignore output for testing


class DummyActor:
    def __init__(self, name="Dummy Actor"):
        self.name = name


@pytest.fixture
def dummy_event():
    """Return a dummy DialogueEvent."""
    actor = DummyActor()
    return DialogueEvent(
        timestamp=5.0,
        actor=actor,
        text="Dummy message",
        expect_reply=False,
        duration=1.0,
        event_type="dialogue",
    )


def test_add_and_peek_event(dummy_event):
    """Test that adding an event and peeking returns the correct event."""
    queue = SimulationQueue()
    assert queue.peek_next_event() is None
    queue.add_event(dummy_event)
    assert queue.peek_next_event() == dummy_event


def test_process_due_events(dummy_event):
    """Test that process_due_events removes events after their timestamp has passed."""
    queue = SimulationQueue()
    queue.add_event(dummy_event)
    fake_current_time = 6.0
    queue.process_due_events(fake_current_time)
    assert queue.peek_next_event() is None


# Group 2: Signal Emission and Shared State

def test_emit_event_updates_global_list(dummy_event):
    """Test that emitting a DialogueEvent updates the global dialogue events list."""
    queue = SimulationQueue()
    queue.emit_event(dummy_event)
    command = Command()
    assert len(command.dialogue_events_received) == 1
    assert command.dialogue_events_received[0] == dummy_event


def test_global_state_identity():
    """Test that the global dialogue events list is shared between modules."""
    command = Command()
    assert id(command.dialogue_events_received) == id(DIALOGUE_EVENTS_RECEIVED)


# Group 3: Overall Simulation Loop with Controlled Time

def test_simulation_loop_with_injected_time(dummy_event):
    """Test the simulation loop by injecting a fake time function for deterministic behavior."""
    queue = SimulationQueue()
    queue.add_event(dummy_event)
    
    # Create a mutable fake time value
    time_val = [1000.0]

    def fake_time():
        return time_val[0]

    command = Command()
    command.stdout = DummyStdout()
    
    stop_event = threading.Event()

    def run_simulation():
        try:
            command.start_simulation_loop(queue, time_fn=fake_time)
        except KeyboardInterrupt:
            pass
        stop_event.set()

    thread = threading.Thread(target=run_simulation)
    thread.daemon = True
    thread.start()

    # Advance fake time so that the event's timestamp (5.0 seconds after start) is reached
    time_val[0] = 1006.0  # start_time + 6 seconds
    
    thread.join(timeout=1.0)

    # The event should have been processed
    assert len(command.dialogue_events_received) == 1
