"""
Tests for the event_feed API endpoint.

These tests verify the core business logic:
- Time-gating: only events with timestamp <= sim_time are returned
- Pagination: after_id correctly filters for incremental updates
- Error handling: invalid inputs are handled gracefully
"""

import io
import time
import wave

from django.test import TestCase, Client

from mysite.universe.models.actor import Controller, Satellite
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
            time_scale=1.0,
        )

    def test_past_events_returned_future_events_hidden(self):
        """
        Events in the "past" (timestamp <= sim_time) should be returned.
        Events in the "future" (timestamp > sim_time) should be hidden.

        If this fails: the timestamp filtering in event_feed is broken,
        and events will appear at wrong times or all at once.
        """
        actor = Controller.objects.create(name="Test")
        # Create one past event and one future event
        DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100,  # 100 seconds in past
            actor=actor,
            actor_name="Past Pilot",
            text="This happened already",
        )
        DialogueEventLog.objects.create(
            timestamp=self.base_sim_time + 1000,  # 1000 seconds in future
            actor=actor,
            actor_name="Future Pilot",
            text="This hasn't happened yet",
        )

        response = self.client.get("/api/events/")
        data = response.json()

        # Should only get the past event
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["actor_name"], "Past Pilot")

        # Debug info should show 1 pending, 1 available
        self.assertEqual(data["debug"]["pending_events"], 1)
        self.assertEqual(data["debug"]["available_events"], 1)


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
            time_scale=1.0,
        )

        self.actor = Controller.objects.create(name="Test")
        # Create 3 events in the past
        self.event1 = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 300,
            actor=self.actor,
            actor_name="Pilot 1",
            text="First message",
        )
        self.event2 = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 200,
            actor=self.actor,
            actor_name="Pilot 2",
            text="Second message",
        )
        self.event3 = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100,
            actor=self.actor,
            actor_name="Pilot 3",
            text="Third message",
        )

    def test_after_id_returns_only_newer_events(self):
        """
        Requesting with a (timestamp, id) cursor should skip events at/before the cursor.

        If this fails: clients will see duplicate events on each poll,
        causing the display to repeat messages.
        """
        # Get events after first one (cursor at event1)
        response = self.client.get(
            f"/api/events/?after_ts={self.event1.timestamp}&after_id={self.event1.id}"
        )
        data = response.json()

        # Should get events 2 and 3 only
        self.assertEqual(len(data["events"]), 2)
        self.assertEqual(data["events"][0]["actor_name"], "Pilot 2")
        self.assertEqual(data["events"][1]["actor_name"], "Pilot 3")

    def test_after_id_with_no_newer_events_returns_empty(self):
        """
        If no events exist after the given ID, return empty list.

        This is the normal case when polling and no new events have arrived.
        """
        response = self.client.get(
            f"/api/events/?after_ts={self.event3.timestamp}&after_id={self.event3.id}"
        )
        data = response.json()

        self.assertEqual(len(data["events"]), 0)
        self.assertIsNone(data["latest_id"])

    def test_invalid_after_id_returns_all_events(self):
        """
        after_id requires after_ts; an invalid after_id should be rejected.

        This ensures malformed requests don't silently produce confusing pagination.
        """
        response = self.client.get("/api/events/?after_ts=0&after_id=invalid")
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
        actor = Controller.objects.create(name="Test")
        # Create some events
        for i in range(5):
            DialogueEventLog.objects.create(
                timestamp=float(i * 100),
                actor=actor,
                actor_name=f"Pilot {i}",
                text=f"Message {i}",
            )

        self.assertEqual(DialogueEventLog.objects.count(), 5)

        response = self.client.post("/api/clear-events/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("5", data["message"])
        self.assertEqual(DialogueEventLog.objects.count(), 0)

    def test_clear_events_requires_post(self):
        """
        clear_events should reject GET requests.

        This prevents accidental data deletion from browser navigation.
        """
        response = self.client.get("/api/clear-events/")
        self.assertEqual(response.status_code, 405)


class EventMetadataTests(TestCase):
    """
    Tests for metadata field handling in events.

    The metadata field stores additional structured data (e.g., modem_data for nav broadcasts).
    These tests verify that metadata is correctly stored and returned in the API.
    """

    def setUp(self):
        """Set up test client and simulation state."""
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()

        self.base_sim_time = 10000.0
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=self.base_sim_time,
            anchor_wall_clock=time.time(),
            time_scale=1.0,
        )

    def test_event_with_metadata_is_stored_and_returned(self):
        """
        Events with metadata should be stored and returned correctly.

        This test would fail if the metadata field migration hasn't been applied,
        as it would raise OperationalError when trying to create an event with metadata.
        """
        actor = Controller.objects.create(name="Test")
        # Create an event with metadata (e.g., nav broadcast with modem_data)
        event = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100,
            actor=actor,
            actor_name="Test Satellite",
            text="All stations, this is TEST with a Navigation Update.",
            metadata={
                "type": "nav_broadcast",
                "satellite_name": "TEST",
                "modem_data": "TEST NAV UPDATE // POS 45.0 90.0 ALT 500KM // STATUS NOM",
            },
        )

        # Verify the event was created with metadata
        self.assertIsNotNone(event.metadata)
        self.assertEqual(event.metadata["type"], "nav_broadcast")
        self.assertIn("modem_data", event.metadata)

        # Request the event via API
        response = self.client.get("/api/events/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify metadata is returned in the API response
        self.assertEqual(len(data["events"]), 1)
        returned_event = data["events"][0]
        self.assertIn("metadata", returned_event)
        self.assertEqual(returned_event["metadata"]["type"], "nav_broadcast")
        self.assertIn("modem_data", returned_event["metadata"])

    def test_event_without_metadata_has_empty_dict(self):
        """
        Events without metadata should have an empty dict, not None.

        This ensures backward compatibility and consistent API responses.
        """
        actor = Controller.objects.create(name="Test2")
        # Create an event without metadata
        event = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100,
            actor=actor,
            actor_name="Test Pilot",
            text="Regular dialogue message",
        )

        # Verify metadata defaults to empty dict
        self.assertEqual(event.metadata, {})

        # Request the event via API
        response = self.client.get("/api/events/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify metadata is returned as empty dict in API response
        self.assertEqual(len(data["events"]), 1)
        returned_event = data["events"][0]
        self.assertIn("metadata", returned_event)
        self.assertEqual(returned_event["metadata"], {})


class EventFeedAudioPlanRobustnessTests(TestCase):
    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()

        self.base_sim_time = 10000.0
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=self.base_sim_time,
            anchor_wall_clock=time.time(),
            time_scale=1.0,
        )

    def test_event_feed_does_not_500_when_duplicate_satellite_names_exist(self):
        """
        Regression test: Actor names are not unique. Duplicate Satellite names previously
        caused /api/events/ to 500 when audio plans were generated via .get(name=...).

        Now we use actor_id from metadata, so duplicate names don't cause issues.
        Satellites get both quindars and modem noise.
        """
        sat1 = Satellite.objects.create(name="DUP SAT")
        Satellite.objects.create(name="DUP SAT")

        DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 10.0,
            actor=sat1,
            actor_name="DUP SAT",
            text="NAV UPDATE",
            metadata={"type": "nav_broadcast", "modem_data": "HELLO"},
        )

        response = self.client.get("/api/events/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["events"]), 1)
        self.assertIn("audio_plan", data["events"][0])

        # Verify we got an audio plan with expected satellite elements
        presets = [a.get("preset") for a in data["events"][0]["audio_plan"]]
        # Satellites should have modem noise AND quindars
        self.assertIn(
            "modem_noise_example", presets, "Satellites should have modem noise"
        )
        # At least one quindar (start or end)
        has_quindar = any("quindar" in str(p) for p in presets)
        self.assertTrue(has_quindar, "Satellites should have quindar tones")


class EventFeedAudioReadyFlagTests(TestCase):
    """
    Integration tests for the audio_ready flag in event_feed API.

    The audio_ready flag tells the frontend whether audio has been pre-generated
    by the worker. This enables the frontend to poll efficiently and display
    appropriate loading states.
    """

    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()

        self.base_sim_time = 10000.0
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=self.base_sim_time,
            anchor_wall_clock=time.time(),
            time_scale=1.0,
        )
        self.actor = Satellite.objects.create(name="Test Satellite")

    def _create_minimal_wav(self) -> bytes:
        """Create a minimal valid WAV file for testing."""
        import io
        import wave

        with io.BytesIO() as buf:
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00" * (22050 // 10 * 2))
            return buf.getvalue()

    def test_event_feed_audio_ready_flag_matches_file_existence(self):
        """
        Integration test: audio_ready flag should accurately reflect worker status.

        This validates the web server's view of worker-generated audio:
        - Events with audio_file → audio_ready=true
        - Events without audio_file → audio_ready=false

        This is critical for frontend to know when to request audio vs. wait.
        """
        from django.core.files.base import ContentFile
        from django.utils import timezone

        # Event 1: No audio generated yet
        event_pending = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 200,
            actor=self.actor,
            actor_name=self.actor.name,
            text="Message 1: Audio pending",
        )

        # Event 2: Audio generated by worker
        event_ready = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100,
            actor=self.actor,
            actor_name=self.actor.name,
            text="Message 2: Audio ready",
        )
        wav_bytes = self._create_minimal_wav()
        event_ready.audio_file.save(
            f"event_{event_ready.id}.wav", ContentFile(wav_bytes)
        )
        event_ready.audio_rendered_at = timezone.now()
        event_ready.save()

        # Request event feed
        response = self.client.get("/api/events/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should get both events
        self.assertEqual(len(data["events"]), 2)

        # Find events in response
        event_pending_data = next(
            e for e in data["events"] if e["id"] == event_pending.id
        )
        event_ready_data = next(e for e in data["events"] if e["id"] == event_ready.id)

        # Verify audio_ready flags
        self.assertFalse(
            event_pending_data.get("audio_ready", False),
            "Event without audio_file should have audio_ready=false",
        )
        self.assertTrue(
            event_ready_data.get("audio_ready", False),
            "Event with audio_file should have audio_ready=true",
        )

        # Verify audio URLs are present for both
        self.assertIn("audio_url", event_pending_data)
        self.assertIn("audio_url", event_ready_data)


class EventFeedLimitValidationTests(TestCase):
    """
    Tests for the limit parameter contract in event_feed.

    Intended behavior:
    - limit=0  → 200 with empty events list (accepted special case)
    - limit=-1 → 400 (negative limits are not acceptable)
    - limit=abc → 400 (non-integer limits are not acceptable)
    """

    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=10000.0,
            anchor_wall_clock=time.time(),
            time_scale=1.0,
        )
        actor = Controller.objects.create(name="Test")
        for i in range(3):
            DialogueEventLog.objects.create(
                timestamp=9000.0 + i,
                actor=actor,
                actor_name=f"Pilot {i}",
                text=f"Message {i}",
            )

    def test_limit_zero_returns_200_with_empty_list(self):
        """limit=0 is an accepted special case: returns 200 with zero events."""
        response = self.client.get("/api/events/?limit=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["events"]), 0)

    def test_limit_negative_returns_400(self):
        """Negative limit must be rejected with a 400-class error."""
        response = self.client.get("/api/events/?limit=-1")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "error")

    def test_limit_non_integer_returns_400(self):
        """Non-integer limit must be rejected with a 400-class error."""
        response = self.client.get("/api/events/?limit=abc")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "error")

    def test_limit_large_float_string_returns_400(self):
        """Floats are not integers; '2.5' must be rejected."""
        response = self.client.get("/api/events/?limit=2.5")
        self.assertEqual(response.status_code, 400)


