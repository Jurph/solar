from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict

# Django imports for model
from django.db import models

# Import the Actor model to associate events with an actor.
from mysite.universe.models.actor import Actor, Controller
from mysite.universe.models.base import Location
from mysite.universe.models.navigation import ManeuverType

@dataclass(frozen=True, kw_only=True)
class Event(ABC):
    """
    Base class for all simulation events.
    
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

    @abstractmethod
    def process(self):
        """
        Process this event when it is popped off the simulation queue.
        
        Returns:
            None, Event, or List[Event]:
                - None if no follow-up events are needed
                - A single Event if one follow-up event is needed
                - A list of Events if multiple follow-up events are needed
        
        This method should:
        1. Perform any state changes required by the event
        2. Return any follow-up events that should be added to the queue
        """
        pass

@dataclass(frozen=True, kw_only=True)
class DialogueEvent(Event):
    """
    A dialogue event represents a line of dialogue spoken by an actor.
    
    This can be a request for clearance, acknowledgment of instructions,
    or any other communication between actors.
    
    Attributes:
        timestamp: When the event should occur in simulation time
        actor: The actor speaking the dialogue
        text: The spoken dialogue text
        expect_reply: Whether the dialogue expects a response
        duration: How long the dialogue takes to deliver (for TTS timing)
        event_type: The type of event ("dialogue")
        metadata: Additional information about the event
        expected_reply_actor: Optional[Actor] = None
    """
    # Required fields first
    timestamp: float
    actor: Actor
    text: str
    
    # Optional fields with defaults last
    expect_reply: bool = False
    duration: float = 0.0
    event_type: str = "dialogue"
    metadata: Optional[Dict] = None
    expected_reply_actor: Optional[Actor] = None
    
    def process(self):
        """
        Process the dialogue event.
        
        For dialogue, this means displaying or speaking the text.
        If expect_reply is True, this may also generate a reply event.
        """
        if self.expect_reply:
            return self.expect_reply_action()
        else:
            return self.end_conversation_action()
    
    def expect_reply_action(self):
        """Action to take when the dialogue expects a reply."""
        if self.expected_reply_actor is not None:
            reply_actor = self.expected_reply_actor
        else:
            # Try to get the reply actor from metadata
            reply_name = self.metadata.get("reply_actor_name") if self.metadata else None
            if reply_name:
                qs = Actor.objects.filter(name=reply_name)
                reply_actor = qs.first() if qs.exists() else None
            else:
                # If no specific reply actor is found, check if this is a pilot-controller dialogue
                if getattr(self.actor, 'role', None) == Actor.Role.PILOT:
                    # Get the controller name from metadata
                    control_name = self.metadata.get("control_name") if self.metadata else None
                    if control_name:
                        # Just look up the controller - it should exist
                        reply_actor = Controller.objects.filter(name=control_name).first()
                    else:
                        reply_actor = None
                elif getattr(self.actor, 'role', None) == Actor.Role.CONTROLLER:
                    # Get the ship name from metadata to find the pilot
                    ship_name = self.metadata.get("ship_name") if self.metadata else None
                    if ship_name:
                        # Look up the ship and get its pilot
                        from mysite.universe.models.ship import Ship
                        from mysite.universe.models.actor import Pilot
                        ship = Ship.objects.filter(name=ship_name).first()
                        if ship and ship.pilot:
                            reply_actor = ship.pilot
                        else:
                            # Try to find pilot by name from metadata
                            pilot_name = self.metadata.get("pilot_name") if self.metadata else None
                            if pilot_name:
                                reply_actor = Pilot.objects.filter(name=pilot_name).first()
                            else:
                                reply_actor = None
                    else:
                        reply_actor = None
                else:
                    reply_actor = None

        # If we still don't have a reply actor, use the original actor
        if reply_actor is None:
            reply_actor = self.actor

        # Determine the reply text based on actor role
        if getattr(reply_actor, 'role', None) == Actor.Role.SATELLITE:
            reply_text = "BEEP BOOP"
            expect_reply = False
        elif getattr(reply_actor, 'role', None) == Actor.Role.CONTROLLER:
            # Pilot -> Controller: Chains are now generated upfront, so this should not happen
            # If expect_reply=True on a chain event, the next event is already in the chain
            # Return None to indicate no dynamic reply needed
            return None
        elif getattr(self.actor, 'role', None) == Actor.Role.CONTROLLER and getattr(reply_actor, 'role', None) == Actor.Role.PILOT:
            # Controller -> Pilot: Chains are now generated upfront, so this should not happen
            # If expect_reply=True on a chain event, the next event is already in the chain
            # Return None to indicate no dynamic reply needed
            return None
        else:
            # Use expected_reply from metadata if provided, otherwise generate a generic reply
            reply_text = (
                self.metadata["expected_reply"]
                if self.metadata and "expected_reply" in self.metadata
                else f"Acknowledged, {self.actor.name}."
            )
            expect_reply = False

        # Create the reply event 5 seconds after the original message
        return DialogueEvent(
            timestamp=self.timestamp + 5.0,
            actor=reply_actor,
            text=reply_text,
            expect_reply=expect_reply,
            duration=2.0,
            event_type="dialogue",
            metadata=self.metadata
        )
    
    def end_conversation_action(self):
        """Action to take when the dialogue ends the conversation."""
        # No follow-up events needed
        return None

@dataclass(frozen=True, kw_only=True)
class NavigationEvent(Event):
    """
    A navigation event represents a navigation maneuver in the simulation.
    
    Attributes:
        timestamp: When the event should occur in simulation time.
        maneuver: The actor performing the maneuver.
        target: The target actor or destination.
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
    
    def process(self):
        """Process the navigation event. Returns None as navigation events don't generate follow-ups."""
        # Navigation events don't generate follow-up events
        return None


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
    text = models.TextField(help_text="The dialogue message (natural language only, never JSON)")
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

