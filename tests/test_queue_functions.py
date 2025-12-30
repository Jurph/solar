"""
Tests for the SimulationQueue and event processing system.

These tests verify:
- Events are processed in timestamp order regardless of add order
- Only due events (timestamp <= current_time) are processed
- Signal emission connects queue processing to UI updates
- Simulation loop processes events at correct times
"""
import threading
import time
from unittest.mock import patch, MagicMock

import pytest
from django.dispatch import receiver
from django.test import TestCase

from mysite.universe.management.commands.start_simulation_loop import (
    Command,
    DIALOGUE_EVENTS_RECEIVED,
    SimulationQueue,
)
from mysite.universe.models.actor import Pilot, Controller
from mysite.universe.models.base import Location
from mysite.universe.models.event import DialogueEvent, NavigationEvent
from mysite.universe.models.ship import Ship
from mysite.universe.signals import dialogue_event_processed, navigation_event_processed
from mysite.universe.models.navigation import ManeuverType


class TestSimulationQueue(TestCase):
    """Integration tests for SimulationQueue with real Django models."""
    
    def setUp(self):
        """Set up test data with real Django models."""
        self.origin = Location.objects.create(name="Test Origin")   
        self.destination = Location.objects.create(name="Test Destination")
        
        self.ship = Ship.objects.create(
            name="Test Ship",
            current_location=self.origin
        )
        
        self.pilot = Pilot.create(ship=self.ship)
        self.pilot.name = "Test Pilot"
        self.pilot.save()
        
        self.controller = Controller.create()
        self.controller.name = "Test Controller"
        self.controller.save()
        
        self.queue = SimulationQueue()
        
        # Track processed events via signals
        self.dialogue_events = []
        self.navigation_events = []
        
        @receiver(dialogue_event_processed, sender=None)
        def test_dialogue_handler(sender, event, **kwargs):
            self.dialogue_events.append(event)
            
        @receiver(navigation_event_processed, sender=None)
        def test_navigation_handler(sender, event, **kwargs):
            self.navigation_events.append(event)
            
        self.test_dialogue_handler = test_dialogue_handler
        self.test_navigation_handler = test_navigation_handler
        
    def create_test_events(self):
        """Create events with different timestamps for queue testing."""
        events = [
            DialogueEvent(
                timestamp=10,
                actor=self.pilot,
                text="Requesting clearance for departure",
                duration=2.0,
                event_type="dialogue",
                metadata={"order": "first_event", "control_name": self.controller.name},
            ),
            DialogueEvent(
                timestamp=12,
                actor=self.controller,
                text="Clearance granted",
                duration=1.5,
                event_type="dialogue",
                metadata={"order": "second_event"}
            ),
            NavigationEvent(
                timestamp=30,
                maneuver=ManeuverType.LAUNCH,
                target=self.destination,
                duration=5.0,
                event_type="navigation",
                metadata={"order": "third_event"}
            )
        ]
        return events
    
    def test_peek_does_not_remove_event(self):
        """Peeking at the queue should not remove the event."""
        event = DialogueEvent(
            timestamp=5.0,
            actor=self.pilot,
            text="Test message",
            duration=1.0,
            event_type="dialogue"
        )
        self.queue.add_event(event)
        
        # Peek twice - should get same event
        first_peek = self.queue.peek_next_event()
        second_peek = self.queue.peek_next_event()
        
        self.assertEqual(first_peek, second_peek)
        self.assertEqual(len(self.queue._queue), 1)
    
    def test_events_processed_in_timestamp_order(self):
        """Events should be processed in timestamp order regardless of add order."""
        events = self.create_test_events()
        
        # Add in reverse order to test sorting
        for event in reversed(events):
            self.queue.add_event(event)
        
        # Get first event - should be earliest timestamp
        first = self.queue.get_next_event()
        self.assertEqual(first.timestamp, 10)
        
        # Next should be timestamp 12
        second = self.queue.get_next_event()
        self.assertEqual(second.timestamp, 12)
    
    def test_process_due_events_respects_timestamp(self):
        """Only events with timestamp <= current_time should be processed."""
        events = self.create_test_events()
        
        for event in events:
            self.queue.add_event(event)
        
        # Process at time 12.0 - should get events at 10 and 12
        self.queue.process_due_events(current_time=12.0)
        
        self.assertEqual(len(self.dialogue_events), 2)
        
        # Event at 30.0 should still be in queue
        self.assertEqual(len(self.queue._queue), 1)
        self.assertEqual(self.queue.peek_next_event().timestamp, 30)
    
    @patch('time.time')
    def test_simulation_loop_processes_events_at_correct_time(self, mock_time):
        """The simulation loop should process events when their time arrives."""
        DIALOGUE_EVENTS_RECEIVED.clear()
        
        start_time = 1000.0
        mock_time.return_value = start_time
        
        events = self.create_test_events()
        for event in events:
            self.queue.add_event(event)
        
        command = Command()
        command.stdout = MagicMock()
        command.load_initial_events = MagicMock()
        
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
        
        # Process each event by advancing mock time
        for i, event in enumerate(events):
            mock_time.return_value = start_time + event.timestamp + 0.1
            time.sleep(0.5)
            
            expected_count = i + 1
            self.assertEqual(
                len(DIALOGUE_EVENTS_RECEIVED), expected_count,
                f"Expected {expected_count} events after timestamp {event.timestamp}"
            )
        
        stop_event.set()
        thread.join(timeout=1.0)


