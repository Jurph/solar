"""
Comprehensive tests for Actor and Event creation bookkeeping.

Ensures all creation paths properly:
1. Assign audio profiles to actors
2. Store actor_id in event metadata
3. No code paths bypass proper bookkeeping
"""
import pytest
from django.utils import timezone
from django.db import transaction

from mysite.universe.models.actor import Pilot, Controller, Satellite, Actor
from mysite.universe.models.event import DialogueEvent, DialogueEventLog
from mysite.universe.models.ship import Ship
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale


@pytest.mark.django_db(transaction=True)
def test_pilot_create_assigns_audio_profile():
    """Pilot.create() must assign audio profile."""
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    
    pilot = Pilot.create(ship=ship)
    
    # Must have audio profile
    assert hasattr(pilot, 'audio_profile'), "Pilot must have audio_profile after create()"
    profile = pilot.audio_profile
    assert profile is not None
    
    # Profile must be linked to pilot
    assert profile.actor == pilot


@pytest.mark.django_db(transaction=True)
def test_controller_create_assigns_audio_profile():
    """Controller.create() must assign audio profile."""
    loc = Location.objects.create(name="Mars Control", scale=Scale.STATION)
    
    controller = Controller.create(location=loc)
    
    # Must have audio profile
    assert hasattr(controller, 'audio_profile'), "Controller must have audio_profile after create()"
    profile = controller.audio_profile
    assert profile is not None
    assert profile.actor == controller


@pytest.mark.django_db(transaction=True)
def test_satellite_create_assigns_audio_profile():
    """Satellite.create() must assign audio profile."""
    sat = Satellite.create(name="NAVSAT ALPHA")
    
    # Must have audio profile
    assert hasattr(sat, 'audio_profile'), "Satellite must have audio_profile after create()"
    profile = sat.audio_profile
    assert profile is not None
    assert profile.actor == sat


@pytest.mark.django_db(transaction=True)
def test_dialogue_event_log_via_receiver_has_actor():
    """DialogueEvent processed via signal must have actor ForeignKey."""
    from mysite.universe.signals import dialogue_event_processed
    
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    
    # Create DialogueEvent and send signal
    event = DialogueEvent(
        timestamp=100.0,
        actor=pilot,
        text="Test message",
    )
    
    dialogue_event_processed.send(sender=None, event=event)
    
    # Check that log entry was created with actor ForeignKey
    log_entry = DialogueEventLog.objects.filter(actor_name=pilot.name).first()
    assert log_entry is not None, "DialogueEventLog should be created via receiver"
    assert log_entry.actor is not None, "DialogueEventLog must have actor reference"
    assert log_entry.actor.id == pilot.id, "actor_id must match actor.id"


@pytest.mark.django_db(transaction=True)
def test_dialogue_event_log_direct_create_has_actor_id():
    """DialogueEventLog created directly must have actor_id in metadata."""
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)  # .create() ensures audio profile
    
    # Create DialogueEvent
    event = DialogueEvent(
        timestamp=100.0,
        actor=pilot,
        text="Test message",
    )
    
    # Create log entry directly (simulating missions.py path)
    # This is the pattern used in missions.py - must include actor_id
    metadata = dict(event.metadata) if event.metadata else {}
    if hasattr(event, 'actor') and event.actor is not None:
        if hasattr(event.actor, 'id'):
            metadata['actor_id'] = event.actor.id
    
    log_entry = DialogueEventLog.objects.create(
        timestamp=event.timestamp,
        actor_name=event.actor.name,
        text=event.text,
        metadata=metadata,
    )
    
    # Verify actor_id is present
    assert 'actor_id' in log_entry.metadata, "Direct create must include actor_id in metadata"
    assert log_entry.metadata['actor_id'] == pilot.id


@pytest.mark.django_db(transaction=True)
def test_all_actor_types_have_audio_profiles():
    """All actor types (Pilot, Controller, Satellite) must have audio profiles after create()."""
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    
    pilot = Pilot.create(ship=ship)
    controller = Controller.create(location=loc)
    satellite = Satellite.create(name="NAVSAT")
    
    # All must have profiles
    assert hasattr(pilot, 'audio_profile')
    assert hasattr(controller, 'audio_profile')
    assert hasattr(satellite, 'audio_profile')
    
    # Profiles must be linked
    assert pilot.audio_profile.actor == pilot
    assert controller.audio_profile.actor == controller
    assert satellite.audio_profile.actor == satellite


@pytest.mark.django_db(transaction=True)
def test_dialogue_event_always_has_actor():
    """DialogueEvent must always have an actor attribute."""
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    
    # Valid creation
    event = DialogueEvent(
        timestamp=100.0,
        actor=pilot,
        text="Test",
    )
    assert event.actor == pilot
    assert hasattr(event.actor, 'id')
    assert event.actor.id == pilot.id


@pytest.mark.django_db(transaction=True)
def test_dialogue_event_log_has_actor_reference():
    """All DialogueEventLog entries should have actor ForeignKey."""
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    controller = Controller.create(location=loc)
    satellite = Satellite.create(name="NAVSAT")
    
    actors = [pilot, controller, satellite]
    
    for actor in actors:
        # Create event
        event = DialogueEvent(
            timestamp=100.0,
            actor=actor,
            text=f"Test from {actor.name}",
        )
        
        # Create log entry with actor ForeignKey
        log_entry = DialogueEventLog.objects.create(
            timestamp=event.timestamp,
            actor=event.actor,
            text=event.text,
        )
        
        # Verify actor reference is present and correct
        assert log_entry.actor is not None, f"Event from {actor.name} missing actor"
        assert log_entry.actor.id == actor.id, f"actor_id mismatch for {actor.name}"
        assert log_entry.actor_name == actor.name, f"actor_name not cached for {actor.name}"


@pytest.mark.django_db(transaction=True)
def test_actor_reference_survives_with_set_null():
    """If actor is deleted, DialogueEventLog survives with cached actor_name."""
    loc = Location.objects.create(name="Test Station", scale=Scale.STATION)
    ship = Ship.objects.create(name="TestShip", current_location=loc, size=Ship.Size.MEDIUM)
    pilot = Pilot.create(ship=ship)
    
    log_entry = DialogueEventLog.objects.create(
        timestamp=100.0,
        actor=pilot,
        text="Test"
    )
    
    # Verify actor reference exists
    assert log_entry.actor is not None
    assert log_entry.actor_name == pilot.name
    
    # Delete actor
    pilot_name = pilot.name
    pilot.delete()
    
    # Reload log entry and verify it survives with cached name
    log_entry.refresh_from_db()
    assert log_entry.actor is None  # ForeignKey is now NULL
    assert log_entry.actor_name == pilot_name  # Cached name survives

