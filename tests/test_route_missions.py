from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from django.test import TestCase

from mysite.universe.models.base import Location
from mysite.universe.models.navigation import ManeuverType, NavigationEvent
from mysite.universe.models.scale import Scale
from mysite.universe.models.ship import Ship
from mysite.universe.services.route.missions import (
    pick_random_destination,
    random_journey,
    get_local_locations,
)


class _DummyUniverse:
    def __init__(self, path):
        self._path = path

    def get_path(self, origin, destination):
        return list(self._path)

    def get_local_graph(self, current, ordered_scale):
        # Keep this intentionally simple: the service under test is that we
        # delegate to UniverseGraph.get_local_graph(), not the filtering logic here.
        return list(Location.objects.all())


class _DummyService:
    def __init__(self, *, events, controller_for):
        self._events = events
        self._controller_for = controller_for
        self.effective_controller_calls = []

    def plan_route(self, origin, destination):
        return list(self._events)

    def effective_controller(self, location):
        self.effective_controller_calls.append(location)
        return self._controller_for(location)


class TestRouteMissions(TestCase):
    def setUp(self):
        self.origin = Location.objects.create(name="Origin", scale=Scale.PLANET)
        self.mid = Location.objects.create(name="Mid", scale=Scale.MOON)
        self.dest = Location.objects.create(name="Dest", scale=Scale.STATION)
        self.ctrl_origin = Location.objects.create(name="Origin Control", scale=Scale.STATION)
        self.ctrl_dest = Location.objects.create(name="Dest Control", scale=Scale.STATION)

    def test_pick_random_destination_filters_by_max_scale(self):
        # Create another ineligible location with a higher scale
        Location.objects.create(name="TooBig", scale=Scale.GALAXY)
        with patch("mysite.universe.services.route.missions.random.choice", side_effect=lambda xs: xs[0]):
            picked = pick_random_destination(
                service=None,
                excluding=self.origin,
                max_scale=Scale.STATION,
                cargo_mission=False,
            )
        assert picked.id != self.origin.id
        assert picked.scale <= Scale.STATION

    def test_pick_random_destination_raises_when_no_eligible(self):
        # Only one location in DB; excluding it means none eligible
        Location.objects.all().exclude(id=self.origin.id).delete()
        with self.assertRaises(ValueError):
            pick_random_destination(service=None, excluding=self.origin, cargo_mission=False)

    def test_pick_random_destination_cargo_uses_ship_valid_locations(self):
        other = Location.objects.create(name="CargoDest", scale=Scale.PLANET)
        with (
            patch.object(Ship, "get_valid_cargo_locations", return_value=[self.origin, other]),
            patch("mysite.universe.services.route.missions.random.choice", side_effect=lambda xs: xs[0]),
        ):
            picked = pick_random_destination(service=None, excluding=self.origin, cargo_mission=True)
        assert picked == other

    def test_random_journey_assigns_origin_when_ship_location_missing(self):
        class _ShipStub:
            def __init__(self):
                self.current_location = None
                self.saved = False

            def save(self):
                self.saved = True

        ship = _ShipStub()

        events = [
            NavigationEvent(
                maneuver=ManeuverType.LAUNCH,
                origin=self.origin,
                current=self.origin,
                next=self.mid,
                destination=self.mid,
                description="launch",
                controller=None,
            ),
            NavigationEvent(
                maneuver=ManeuverType.DOCK,
                origin=self.mid,
                current=self.mid,
                next=self.dest,
                destination=self.dest,
                description="dock",
                controller=None,
            ),
        ]

        def controller_for(loc):
            if loc == self.origin:
                return self.ctrl_origin
            return self.ctrl_dest

        service = _DummyService(events=events, controller_for=controller_for)
        universe = _DummyUniverse(path=[self.origin, self.mid, self.dest])

        with (
            patch.object(Ship, "get_random_cargo_origin", return_value=self.origin),
            patch("mysite.universe.services.route.missions.pick_random_destination", return_value=self.dest),
            patch("mysite.universe.services.route.missions.UniverseGraph.get_instance", return_value=universe),
        ):
            out = random_journey(service, ship, cargo_mission=True)

        # Should return same number of events
        assert len(out) == 2
        assert ship.saved is True

        # Controllers should be filled in with correct effective controller selection
        assert out[0].controller == self.ctrl_origin
        assert out[1].controller == self.ctrl_dest

        # And the service should have been asked for the right controlling locations
        assert service.effective_controller_calls[0] == self.origin
        assert service.effective_controller_calls[1] == self.dest

    def test_random_journey_preserves_existing_controller(self):
        ship = Ship.objects.create(
            name="TestShip2",
            current_location=self.origin,
            size=Ship.Size.MEDIUM,
        )
        existing = NavigationEvent(
            maneuver=ManeuverType.TRANSFER,
            origin=self.origin,
            current=self.origin,
            next=self.dest,
            destination=self.dest,
            description="transfer",
            controller=self.ctrl_origin,
        )

        service = _DummyService(events=[existing], controller_for=lambda loc: self.ctrl_dest)
        universe = _DummyUniverse(path=[self.origin, self.dest])

        with (
            patch("mysite.universe.services.route.missions.pick_random_destination", return_value=self.dest),
            patch("mysite.universe.services.route.missions.UniverseGraph.get_instance", return_value=universe),
        ):
            out = random_journey(service, ship, cargo_mission=False)

        assert out[0].controller == self.ctrl_origin
        assert service.effective_controller_calls == []

    def test_get_local_locations_delegates_to_universe_graph(self):
        current = self.origin
        universe = _DummyUniverse(path=[self.origin])
        with patch("mysite.universe.services.route.missions.UniverseGraph.get_instance", return_value=universe):
            locals_ = get_local_locations(service=None, current=current, max_scale=Scale.STATION)
        assert all(isinstance(x, Location) for x in locals_)

