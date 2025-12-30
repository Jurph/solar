import pytest
from django.utils import timezone

from mysite.universe.services.audio_cache import AudioCache, AudioEntry
from mysite.universe.models.event import DialogueEventLog


@pytest.mark.django_db(transaction=True)
def test_post_save_enqueues_prefetch(monkeypatch):
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

    ev = DialogueEventLog.objects.create(
        timestamp=timezone.now().timestamp(),
        actor_name="A",
        text="hello world",
        metadata={},
    )

    # Post-save receiver should have enqueued one job
    assert len(captured) == 1
    assert captured[0].event_id == ev.id


@pytest.mark.django_db(transaction=True)
def test_post_save_skips_cached(monkeypatch):
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

