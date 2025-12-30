"""
Audio worker tests.

Tests worker behavior:
- Audio processing workflow
- Error handling and robustness
- TTS failure handling
- Graceful degradation when resources unavailable
"""
import pytest
from unittest.mock import Mock, patch
from django.utils import timezone

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale
from mysite.universe.services.audio_cache import AudioCache, AudioJobQueue, AudioWorker, AudioJob
from mysite.universe.views.events import _get_audio_cache, _get_audio_queue, _ensure_worker


@pytest.mark.django_db(transaction=True)
def test_worker_handles_tts_exception_gracefully():
    """Worker should log errors and mark job complete even if TTS fails."""
    cache = AudioCache(capacity=10)
    queue = AudioJobQueue(capacity=10)
    
    # Mock TTS service to raise exception
    with patch("mysite.universe.services.audio_cache.get_tts_service") as mock_get_svc:
        mock_svc = Mock()
        mock_svc.generate.side_effect = Exception("TTS service unavailable")
        mock_get_svc.return_value = mock_svc
        
        worker = AudioWorker(cache=cache, queue=queue)
        worker.start()
        
        # Enqueue a job
        job = AudioJob(event_id=999, text="Test text", voice_id="test_voice")
        queue.enqueue(job)
        
        # Wait for worker to process (with timeout)
        import time
        for _ in range(50):  # 5 seconds max
            if job.event_id not in queue._inflight:
                break
            time.sleep(0.1)
        
        # Job should be marked complete (even though it failed)
        assert job.event_id not in queue._inflight
        # But cache should NOT have the entry
        assert cache.get(999) is None
        
        worker.stop()
        # Give worker time to exit (don't call join - it conflicts with _stop Event)
        time.sleep(0.2)


@pytest.mark.django_db(transaction=True)
def test_worker_handles_missing_voice_file():
    """Worker should handle FileNotFoundError when voice file doesn't exist."""
    cache = AudioCache(capacity=10)
    queue = AudioJobQueue(capacity=10)
    
    with patch("mysite.universe.services.audio_cache.get_tts_service") as mock_get_svc:
        mock_svc = Mock()
        mock_svc.generate.side_effect = FileNotFoundError("Voice file not found: pilot_default")
        mock_get_svc.return_value = mock_svc
        
        worker = AudioWorker(cache=cache, queue=queue)
        worker.start()
        
        job = AudioJob(event_id=888, text="Test", voice_id="nonexistent_voice")
        queue.enqueue(job)
        
        import time
        for _ in range(50):
            if job.event_id not in queue._inflight:
                break
            time.sleep(0.1)
        
        assert cache.get(888) is None
        worker.stop()
        # Give worker time to exit (don't call join - it conflicts with _stop Event)
        time.sleep(0.2)


@pytest.mark.django_db(transaction=True)
def test_event_with_failed_tts_never_gets_audio_ready():
    """If TTS fails, event should never report audio_ready=True."""
    from mysite.universe.views import events as events_views
    
    # Create minimal test data
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    
    # Mock TTS to always fail
    with patch("mysite.universe.services.audio_cache.get_tts_service") as mock_get_svc:
        mock_svc = Mock()
        mock_svc.generate.side_effect = Exception("TTS failed")
        mock_get_svc.return_value = mock_svc
        
        # Create event
        ev = DialogueEventLog.objects.create(
            actor_name=pilot.name,
            text="Test dialogue",
            timestamp=timezone.now().timestamp(),
            metadata={"actor_id": pilot.id},
        )
        
        # Enqueue (this will fail silently)
        events_views._prefetch_audio_for_events([ev])
        
        # Manually drain worker once
        queue = events_views._get_audio_queue()
        cache = events_views._get_audio_cache()
        
        # Simulate worker processing (will fail)
        job = queue.pop()
        if job:
            try:
                mock_svc.generate(text=job.text, voice_id=job.voice_id)
            except Exception:
                pass  # Expected
            finally:
                queue.complete(job)
        
        # Check that audio is NOT ready
        entry = cache.get(ev.id)
        assert entry is None
        
        # event_feed should report audio_ready=False
        from django.test import Client
        client = Client()
        resp = client.get(f"/api/events/?limit=10&after_ts=0")
        assert resp.status_code == 200
        data = resp.json()
        event_data = next((e for e in data["events"] if e["id"] == ev.id), None)
        if event_data:
            assert event_data["audio_ready"] is False


@pytest.mark.django_db(transaction=True)
def test_actor_without_profile_does_not_crash():
    """Looking up audio_profile for actor without profile should not raise."""
    from mysite.universe.views import events as events_views
    
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    
    # Delete the profile (simulate missing profile)
    if hasattr(pilot, "audio_profile"):
        pilot.audio_profile.delete()
    
    ev = DialogueEventLog.objects.create(
        actor_name=pilot.name,
        text="Test",
    timestamp=timezone.now().timestamp(),
    metadata={"actor_id": pilot.id},
    )
    
    # This should not raise RelatedObjectDoesNotExist
    try:
        events_views._prefetch_audio_for_events([ev])
    except Exception as e:
        if "RelatedObjectDoesNotExist" in str(type(e)):
            pytest.fail(f"Should handle missing profile gracefully: {e}")
        raise  # Other exceptions are fine to raise

