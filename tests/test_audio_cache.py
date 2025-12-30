"""
Unified audio cache and queue tests.

Tests cache/queue mechanics:
- AudioJobQueue: deduplication, capacity, statistics
- AudioCache: put/get, eviction, capacity management
- Cache serving: event_audio endpoint integration
- Prefetch horizon: time-based event selection
"""
import time
import pytest
from django.test import RequestFactory, Client
from django.db import transaction
from django.utils import timezone
from unittest.mock import patch

from mysite.universe.services.audio_cache import AudioJob, AudioJobQueue, AudioCache, AudioEntry, EnqueueResult
from mysite.universe.models.actor import Actor, Pilot
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale


class TestAudioJobQueue:
    """Test queue operations: enqueue, dedup, capacity, statistics."""

    def test_queue_dedup_and_capacity(self):
        q = AudioJobQueue(capacity=2)
        assert q.enqueue(AudioJob(event_id=1, text="a", voice_id="v1")) == EnqueueResult.SUCCESS
        assert q.enqueue(AudioJob(event_id=1, text="dup", voice_id="v1")) == EnqueueResult.DUPLICATE
        assert q.enqueue(AudioJob(event_id=2, text="b", voice_id="v2")) == EnqueueResult.SUCCESS
        assert q.enqueue(AudioJob(event_id=3, text="c", voice_id="v3")) == EnqueueResult.QUEUE_FULL  # dropped due to capacity

        jobs = [q.pop(), q.pop(), q.pop()]
        assert jobs[0].event_id == 1
        assert jobs[1].event_id == 2
        assert jobs[2] is None

        q.complete(jobs[0])
        q.complete(jobs[1])
        
        # Verify statistics
        stats = q.get_stats()
        assert stats['rejects_duplicate'] == 1
        assert stats['rejects_full'] == 1


class TestAudioCache:
    """Test cache operations: put, get, eviction, capacity management."""

    def test_cache_put_eviction(self):
        cache = AudioCache(capacity=2)
        assert cache.put(AudioEntry(event_id=1, voice_id="v1", duration_s=1.0, wav_bytes=b"a", created_at=time.time())) is True
        assert cache.put(AudioEntry(event_id=2, voice_id="v2", duration_s=1.0, wav_bytes=b"b", created_at=time.time())) is True
        assert cache.put(AudioEntry(event_id=3, voice_id="v3", duration_s=1.0, wav_bytes=b"c", created_at=time.time())) is True

        assert cache.get(1) is None  # evicted
        assert cache.get(2) is not None
        assert cache.get(3) is not None
        
        # Verify statistics
        stats = cache.get_stats()
        assert stats['evictions'] == 1
        assert stats['cached'] == 2
        assert stats['capacity'] == 2

    def test_cache_eviction_removes_old_entries(self):
        """Cache should evict oldest entries when capacity is exceeded."""
        cache = AudioCache(capacity=3)  # Small capacity for testing
        
        # Add 4 entries (one more than capacity)
        for i in range(4):
            entry = AudioEntry(
                event_id=i,
                voice_id="test_voice",
                duration_s=1.0,
                wav_bytes=b"fake_wav_data",
                created_at=timezone.now().timestamp() + i
            )
            cache.put(entry)
        
        # First entry (event_id=0) should be evicted
        assert cache.get(0) is None
        # Last 3 entries should still be present
        assert cache.get(1) is not None
        assert cache.get(2) is not None
        assert cache.get(3) is not None


