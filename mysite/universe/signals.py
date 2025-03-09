from django.dispatch import Signal

# Define a signal for simulation events.
# When an event is ready, the signal will be sent with a keyword argument "item"
# containing the SimulationQueueItem.
simulation_event = Signal()

# Signal emitted when a dialogue event is processed
dialogue_event_processed = Signal()

# Signal emitted when a navigation event is processed
navigation_event_processed = Signal() 