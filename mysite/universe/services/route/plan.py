from typing import List, Union

from mysite.universe.models.base import Location
from mysite.universe.models.constants import TypeName
from mysite.universe.models.navigation import (
    ManeuverType,
    NavigationEvent,
    UniverseGraph,
    is_planetary,
)
from mysite.universe.models.scale import OrderedScale, Scale


def build_scale_path(path: List[Location]) -> List[int]:
    """
    Convert a list of Locations into an ordered-scale path (list of integers).
    """
    scale_path = []
    for loc in path:
        concrete = loc.get_concrete_instance()
        scale_val = OrderedScale(concrete.scale)
        scale_path.append(scale_val)
    return scale_path


def compress_location_path(location_path: List[Location]) -> List[Location]:
    """
    Compress the location path by retaining only essential nodes.

    The first and last nodes are always kept, and any intermediate node whose concrete type is
    one of Planet/Moon/Station is retained.
    """
    if not location_path:
        return location_path

    compressed = [location_path[0]]
    for node in location_path[1:-1]:
        node_type = node.get_concrete_instance().get_type_name()
        if node_type in TypeName.SURFACE_LOCATIONS:
            compressed.append(node)
    compressed.append(location_path[-1])
    return compressed


def determine_transfer_plan(scale_path: List[int]) -> List[Union[int, ManeuverType]]:
    """
    Given an ordered scale path, produce a hybrid list interleaving scale values with transfer types.
    """
    if len(scale_path) < 2:
        return scale_path

    transfer_plan = [scale_path[0]]

    transfer_plan.append(ManeuverType.INSERTION)
    transfer_plan.append(scale_path[1])

    for i in range(1, len(scale_path) - 1):
        transfer_plan.append(ManeuverType.SUBLIGHT)
        transfer_plan.append(scale_path[i + 1])

    return transfer_plan


def plan_route(
    service, origin: Location, destination: Location
) -> List[NavigationEvent]:
    """
    Plans a route from origin to destination using a two-pass approach.

    Public API wrapper lives on RouteService; this function holds the implementation.
    """
    universe = UniverseGraph.get_instance()
    path = universe.get_path(origin, destination)
    if not path or len(path) < 2:
        return []

    original_scale_path = build_scale_path(path)
    overall_max = max(original_scale_path)

    compressed_path = compress_location_path(path)

    # SPECIAL CASE: Direct ascent if the path has exactly two nodes
    if len(path) == 2:
        origin_type = origin.get_concrete_instance().get_type_name()
        dest_type = destination.get_concrete_instance().get_type_name()
        return _plan_direct_ascent_route(
            service, origin, destination, origin_type, dest_type
        )

    # Pass 1: Build scale path from the compressed path
    scale_path = build_scale_path(compressed_path)

    # Pass 2: Determine transfer plan
    if overall_max > OrderedScale(Scale.STARSYSTEM):
        transfer_plan = [
            scale_path[0],
            ManeuverType.INSERTION,
            scale_path[-1],
            ManeuverType.HYPERSPACE,
            scale_path[-1],
        ]
    else:
        transfer_plan = determine_transfer_plan(scale_path)

    # Pass 3: Generate maneuvers using the compressed path and overall_max from the original path
    return determine_maneuvers(service, transfer_plan, compressed_path, overall_max)


def _plan_direct_ascent_route(
    service,
    origin: Location,
    destination: Location,
    origin_type: str,
    dest_type: str,
) -> List[NavigationEvent]:
    """
    Build the maneuver sequence for a direct-ascent transfer between two locations.

    Direct ascent is used when the origin and destination are close enough that
    no intermediate Hohmann transfer or hyperspace jump is needed — the ship
    flies straight from one body to the other.

    The sequence is: optional departure (UNDOCK/LAUNCH) → DIRECT_ASCENT →
    optional arrival (DOCK, or CIRCULARIZE+DEORBIT+LANDING, or DEORBIT+LANDING).
    """

    def _make_event(maneuver: ManeuverType) -> NavigationEvent:
        current_loc = origin
        if maneuver in (
            ManeuverType.DEORBIT,
            ManeuverType.LANDING,
            ManeuverType.DOCK,
            ManeuverType.CIRCULARIZE,
        ):
            current_loc = destination

        return NavigationEvent(
            maneuver=maneuver,
            origin=origin,
            current=current_loc,
            next=destination,
            destination=destination,
            description=f"{maneuver.name} from {origin.name} to {destination.name}",
            controller=None,
        )

    events: List[NavigationEvent] = []

    if origin_type == TypeName.STATION:
        events.append(_make_event(ManeuverType.UNDOCK))
    elif origin_type == TypeName.MOON:
        events.append(_make_event(ManeuverType.LAUNCH))

    events.append(_make_event(ManeuverType.DIRECT_ASCENT))

    if dest_type == TypeName.STATION:
        events.append(_make_event(ManeuverType.DOCK))
    elif dest_type == TypeName.MOON:
        events.extend(
            [
                _make_event(ManeuverType.CIRCULARIZE),
                _make_event(ManeuverType.DEORBIT),
                _make_event(ManeuverType.LANDING),
            ]
        )
    else:
        events.extend(
            [_make_event(ManeuverType.DEORBIT), _make_event(ManeuverType.LANDING)]
        )

    from .controllers import enhance_with_controllers

    return enhance_with_controllers(service, events)


