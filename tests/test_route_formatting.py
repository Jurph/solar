from django.test import TestCase

from mysite.universe.models.base import Location
from mysite.universe.models.navigation import ManeuverType, NavigationEvent
from mysite.universe.models.scale import Scale
from mysite.universe.services.route.formatting import pretty_print_events


class TestRouteFormatting(TestCase):
    def setUp(self):
        self.a = Location.objects.create(name="A", scale=Scale.STATION)
        self.b = Location.objects.create(name="B", scale=Scale.PLANET)
        self.c = Location.objects.create(name="C", scale=Scale.MOON)
        self.ctrl = Location.objects.create(name="A Control", scale=Scale.STATION)

    def test_pretty_print_events_empty(self):
        assert pretty_print_events([]) == "No navigation events to display"

    def test_pretty_print_events_includes_headers_by_default(self):
        events = [
            NavigationEvent(
                origin=self.a,
                current=self.a,
                next=self.b,
                destination=self.b,
                maneuver=ManeuverType.TRANSFER,
                controller=self.ctrl,
            )
        ]
        text = pretty_print_events(events)
        assert "Origin" in text
        assert "Next Stop" in text
        assert "Maneuver Type" in text
        assert "Effective Controller" in text
        assert "STARTING POINT" in text
        assert "B" in text
        assert "TRANSFER" in text
        assert "A Control" in text

    def test_pretty_print_events_uses_prior_destination_as_origin(self):
        events = [
            NavigationEvent(
                origin=self.a,
                current=self.a,
                next=self.b,
                destination=self.b,
                maneuver=ManeuverType.TRANSFER,
                controller=None,
            ),
            NavigationEvent(
                origin=self.b,
                current=self.b,
                next=self.c,
                destination=self.c,
                maneuver=ManeuverType.CIRCULARIZE,
                controller=self.ctrl,
            ),
        ]
        text = pretty_print_events(events, include_headers=False)
        lines = text.splitlines()
        assert len(lines) == 2
        assert lines[0].startswith("STARTING POINT")
        assert lines[1].startswith("B")

    def test_pretty_print_events_handles_missing_destination(self):
        events = [
            NavigationEvent(
                origin=self.a,
                current=self.a,
                next=self.b,
                destination=None,  # intentional for coverage / robustness
                maneuver=ManeuverType.SUBLIGHT,
                controller=None,
            )
        ]
        text = pretty_print_events(events, include_headers=False)
        assert "Unknown" in text