@pytest.fixture(autouse=True)
def clear_dialogue_events():
    """Ensure the global dialogue events list is empty before and after each test."""
    DIALOGUE_EVENTS_RECEIVED.clear()
    yield
    DIALOGUE_EVENTS_RECEIVED.clear()


class DummyStdout:
    def write(self, message):
        pass


class DummyActor:
    def __init__(self, name="Dummy Actor"):
        self.name = name
        self.id = 1  # DialogueEvent requires actor to have an id attribute


def test_queue_processes_only_due_events():
    """
    Events with timestamp > current_time should remain in queue.
    
    This tests the core time-gating at the queue level.
    """
    queue = SimulationQueue()
    dummy_actor = DummyActor()
    
    events = [
        DialogueEvent(timestamp=10, actor=dummy_actor, text="First", duration=1.0, event_type="dialogue"),
        DialogueEvent(timestamp=20, actor=dummy_actor, text="Second", duration=1.0, event_type="dialogue"),
        DialogueEvent(timestamp=30, actor=dummy_actor, text="Third", duration=1.0, event_type="dialogue"),
        DialogueEvent(timestamp=40, actor=dummy_actor, text="Fourth", duration=1.0, event_type="dialogue"),
    ]
    
    for event in events:
        queue.add_event(event)
    
    # Process up to time 25 - should process events at 10 and 20
    queue.process_due_events(current_time=25)
    
    # Events at 30 and 40 should remain
    next_event = queue.peek_next_event()
    assert next_event is not None
    assert next_event.timestamp == 30


def test_global_state_identity():
    """
    The global DIALOGUE_EVENTS_RECEIVED list should be shared.
    
    This ensures signal handlers and command share the same state.
    """
    command = Command()
    assert id(command.dialogue_events_received) == id(DIALOGUE_EVENTS_RECEIVED)


@pytest.mark.django_db
def test_dialogue_event_emits_signal():
    """
    Processing a DialogueEvent should emit the dialogue_event_processed signal.
    
    This is critical for connecting queue processing to UI updates.
    """
    DIALOGUE_EVENTS_RECEIVED.clear()
    
    location = Location.objects.create(name="Test Location")
    ship = Ship.objects.create(name="Test Ship", current_location=location)
    pilot = Pilot.create(ship=ship)
    pilot.name = "Test Pilot"
    pilot.save()
    
    queue = SimulationQueue()
    event = DialogueEvent(
        timestamp=5.0,
        actor=pilot,
        text="Control, this is Test Ship, requesting status.",
        duration=2.0,
        event_type="dialogue",
    )
    
    queue.add_event(event)
    queue.process_due_events(5.1)
    
    assert len(DIALOGUE_EVENTS_RECEIVED) == 1
    assert DIALOGUE_EVENTS_RECEIVED[0].actor == pilot
    assert "requesting status" in DIALOGUE_EVENTS_RECEIVED[0].text