def determine_maneuvers(
    service,
    transfer_plan: List[Union[int, ManeuverType]],
    location_path: List[Location],
    overall_max: int,
) -> List[NavigationEvent]:
    """Create navigation events from the transfer plan."""
    if not location_path or len(location_path) < 2:
        raise ValueError("Invalid route: Path must contain at least two locations")

    compressed_path = compress_location_path(location_path)

    origin = compressed_path[0]
    destination = compressed_path[-1]
    next_location = destination
    origin_type = origin.get_concrete_instance().get_type_name()
    dest_type = destination.get_concrete_instance().get_type_name()

    events = []

    if (
        len(transfer_plan) == 3
        and isinstance(transfer_plan[1], ManeuverType)
        and transfer_plan[1] == ManeuverType.DIRECT_ASCENT
    ):
        return _plan_direct_ascent_route(
            service, origin, destination, origin_type, dest_type
        )

    # Multi-leg journey branch
    def make_departure_event(maneuver: ManeuverType) -> NavigationEvent:
        return NavigationEvent(
            maneuver=maneuver,
            origin=origin,
            current=origin,
            next=next_location,
            destination=destination,
            description=f"{maneuver.name} from {origin.name} to {destination.name}",
            controller=None,
        )

    def make_transfer_event(maneuver: ManeuverType) -> NavigationEvent:
        return NavigationEvent(
            maneuver=maneuver,
            origin=origin,
            current=origin,
            next=next_location,
            destination=destination,
            description=f"{maneuver.name} from {origin.name} to {destination.name}",
            controller=None,
        )

    def make_transfer_arrival_event(maneuver: ManeuverType) -> NavigationEvent:
        return NavigationEvent(
            maneuver=maneuver,
            origin=origin,
            current=destination,
            next=next_location,
            destination=destination,
            description=f"{maneuver.name} from {origin.name} to {destination.name}",
            controller=None,
        )

    # 1. DEPARTURE PHASE
    if origin_type == TypeName.STATION:
        events.append(make_departure_event(ManeuverType.UNDOCK))
        events.append(make_departure_event(ManeuverType.INSERTION))
        events.append(make_departure_event(ManeuverType.CIRCULARIZE))
    elif origin_type in TypeName.PLANETARY_BODIES or is_planetary(origin):
        events.append(make_departure_event(ManeuverType.LAUNCH))
        events.append(make_departure_event(ManeuverType.INSERTION))
        events.append(make_departure_event(ManeuverType.CIRCULARIZE))

    # 2. TRANSFER PHASE
    if len(transfer_plan) == 3:
        if dest_type == TypeName.STATION:
            events.append(make_transfer_event(ManeuverType.PLANE_CHANGE))
        else:
            events.append(make_transfer_event(ManeuverType.SUBLIGHT))
    else:
        is_origin_planetary = origin_type in TypeName.PLANETARY_BODIES or is_planetary(
            origin
        )
        if is_origin_planetary:
            if not any(
                isinstance(x, ManeuverType) and x == ManeuverType.HYPERSPACE
                for x in transfer_plan
            ):
                if dest_type == TypeName.STATION:
                    if len(transfer_plan) == 5:
                        events.append(
                            make_transfer_arrival_event(ManeuverType.PLANE_CHANGE)
                        )
                        events.append(make_transfer_event(ManeuverType.SUBLIGHT))
                        events.append(
                            make_transfer_arrival_event(ManeuverType.CIRCULARIZE)
                        )
                        events.append(
                            make_transfer_arrival_event(ManeuverType.PLANE_CHANGE)
                        )
                    else:
                        events.append(make_transfer_event(ManeuverType.PLANE_CHANGE))
                        events.append(make_transfer_event(ManeuverType.SUBLIGHT))
                        events.append(make_transfer_event(ManeuverType.CIRCULARIZE))
                        events.append(
                            make_transfer_arrival_event(ManeuverType.SUBLIGHT)
                        )
                        events.append(
                            make_transfer_arrival_event(ManeuverType.CIRCULARIZE)
                        )
                        events.append(
                            make_transfer_arrival_event(ManeuverType.PLANE_CHANGE)
                        )
                else:
                    events.append(make_transfer_arrival_event(ManeuverType.SUBLIGHT))
                    events.append(make_transfer_arrival_event(ManeuverType.CIRCULARIZE))
            else:
                hyperspace_segments = [
                    (i, t)
                    for i, t in enumerate(transfer_plan)
                    if isinstance(t, ManeuverType) and t == ManeuverType.HYPERSPACE
                ]
                for i, _ in hyperspace_segments:
                    events.append(make_transfer_event(ManeuverType.SUBLIGHT))
                    events.append(make_transfer_event(ManeuverType.HYPERSPACE))
                    events.append(make_transfer_arrival_event(ManeuverType.SUBLIGHT))
                    events.append(make_transfer_arrival_event(ManeuverType.CIRCULARIZE))
                if dest_type == TypeName.STATION:
                    events.append(
                        make_transfer_arrival_event(ManeuverType.PLANE_CHANGE)
                    )
        else:
            events.append(make_transfer_event(ManeuverType.SUBLIGHT))
            events.append(make_transfer_event(ManeuverType.CIRCULARIZE))

    # 3. ARRIVAL PHASE
    if dest_type == TypeName.STATION:
        events.append(make_transfer_arrival_event(ManeuverType.DOCK))
    elif dest_type in TypeName.PLANETARY_BODIES or is_planetary(destination):
        events.append(make_transfer_arrival_event(ManeuverType.DEORBIT))
        events.append(make_transfer_arrival_event(ManeuverType.LANDING))

    from .controllers import enhance_with_controllers

    return enhance_with_controllers(service, events)
