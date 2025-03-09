from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

# Import the Actor model to associate events with an actor.
from mysite.universe.models.actor import Actor

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
    
