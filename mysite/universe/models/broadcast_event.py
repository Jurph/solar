from dataclasses import dataclass
from typing import Optional

# Import the Actor model, which represents an entity (e.g. Pilot, Controller, Satellite) in our simulation
from mysite.universe.models.actor import Actor


@dataclass(frozen=True)
class BroadcastEvent:
    """
    Represents a broadcast event intended for simulation output.

    Attributes:
        timestamp: float
            The time (seconds from simulation start) at which the event should trigger.
        actor: Actor
            The actor responsible for the broadcast (e.g., a Satellite, Pilot, or Controller).
        text: str
            The finalized dialogue to be spoken or displayed.
        duration: Optional[float]
            Optional. How long the broadcast should be displayed or lasts for TTS playback.
        event_type: Optional[str]
            Optional. A type or category label for the event (e.g., 'dialogue', 'alert', or 'announcement').
        metadata: Optional[dict]
            Optional extra metadata for the event as key-value pairs.
    """
    timestamp: float
    actor: Actor
    text: str
    duration: Optional[float] = None
    event_type: Optional[str] = None
    metadata: Optional[dict] = None 