from dataclasses import dataclass
from typing import List

# Import models that comprise the mission context
from mysite.universe.models.navigation import NavigationEvent
from mysite.universe.models.ship import Ship
from mysite.universe.signals import simulation_event  # Import our Django signal


@dataclass(frozen=True)
class SimulationQueueItem:
    """
    Aggregates a NavigationEvent with its associated Ship and a timestamp.
    The timestamp is derived from the NavigationEvent's duration field, indicating when the event should trigger.
    This allows the simulation engine to access detailed mission context including:
      - The NavigationEvent itself (maneuver type, origin, destination, etc.)
      - The Ship on which the event is taking place
      - Through the Ship, access to its Pilot (ship.pilot) and its cargo information (ship.cargo)
    """
    nav_event: NavigationEvent
    ship: Ship
    timestamp: float


class SimulationQueue:
    """
    A simple simulation queue that manages SimulationQueueItems.

    This queue allows the loading of missions by bundling a Ship and its
    corresponding series of NavigationEvents. As events are processed, the
    associated SimulationQueueItem provides full context needed by the simulation
    engine.
    """

    def __init__(self):
        self.queue: List[SimulationQueueItem] = []

    def add_item(self, item: SimulationQueueItem) -> None:
        """Add a SimulationQueueItem to the queue."""
        self.queue.append(item)

    def pop_item(self) -> SimulationQueueItem:
        """Remove and return the next item from the simulation queue. Raises IndexError if empty."""
        if self.queue:
            return self.queue.pop(0)
        raise IndexError("The simulation queue is empty.")

    def load_mission(self, ship: Ship, nav_events: List[NavigationEvent]) -> None:
        """
        Load a mission into the simulation queue by bundling a Ship with a list of NavigationEvents.

        Args:
            ship: The Ship instance for the mission. It carries cargo and pilot info.
            nav_events: A list of NavigationEvent objects defining the mission route and maneuvers.
        """
        for event in nav_events:
            self.add_item(SimulationQueueItem(nav_event=event, ship=ship, timestamp=event.duration))

    def is_empty(self) -> bool:
        """Return True if the simulation queue is empty, otherwise False."""
        return len(self.queue) == 0

    def notify_subscribers(self, item: SimulationQueueItem) -> None:
        """
        Instead of calling custom subscriber callbacks, use Django Signals to notify interested receivers.
        """
        simulation_event.send(sender=self.__class__, item=item) 