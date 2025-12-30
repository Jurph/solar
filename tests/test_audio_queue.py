from mysite.universe.services.audio_cache import AudioJob, AudioJobQueue, AudioCache, AudioEntry, EnqueueResult
import time
from django.test import RequestFactory
from django.db import transaction
from django.utils import timezone
import pytest
from mysite.universe.models.actor import Actor


def test_queue_dedup_and_capacity():
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


def test_cache_put_eviction():
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


def test_event_audio_view_serves_cached(monkeypatch):
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
def test_prefetch_skips_cached(monkeypatch):
    from mysite.universe import views as universe_views
    from mysite.universe.views import events as events_views
    from mysite.universe.models.event import DialogueEventLog

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
        actor_a = Actor.create(name="A")
        actor_b = Actor.create(name="B")
        ev1 = DialogueEventLog.objects.create(timestamp=timezone.now().timestamp(), actor=actor_a, text="hello")
        ev2 = DialogueEventLog.objects.create(timestamp=timezone.now().timestamp(), actor=actor_b, text="world")

    fake_cache.put(AudioEntry(event_id=ev1.id, voice_id="v1", duration_s=1.0, wav_bytes=b"x", created_at=time.time()))

    # Ignore any enqueues from post_save; we only care about additional enqueues here
    captured.clear()
    events_views._prefetch_audio_for_events([ev1, ev2])

    # Only ev2 should be enqueued (ev1 already cached)
    assert len(captured) == 1
    assert captured[0].event_id == ev2.id

