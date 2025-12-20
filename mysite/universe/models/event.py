from dataclasses import dataclass
from typing import Optional, Dict

# Django imports for model
from django.db import models

# Import the Actor model to associate events with an actor.
from mysite.universe.models.actor import Actor
from mysite.universe.models.base import Location
from mysite.universe.models.navigation import ManeuverType


@dataclass(frozen=True, kw_only=True)
class Event:
    """
    Base class for all simulation events.
    
    Events are data objects that represent things happening in the simulation.
    The simulation queue processes events by emitting signals when their
    timestamp is reached. Dialogue chains are generated complete upfront,
    so events don't generate follow-up events.
    
    Attributes:
        timestamp: float
            The time (in seconds from the simulation start) when the event should trigger.
        duration: float
            How long this event takes to complete.
        event_type: str
            The type of event (e.g., "dialogue", "navigation")
        metadata: Optional[Dict]
            Additional data associated with this event.
    """
    # Required fields (no defaults) must come first
    timestamp: float
    
    # Optional fields with defaults come last
    duration: float = 5.0
    event_type: str = "event"
    metadata: Optional[Dict] = None

@dataclass(frozen=True, kw_only=True)
class DialogueEvent(Event):
    """
    A dialogue event represents a line of dialogue spoken by an actor.
    
    This can be a request for clearance, acknowledgment of instructions,
    or any other communication between actors.
    
    Dialogue chains are generated complete upfront by DialogueService,
    so events are pure data objects with no reply generation logic.
    
    Attributes:
        timestamp: When the event should occur in simulation time
        actor: The actor speaking the dialogue
        text: The spoken dialogue text
        duration: How long the dialogue takes to deliver (for TTS timing)
        event_type: The type of event ("dialogue")
        metadata: Additional information about the event
    """
    # Required fields first
    timestamp: float
    actor: Actor
    text: str
    
    # Optional fields with defaults last
    duration: float = 0.0
    event_type: str = "dialogue"
    metadata: Optional[Dict] = None


@dataclass(frozen=True, kw_only=True)
class NavigationEvent(Event):
    """
    A navigation event represents a navigation maneuver in the simulation.
    
    Attributes:
        timestamp: When the event should occur in simulation time.
        maneuver: The type of maneuver being performed.
        target: The target destination.
        duration: Optional; time the event takes.
        event_type: The type of event ("navigation").
        metadata: Additional context for the event.
    """
    timestamp: float
    maneuver: ManeuverType
    target: Location
    duration: float = 0.0
    event_type: str = "navigation"
    metadata: Optional[Dict] = None


class DialogueEventLog(models.Model):
    """
    Django model for storing dialogue events in the database for real-time display.
    
    This is an ephemeral storage solution - events are temporary and don't need
    long-term persistence. Used by the web interface to display scrolling dialogue.
    
    CRITICAL: The 'text' field MUST always contain natural language dialogue.
    If JSON is needed, it can be stored in metadata, but 'text' is for display only.
    """
    timestamp = models.FloatField(help_text="Simulation time when event occurred")
    actor_name = models.CharField(max_length=200, help_text="Name of the speaking actor")
    text = models.TextField(help_text="The dialogue message")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Database insertion time")
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
        ]
        verbose_name = "Dialogue Event Log"
        verbose_name_plural = "Dialogue Event Logs"
    
    def __str__(self):
        return f"[{self.timestamp:.2f}] {self.actor_name}: {self.text[:50]}"