class EventFeedMethodTests(TestCase):
    """The event feed is a read-only API and should reject non-GET methods."""

    def test_post_rejected(self):
        response = self.client.post("/api/events/")
        self.assertEqual(response.status_code, 405)


class EventFeedTimestampTieBreakTests(TestCase):
    """
    Tests for cursor behavior when two events share the same timestamp.

    The cursor is (timestamp, id).  When ts values are equal, id is the
    tie-breaker.  Events with id <= cursor_id at cursor_ts must be excluded.
    """

    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()
        self.base_sim_time = 10000.0
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=self.base_sim_time,
            anchor_wall_clock=time.time(),
            time_scale=1.0,
        )

    def test_cursor_at_first_of_duplicate_timestamps_skips_it(self):
        """
        Given two events at the same timestamp, a cursor at (ts, id_A)
        must return only event_B (the one with the higher id).
        """
        actor = Controller.objects.create(name="Test")
        shared_ts = self.base_sim_time - 100.0
        event_a = DialogueEventLog.objects.create(
            timestamp=shared_ts, actor=actor, actor_name="Pilot A", text="First"
        )
        event_b = DialogueEventLog.objects.create(
            timestamp=shared_ts, actor=actor, actor_name="Pilot B", text="Second"
        )

        response = self.client.get(
            f"/api/events/?after_ts={shared_ts}&after_id={event_a.id}"
        )
        data = response.json()
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["id"], event_b.id)

    def test_cursor_past_all_duplicate_timestamps_returns_empty(self):
        """
        A cursor at (ts, id_B) — the last event at that timestamp —
        returns an empty list.
        """
        actor = Controller.objects.create(name="Test2")
        shared_ts = self.base_sim_time - 100.0
        DialogueEventLog.objects.create(
            timestamp=shared_ts, actor=actor, actor_name="Pilot A", text="First"
        )
        event_b = DialogueEventLog.objects.create(
            timestamp=shared_ts, actor=actor, actor_name="Pilot B", text="Second"
        )

        response = self.client.get(
            f"/api/events/?after_ts={shared_ts}&after_id={event_b.id}"
        )
        data = response.json()
        self.assertEqual(len(data["events"]), 0)

    def test_mixed_timestamps_cursor_at_first_returns_remaining(self):
        """
        Three events: two share a timestamp, one is later.
        Cursor at the first shared-ts event must return the other two.
        """
        actor = Controller.objects.create(name="Test3")
        shared_ts = self.base_sim_time - 200.0
        later_ts = self.base_sim_time - 100.0
        event_a = DialogueEventLog.objects.create(
            timestamp=shared_ts, actor=actor, actor_name="Pilot A", text="First"
        )
        event_b = DialogueEventLog.objects.create(
            timestamp=shared_ts, actor=actor, actor_name="Pilot B", text="Second"
        )
        event_c = DialogueEventLog.objects.create(
            timestamp=later_ts, actor=actor, actor_name="Pilot C", text="Third"
        )

        response = self.client.get(
            f"/api/events/?after_ts={shared_ts}&after_id={event_a.id}"
        )
        data = response.json()
        returned_ids = {e["id"] for e in data["events"]}
        self.assertIn(event_b.id, returned_ids)
        self.assertIn(event_c.id, returned_ids)
        self.assertNotIn(event_a.id, returned_ids)


