from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict

# Import the Actor model to associate events with an actor.
from mysite.universe.models.actor import Actor
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
        """Action to take when the dialogue expects a reply.
        Determines the replying actor and generates an appropriate reply based on the actor type and metadata.
        """
        print(f"{self.actor.name} says: {self.text} [Expecting reply]")

        # First, try to use the explicitly attached expected_reply_actor
        if self.expected_reply_actor is not None:
            reply_actor = self.expected_reply_actor
        else:
            # If no actor attached, check metadata for a 'reply_actor_name'
            reply_name = self.metadata.get("reply_actor_name") if self.metadata else None

            if reply_name:
                # Look up the Actor by name
                from mysite.universe.models.actor import Actor
                qs = Actor.objects.filter(name=reply_name)
                reply_actor = qs.first() if qs.exists() else None
            else:
                reply_actor = None

        # If we still don't have a reply actor, use the original actor
        if reply_actor is None:
            reply_actor = self.actor

        # Determine the reply text based on actor role and metadata
        # Use getattr to safely get the role attribute; default to None if it doesn't exist
        if getattr(reply_actor, 'role', None) == "satellite":
            reply_text = "BEEP BOOP"
        else:
            # Use expected_reply from metadata if provided, otherwise generate a generic reply
            reply_text = (
                self.metadata.get("expected_reply")
                if self.metadata and "expected_reply" in self.metadata
                else f"Acknowledged, {self.actor.name}."
            )

        # Create the reply event 5 seconds after the original message
        return DialogueEvent(
            timestamp=self.timestamp + 5.0,  # Satellite replies after 5 seconds
            actor=reply_actor,
            text=reply_text,
            expect_reply=False,  # Satellites don't expect replies to their beeps
            duration=2.0,
            event_type="dialogue",
            metadata={}
        )
    
    def end_conversation_action(self):
        """Action to take when the dialogue ends the conversation."""
        print(f"{self.actor.name} says: {self.text} [End of conversation]")

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
        print(f"Navigation: {self.maneuver.name} to {self.target.name}")

