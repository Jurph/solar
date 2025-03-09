from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict

# Import the Actor model to associate events with an actor.
from mysite.universe.models.actor import Actor
from mysite.universe.models.base import Location
from mysite.universe.models.navigation import ManeuverType

@dataclass(frozen=True)
class Event(ABC):
    """
    Base class for all simulation events.
    
    Attributes:
        timestamp: float
            The time (in seconds from the simulation start) when the event should trigger.
    """
    timestamp: float

    @abstractmethod
    def process(self):
        """
        Process this event when it is popped off the simulation queue.
        Subclasses should implement this method to perform their specific actions.
        """
        pass

@dataclass(frozen=True)
class BroadcastEvent(Event):
    """
    Represents a broadcast event intended for simulation output.
    
    In addition to a timestamp, this event includes:
        actor: Actor
            The entity (e.g., Satellite, Pilot, Controller) responsible for the broadcast.
        text: str
            Finalized dialogue or message to be spoken or displayed.
        duration: Optional[float]
            Optional; indicates how long the broadcast should be displayed or how long the TTS playback lasts.
        event_type: Optional[str]
            Optional; a category label for the event (e.g., 'dialogue', 'alert', or 'announcement').
        metadata: Optional[dict]
            Optional extra metadata for additional context.
    """
    actor: Actor
    text: str
    duration: Optional[float] = None
    event_type: Optional[str] = None
    metadata: Optional[dict] = None

    def process(self):
        """
        Process the broadcast event.
        
        This is a simple demonstration implementation. In a production setting,
        this method could send the text to a TTS service or a scrolling dialogue UI.
        For now, it simply prints the actor's name (in uppercase) along with the message.
        """
        print(f"Broadcast from {self.actor.name.upper()}: {self.text}")
    
@dataclass(frozen=True)
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
    """
    timestamp: float
    actor: Actor
    text: str
    expect_reply: bool = False
    duration: float = 0.0
    event_type: str = "dialogue"
    metadata: Optional[Dict] = None
    
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
        print(f"{self.actor.name} says: {self.text} [Expecting reply]")
        # In a real implementation, this might add a reply event to the queue
    
    def end_conversation_action(self):
        """Action to take when the dialogue ends the conversation."""
        print(f"{self.actor.name} says: {self.text} [End of conversation]")

@dataclass(frozen=True)
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