class EventFeedAudioReadyCacheTests(TestCase):
    """
    Tests for audio_ready flag when the Django cache is the source of truth.

    The feed's audio_ready flag is True when EITHER audio_file is set
    OR the cache has mixed audio for that event.  These tests verify the
    cache branch specifically.
    """

    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        SimulationState.objects.all().delete()
        from django.core.cache import cache as django_cache

        django_cache.clear()
        self.base_sim_time = 10000.0
        SimulationState.objects.create(
            pk=1,
            anchor_sim_time=self.base_sim_time,
            anchor_wall_clock=time.time(),
            time_scale=1.0,
        )

    def test_audio_ready_true_when_only_cache_has_audio(self):
        """audio_ready=True when no audio_file but cache holds mixed audio."""
        from django.core.cache import cache as django_cache

        actor = Controller.objects.create(name="CacheTest")
        event = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100.0,
            actor=actor,
            actor_name="Cached Pilot",
            text="Cached.",
        )
        # Populate cache; leave audio_file blank
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(b"\x00" * 100)
        django_cache.set(f"mixed_audio:{event.id}", buf.getvalue())

        response = self.client.get("/api/events/")
        data = response.json()
        event_data = next(e for e in data["events"] if e["id"] == event.id)
        self.assertTrue(event_data["audio_ready"])

    def test_audio_ready_false_when_no_file_and_no_cache(self):
        """audio_ready=False when neither audio_file nor cache has audio."""
        actor = Controller.objects.create(name="CacheTest2")
        event = DialogueEventLog.objects.create(
            timestamp=self.base_sim_time - 100.0,
            actor=actor,
            actor_name="Pending Pilot",
            text="Pending.",
        )

        response = self.client.get("/api/events/")
        data = response.json()
        event_data = next(e for e in data["events"] if e["id"] == event.id)
        self.assertFalse(event_data["audio_ready"])

    def test_post_clear_feed_is_empty_and_debug_reflects_state(self):
        """
        After clear_events, the event feed returns no events.
        debug.total_events must also report 0.
        """
        actor = Controller.objects.create(name="CacheTest3")
        for i in range(3):
            DialogueEventLog.objects.create(
                timestamp=self.base_sim_time - 100.0 * (i + 1),
                actor=actor,
                actor_name=f"Pilot {i}",
                text=f"Message {i}",
            )

        response = self.client.get("/api/events/")
        self.assertEqual(len(response.json()["events"]), 3)

        self.client.post("/api/clear-events/")

        response = self.client.get("/api/events/")
        data = response.json()
        self.assertEqual(len(data["events"]), 0)
        self.assertEqual(data["debug"]["total_events"], 0)


if __name__ == "__main__":
    import unittest

    unittest.main()
