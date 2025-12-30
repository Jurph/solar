"""
Test audio cache eviction and client handling of evicted entries.
"""
import pytest
from unittest.mock import patch
from django.utils import timezone
from django.test import Client

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.actor import Pilot
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale
from mysite.universe.services.audio_cache import AudioCache, AudioEntry
from mysite.universe.views.events import _get_audio_cache


@pytest.mark.django_db(transaction=True)
def test_cache_eviction_removes_old_entries():
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


@pytest.mark.django_db(transaction=True)
def test_evicted_event_returns_404():
    """Event_audio endpoint should return 404 for evicted entries."""
    from mysite.universe.views import events as events_views
    
    # Create event and add to cache
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    
    ev = DialogueEventLog.objects.create(
        actor_name=pilot.name,
        text="Test",
        timestamp=timezone.now().timestamp()
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
def test_event_feed_reports_false_for_evicted_audio():
    """event_feed should report audio_ready=False for evicted entries."""
    from mysite.universe.views import events as events_views
    from mysite.universe.models.simulation import get_simulation_time
    
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    
    ev = DialogueEventLog.objects.create(
        actor_name=pilot.name,
        text="Test",
        timestamp=get_simulation_time() + 1.0  # Future event
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

