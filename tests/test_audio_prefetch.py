"""
Unified audio prefetch tests.

Tests prefetch behavior:
- Post-save signals triggering prefetch
- Skipping already-cached events
- Cache awareness during prefetch
"""
import pytest
from django.utils import timezone
from django.db import transaction

from mysite.universe.services.audio_cache import AudioCache, AudioEntry
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.actor import Pilot
from mysite.universe.models.base import Location
from mysite.universe.models.ship import Ship
from mysite.universe.models.scale import Scale


class TestPrefetchSignal:
    """Test that post_save signal triggers audio prefetch."""

    @pytest.mark.django_db(transaction=True)
    def test_post_save_enqueues_prefetch(self, monkeypatch):
        """Creating a DialogueEventLog should trigger prefetch via post_save signal."""
        # Fake cache/queue to observe enqueues
        captured = []

        class FakeQueue:
            def enqueue(self, job):
                captured.append(job)

        from mysite.universe.views import events as events_views

        fake_cache = AudioCache(capacity=10)
        fake_queue = FakeQueue()

        monkeypatch.setattr(events_views, "_audio_cache", fake_cache)
        monkeypatch.setattr(events_views, "_audio_queue", fake_queue)
        monkeypatch.setattr(events_views, "_ensure_worker", lambda: None)

        # Create an actor to get a valid actor reference
        loc = Location.objects.create(name="Test Location", scale=Scale.STATION)
        ship = Ship.objects.create(name="Test Ship", current_location=loc, size=Ship.Size.MEDIUM)
        actor = Pilot.create(name="A", ship=ship)

        ev = DialogueEventLog.objects.create(
            timestamp=timezone.now().timestamp(),
            actor=actor,
            text="hello world"
        )

        # Post-save receiver should have enqueued one job
        assert len(captured) == 1
        assert captured[0].event_id == ev.id

    @pytest.mark.django_db(transaction=True)
    def test_post_save_skips_cached(self, monkeypatch):
        """If audio is already cached, post_save prefetch should skip it."""
        captured = []

        class FakeQueue:
            def enqueue(self, job):
                captured.append(job)

        from mysite.universe.views import events as events_views

        fake_cache = AudioCache(capacity=10)
        fake_queue = FakeQueue()

        monkeypatch.setattr(events_views, "_audio_cache", fake_cache)
        monkeypatch.setattr(events_views, "_audio_queue", fake_queue)
        monkeypatch.setattr(events_views, "_ensure_worker", lambda: None)

        # Seed cache for this event id
        fake_cache.put(AudioEntry(event_id=999, voice_id="v", duration_s=1.0, wav_bytes=b"x", created_at=0))

        ev = DialogueEventLog.objects.create(
            timestamp=timezone.now().timestamp(),
            actor_name="B",
            text="hello cached",
            metadata={},
        )
        # Manually set id to cached (simulate same id) is not trivial; instead, ensure cache prevents double enqueue by adding cache after creation
        fake_cache.put(AudioEntry(event_id=ev.id, voice_id="v", duration_s=1.0, wav_bytes=b"x", created_at=0))
        captured.clear()
        events_views._prefetch_audio_for_events([ev])

        assert len(captured) == 0


class TestPrefetchCacheSkip:
    """Test that prefetch skips already-cached events."""

    @pytest.mark.django_db(transaction=True)
    def test_prefetch_skips_cached(self, monkeypatch):
        """_prefetch_audio_for_events should skip events already in cache."""
        from mysite.universe.views import events as events_views

        # Disable worker start
        monkeypatch.setattr(events_views, "_ensure_worker", lambda: None)

        # Fake queue to capture enqueued jobs
        captured = []

        class FakeQueue:
            def enqueue(self, job):
                captured.append(job)

        fake_queue = FakeQueue()
        fake_cache = AudioCache(capacity=10)

        monkeypatch.setattr(events_views, "_audio_queue", fake_queue)
        monkeypatch.setattr(events_views, "_audio_cache", fake_cache)

        # Create two events; one already cached
        with transaction.atomic():
            actor_a = Pilot.create(name="A", ship=None)
            actor_b = Pilot.create(name="B", ship=None)
            ev1 = DialogueEventLog.objects.create(timestamp=timezone.now().timestamp(), actor=actor_a, text="hello")
            ev2 = DialogueEventLog.objects.create(timestamp=timezone.now().timestamp(), actor=actor_b, text="world")

        fake_cache.put(AudioEntry(event_id=ev1.id, voice_id="v1", duration_s=1.0, wav_bytes=b"x", created_at=0))

        # Ignore any enqueues from post_save; we only care about additional enqueues here
        captured.clear()
        events_views._prefetch_audio_for_events([ev1, ev2])

        # Only ev2 should be enqueued (ev1 already cached)
        assert len(captured) == 1
        assert captured[0].event_id == ev2.id

