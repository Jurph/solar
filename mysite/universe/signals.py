from django.dispatch import Signal

# Define a signal for simulation events.
# When an event is ready, the signal will be sent with a keyword argument "item"
# containing the SimulationQueueItem.
simulation_event = Signal() 