class TestAudioCacheServing:
    """Test cache serving through view endpoints."""

    def test_event_audio_view_serves_cached(self, monkeypatch):
        from mysite.universe.views import events as events_views

        # Set a known cache
        cache = AudioCache(capacity=2)
        cache.put(AudioEntry(event_id=42, voice_id="v1", duration_s=1.0, wav_bytes=b"abc", created_at=time.time()))

        # Monkeypatch cache getter to return our cache
        monkeypatch.setattr(events_views, "_audio_cache", cache)
        rf = RequestFactory()
        resp = events_views.event_audio(rf.get("/api/event_audio/42/"), event_id=42)
        assert resp.status_code == 200
        assert resp.content == b"abc"

        resp_missing = events_views.event_audio(rf.get("/api/event_audio/43/"), event_id=43)
        assert resp_missing.status_code == 404

    @pytest.mark.django_db(transaction=True)
    def test_evicted_event_returns_404(self):
        """Event_audio endpoint should return 404 for evicted entries."""
        from mysite.universe.views import events as events_views
        
        # Create event and add to cache
        loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
        ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
        pilot = Pilot.create(ship=ship)
        
        ev = DialogueEventLog.objects.create(
            actor=pilot,
            text="Test",
            timestamp=timezone.now().timestamp(),
        )
        
        cache = events_views._get_audio_cache()
        entry = AudioEntry(
            event_id=ev.id,
            voice_id="test_voice",
            duration_s=1.0,
            wav_bytes=b"fake_wav",
            created_at=timezone.now().timestamp()
        )
        cache.put(entry)
        
        # Verify it's accessible
        client = Client()
        resp = client.get(f"/api/event_audio/{ev.id}/")
        assert resp.status_code == 200
        
        # Evict it by filling cache past capacity
        for i in range(cache.capacity + 1):
            other_entry = AudioEntry(
                event_id=1000 + i,
                voice_id="test_voice",
                duration_s=1.0,
                wav_bytes=b"fake_wav",
                created_at=timezone.now().timestamp() + i
            )
            cache.put(other_entry)
        
        # Original entry should be evicted
        assert cache.get(ev.id) is None
        
        # Endpoint should return 404
        resp = client.get(f"/api/event_audio/{ev.id}/")
        assert resp.status_code == 404

    @pytest.mark.django_db(transaction=True)
    def test_event_feed_reports_false_for_evicted_audio(self):
        """event_feed should report audio_ready=False for evicted entries."""
        from mysite.universe.views import events as events_views
        from mysite.universe.models.simulation import get_simulation_time
        
        loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
        ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
        pilot = Pilot.create(ship=ship)
        
        ev = DialogueEventLog.objects.create(
            actor=pilot,
            text="Test",
            timestamp=get_simulation_time() + 1.0,  # Future event
        )
        
        cache = events_views._get_audio_cache()
        entry = AudioEntry(
            event_id=ev.id,
            voice_id="test_voice",
            duration_s=1.0,
            wav_bytes=b"fake_wav",
            created_at=timezone.now().timestamp()
        )
        cache.put(entry)
        
        # Evict it
        for i in range(cache.capacity + 1):
            other_entry = AudioEntry(
                event_id=2000 + i,
                voice_id="test_voice",
                duration_s=1.0,
                wav_bytes=b"fake_wav",
                created_at=timezone.now().timestamp() + i
            )
            cache.put(other_entry)
        
        # Patch sim time to include our event
        with patch("mysite.universe.models.simulation.get_simulation_time", return_value=ev.timestamp + 1.0):
            client = Client()
            resp = client.get(f"/api/events/?limit=10&after_ts=0")
            assert resp.status_code == 200
            data = resp.json()
            event_data = next((e for e in data["events"] if e["id"] == ev.id), None)
            if event_data:
                assert event_data["audio_ready"] is False
                assert event_data["audio_url"] is None


class TestAudioPrefetchHorizon:
    """Test time-based event selection for prefetch horizon."""

    @pytest.mark.django_db(transaction=True)
    def test_select_upcoming_respects_horizon(self, monkeypatch):
        from mysite.universe.views import events as events_views
        
        # Horizon set small to make test deterministic
        monkeypatch.setattr(events_views, "_AUDIO_PREFETCH_HORIZON_SECONDS", 60.0)
        monkeypatch.setattr(events_views, "_AUDIO_PREFETCH_MAX_EVENTS", 10)

        now = timezone.now().timestamp()
        actor_a = Actor.create(name="A")
        actor_b = Actor.create(name="B")
        actor_c = Actor.create(name="C")
        # inside horizon
        ev1 = DialogueEventLog.objects.create(timestamp=now + 10, actor=actor_a, text="t1")
        ev2 = DialogueEventLog.objects.create(timestamp=now + 30, actor=actor_b, text="t2")
        # outside horizon
        ev3 = DialogueEventLog.objects.create(timestamp=now + 120, actor=actor_c, text="t3")

        res = list(events_views._select_upcoming_events(sim_time=now, limit=10))
        ids = [e.id for e in res]

        assert ev1.id in ids
        assert ev2.id in ids
        assert ev3.id not in ids

