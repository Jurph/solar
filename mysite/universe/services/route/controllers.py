from typing import List, Union

from mysite.universe.models.actor import Controller
from mysite.universe.models.base import Location
from mysite.universe.models.navigation import ManeuverType, NavigationEvent, find_controlling_station


def enhance_with_controllers(service, events: List[NavigationEvent]) -> List[NavigationEvent]:
    """
    Enhance all events with proper controller information.

    Rules for controller assignment:
    1. Departure maneuvers (LAUNCH, UNDOCK, INSERTION): controller of origin/departure
    2. Arrival maneuvers (DOCK, DEORBIT, LANDING): controller of destination
    3. Transfer maneuvers (SUBLIGHT, HYPERSPACE, etc.): controller of current location
    """
    enhanced_events: List[NavigationEvent] = []

    for event in events:
        if event.maneuver in [ManeuverType.LAUNCH, ManeuverType.UNDOCK, ManeuverType.INSERTION]:
            controller_loc = event.origin
        elif event.maneuver in [ManeuverType.DOCK, ManeuverType.DEORBIT, ManeuverType.LANDING]:
            controller_loc = event.destination
        else:
            controller_loc = event.current

        controller = effective_controller(service, controller_loc)

        updated_event = NavigationEvent(
            maneuver=event.maneuver,
            origin=event.origin,
            current=event.current,
            next=event.next,
            destination=event.destination,
            description=event.description,
            controller=controller,
        )
        enhanced_events.append(updated_event)

    return enhanced_events


def effective_controller(service, location: Location) -> Union[Controller, Location]:
    """
    Get the controlling entity (Controller actor or Location) for a given Location.

    This is a service-layer adapter that:
    1. Delegates to find_controlling_station() for the world-model logic
    2. Looks up the Controller actor for that station
    3. Returns either the Controller actor or the Location as fallback
    """
    controlling_location = find_controlling_station(location)

    if controlling_location is None:
        # Remote/uncontrolled space - return the location itself
        return location.get_concrete_instance()

    # Controllers are created on-demand; ActorService.deploy_controllers() can pre-populate common stations
    controller = Controller.objects.filter(location=controlling_location).first()
    if not controller:
        controller = Controller.objects.filter(name=controlling_location.name).first()

    if controller:
        return controller

    # No Controller actor exists - return the controlling Location itself
    return controlling_location


