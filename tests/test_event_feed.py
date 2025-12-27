"""
Tests for the event_feed API endpoint.

These tests verify the core business logic:
- Time-gating: only events with timestamp <= sim_time are returned
- Pagination: after_id correctly filters for incremental updates
- Error handling: invalid inputs are handled gracefully
"""
import time
from django.test import TestCase, Client

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.simulation import SimulationState


class EventTimeGatingTests(TestCase):
    """
    Tests for the core time-gating logic.
    
    The event feed should only return events whose timestamp has "arrived"
    according to simulation time. This is the fundamental mechanism that
    makes events appear gradually rather than all at once.
    """
    
    def setUp(self):
        """Set up test client and simulation state at known time."""
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()
        
        self.base_sim_time = 10000.0
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=self.base_sim_time,
            anchor_wall_clock=time.time(),
            time_scale=1.0
        )
    
    def test_past_events_returned_future_events_hidden(self):
        """
        Events in the "past" (timestamp <= sim_time) should be returned.
        Events in the "future" (timestamp > sim_time) should be hidden.
        
        If this fails: the timestamp filtering in event_feed is broken,
        and events will appear at wrong times or all at once.
        """
        # Create one past event and one future event
        DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100,  # 100 seconds in past
            actor_name="Past Pilot",
            text="This happened already"
        )
        DialogueEventLog.objects.create(
            timestamp=self.base_sim_time + 1000,  # 1000 seconds in future
            actor_name="Future Pilot",
            text="This hasn't happened yet"
        )
        
        response = self.client.get('/api/events/')
        data = response.json()
        
        # Should only get the past event
        self.assertEqual(len(data['events']), 1)
        self.assertEqual(data['events'][0]['actor_name'], "Past Pilot")
        
        # Debug info should show 1 pending, 1 available
        self.assertEqual(data['debug']['pending_events'], 1)
        self.assertEqual(data['debug']['available_events'], 1)


class EventPaginationTests(TestCase):
    """
    Tests for the after_id pagination mechanism.
    
    Clients track the last event ID they've seen and request
    only newer events. This prevents duplicates and enables
    efficient polling.
    """
    
    def setUp(self):
        """Set up test client and create multiple events."""
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()
        
        self.base_sim_time = 10000.0
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=self.base_sim_time,
            anchor_wall_clock=time.time(),
            time_scale=1.0
        )
        
        # Create 3 events in the past
        self.event1 = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 300,
            actor_name="Pilot 1",
            text="First message"
        )
        self.event2 = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 200,
            actor_name="Pilot 2",
            text="Second message"
        )
        self.event3 = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100,
            actor_name="Pilot 3",
            text="Third message"
        )
    
    def test_after_id_returns_only_newer_events(self):
        """
        Requesting with a (timestamp, id) cursor should skip events at/before the cursor.
        
        If this fails: clients will see duplicate events on each poll,
        causing the display to repeat messages.
        """
        # Get events after first one (cursor at event1)
        response = self.client.get(
            f'/api/events/?after_ts={self.event1.timestamp}&after_id={self.event1.id}'
        )
        data = response.json()
        
        # Should get events 2 and 3 only
        self.assertEqual(len(data['events']), 2)
        self.assertEqual(data['events'][0]['actor_name'], "Pilot 2")
        self.assertEqual(data['events'][1]['actor_name'], "Pilot 3")
    
    def test_after_id_with_no_newer_events_returns_empty(self):
        """
        If no events exist after the given ID, return empty list.
        
        This is the normal case when polling and no new events have arrived.
        """
        response = self.client.get(
            f'/api/events/?after_ts={self.event3.timestamp}&after_id={self.event3.id}'
        )
        data = response.json()
        
        self.assertEqual(len(data['events']), 0)
        self.assertIsNone(data['latest_id'])
    
    def test_invalid_after_id_returns_all_events(self):
        """
        after_id requires after_ts; an invalid after_id should be rejected.
        
        This ensures malformed requests don't silently produce confusing pagination.
        """
        response = self.client.get('/api/events/?after_ts=0&after_id=invalid')
        self.assertEqual(response.status_code, 400)


class ClearEventsTests(TestCase):
    """Tests for the clear_events API endpoint."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        DialogueEventLog.objects.all().delete()
    
    def test_clear_events_removes_all_and_returns_count(self):
        """
        clear_events should delete all events and report the count.
        
        This confirms the destructive operation actually works.
        """
        # Create some events
        for i in range(5):
            DialogueEventLog.objects.create(
                timestamp=float(i * 100),
                actor_name=f"Pilot {i}",
                text=f"Message {i}"
            )
        
        self.assertEqual(DialogueEventLog.objects.count(), 5)
        
        response = self.client.post('/api/clear-events/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('5', data['message'])
        self.assertEqual(DialogueEventLog.objects.count(), 0)
    
    def test_clear_events_requires_post(self):
        """
        clear_events should reject GET requests.
        
        This prevents accidental data deletion from browser navigation.
        """
        response = self.client.get('/api/clear-events/')
        self.assertEqual(response.status_code, 405)


if __name__ == '__main__':
    import unittest
    unittest.main()
