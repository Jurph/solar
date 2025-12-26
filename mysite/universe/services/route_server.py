"""
RouteService using a two-pass planning approach based on the World Building Rules.

This module is the public façade for route planning. The implementation details live in
`mysite.universe.services.route.*` to keep this file small and readable while preserving the
existing `RouteService` public API and method signatures.
"""

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING, Union

from mysite.universe.models.actor import Controller
from mysite.universe.models.base import Location
from mysite.universe.models.navigation import ManeuverType, NavigationEvent
from mysite.universe.models.scale import Scale

from .route import controllers as route_controllers
from .route import durations as route_durations
from .route import formatting as route_formatting
from .route import missions as route_missions
from .route import plan as route_plan

if TYPE_CHECKING:
    from mysite.universe.models.celestial import PhysicalBody


@dataclass(frozen=True)
class TransferSegment:
    """
    Represents a high-level transfer between two locations.

    Attributes:
        start: The starting location
        end: The ending location
        transfer_type: The type of transfer (SUBLIGHT, HYPERSPACE)
        max_scale: The maximum scale encountered during this transfer
    """

    start: Location
    end: Location
    transfer_type: ManeuverType
    max_scale: Scale


class RouteService:
    """Route planning service implementing a two-pass approach."""

    def plan_route(self, origin: Location, destination: Location) -> List[NavigationEvent]:
        return route_plan.plan_route(self, origin, destination)

    def _build_scale_path(self, path: List[Location]) -> List[int]:
        return route_plan.build_scale_path(path)

    def _determine_transfer_plan(self, scale_path: List[int]) -> List[Union[int, ManeuverType]]:
        return route_plan.determine_transfer_plan(scale_path)

    def _determine_maneuvers(
        self,
        transfer_plan: List[Union[int, ManeuverType]],
        location_path: List[Location],
        overall_max: int,
    ) -> List[NavigationEvent]:
        return route_plan.determine_maneuvers(self, transfer_plan, location_path, overall_max)

    def _enhance_with_controllers(self, events: List[NavigationEvent]) -> List[NavigationEvent]:
        return route_controllers.enhance_with_controllers(self, events)

    def effective_controller(self, location: Location) -> Union[Controller, Location]:
        return route_controllers.effective_controller(self, location)

    def pick_random_destination(
        self,
        excluding: Location,
        max_scale: Scale = None,
        cargo_mission: bool = False,
    ) -> Location:
        return route_missions.pick_random_destination(
            self,
            excluding=excluding,
            max_scale=max_scale,
            cargo_mission=cargo_mission,
        )

    def random_journey(self, ship, cargo_mission: bool = True) -> List[NavigationEvent]:
        return route_missions.random_journey(self, ship, cargo_mission=cargo_mission)

    def get_local_locations(self, current: Location, max_scale: Scale) -> List[Location]:
        return route_missions.get_local_locations(self, current, max_scale)

    def pretty_print_events(self, events: List[NavigationEvent], include_headers: bool = True) -> str:
        return route_formatting.pretty_print_events(events, include_headers=include_headers)

    def _compress_location_path(self, location_path: List[Location]) -> List[Location]:
        return route_plan.compress_location_path(location_path)

    def get_event_duration(self, event: NavigationEvent) -> float:
        return route_durations.get_event_duration(self, event)

    def _get_relevant_body_for_maneuver(self, event: NavigationEvent) -> Optional["PhysicalBody"]:
        return route_durations.get_relevant_body_for_maneuver(self, event)

    def _extract_body_params(self, body) -> dict:
        return route_durations.extract_body_params(body)

    def _build_physics_nav_context(self, event: NavigationEvent, body) -> dict:
        return route_durations.build_physics_nav_context(self, event, body)


