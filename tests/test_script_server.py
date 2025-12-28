from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase

from mysite.universe.models.actor import Controller, Pilot, Satellite
from mysite.universe.models.base import Location
from mysite.universe.models.celestial import Galaxy, Planet, Star, StarSystem
from mysite.universe.models.navigation import ManeuverType, NavigationEvent
from mysite.universe.models.ship import Ship
from mysite.universe.models.station import Station
from mysite.universe.schemas.dialogue_schema import DialogueMessage, Role
from mysite.universe.services.script_server import ScriptService


class TestScriptServiceNavBroadcast(TestCase):
    def setUp(self):
        galaxy = Galaxy.objects.create(name="G", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="S",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Sol", orbits=system, star_type="G")
        self.planet = Planet.objects.create(name="Earth", orbits=star, planet_type="TE", orbital_distance_au=1.0)
        self.station = Station.objects.create(name="Earth Orbital Control", orbits=self.planet)
        self.satellite = Satellite.objects.create(name="Earth Navsat")
        self.llm = Mock(temperature=0.25)
        self.service = ScriptService(self.llm)

    def test_generate_nav_broadcast_chain_emits_single_broadcast_by_default(self):
        fake_particle = SimpleNamespace(
            generate_nav_broadcast_text=lambda: "NAV UPDATE",
            get_modem_encoded_data=lambda: "101010",
            get_next_particle_probabilities=lambda: {"gratitude": 0.0},
        )

        with patch.object(
            self.service.dialogue_service.particle_factory,
            "create_particle",
            return_value=fake_particle,
        ):
            events = self.service.generate_nav_broadcast_chain(self.satellite, base_timestamp=123.0)

        assert len(events) == 1
        ev = events[0]
        assert ev.timestamp == 123.0
        assert ev.actor == self.satellite
        assert ev.text == "NAV UPDATE"
        assert ev.metadata["type"] == "nav_broadcast"
        assert ev.metadata["satellite_name"] == self.satellite.name
        assert ev.metadata["modem_data"] == "101010"

    def test_generate_nav_broadcast_chain_adds_gratitude_when_probability_hits(self):
        # Ship + pilot to serve as gratitude source
        ship = Ship.objects.create(name="Test Ship", current_location=self.station, size="M", cargo="X", status="DOCK")
        pilot = Pilot.objects.create(name="Test Pilot", ship=ship)

        fake_broadcast_particle = SimpleNamespace(
            generate_nav_broadcast_text=lambda: "NAV UPDATE",
            get_modem_encoded_data=lambda: "101010",
            get_next_particle_probabilities=lambda: {"gratitude": 1.0},
        )
        fake_gratitude_particle = SimpleNamespace()

        # Use model_construct to avoid schema-level content validation: this test is about
        # ScriptService orchestration, not DialogueMessage validation rules.
        gratitude_msg = DialogueMessage.model_construct(
            role=Role.PILOT,
            speaker_callsign=pilot.name.upper(),
            recipient_callsign=self.satellite.name.upper(),
            message="THANKS FOR THE UPDATE",
        )

        def create_particle_side_effect(*, particle_type, **kwargs):
            if particle_type == "nav_broadcast":
                return fake_broadcast_particle
            if particle_type == "gratitude":
                return fake_gratitude_particle
            raise AssertionError(f"Unexpected particle_type={particle_type}")

        with (
            patch.object(self.service.dialogue_service.particle_factory, "create_particle", side_effect=create_particle_side_effect),
            patch("random.random", return_value=0.0),
            patch("random.choice", return_value=ship),
            patch.object(self.service.dialogue_service, "generate_chain_iteratively", return_value=[(gratitude_msg, 0.5)]),
        ):
            events = self.service.generate_nav_broadcast_chain(self.satellite, base_timestamp=10.0)

        assert len(events) == 2
        broadcast, gratitude = events
        assert broadcast.metadata["type"] == "nav_broadcast"
        assert gratitude.metadata["type"] == "gratitude"
        # gratitude timestamp = base + broadcast duration (5.0) + time offset
        assert gratitude.timestamp == 10.0 + 5.0 + 0.5
        assert gratitude.actor == pilot
        assert gratitude.metadata["ship_name"] == ship.name
        assert gratitude.metadata["pilot_name"] == pilot.name

    def test_generate_nav_broadcast_chain_gratitude_failure_does_not_block_broadcast(self):
        ship = Ship.objects.create(name="Test Ship", current_location=self.station, size="M", cargo="X", status="DOCK")
        Pilot.objects.create(name="Test Pilot", ship=ship)

        fake_broadcast_particle = SimpleNamespace(
            generate_nav_broadcast_text=lambda: "NAV UPDATE",
            get_modem_encoded_data=lambda: "101010",
            get_next_particle_probabilities=lambda: {"gratitude": 1.0},
        )
        fake_gratitude_particle = SimpleNamespace()

        def create_particle_side_effect(*, particle_type, **kwargs):
            return fake_broadcast_particle if particle_type == "nav_broadcast" else fake_gratitude_particle

        with (
            patch.object(self.service.dialogue_service.particle_factory, "create_particle", side_effect=create_particle_side_effect),
            patch("random.random", return_value=0.0),
            patch("random.choice", return_value=ship),
            patch.object(self.service.dialogue_service, "generate_chain_iteratively", side_effect=RuntimeError("LLM down")),
        ):
            events = self.service.generate_nav_broadcast_chain(self.satellite, base_timestamp=10.0)

        assert len(events) == 1
        assert events[0].metadata["type"] == "nav_broadcast"


class TestScriptServiceNavigationChains(TestCase):
    def setUp(self):
        galaxy = Galaxy.objects.create(name="G2", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="S2",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Sol2", orbits=system, star_type="G")
        self.planet = Planet.objects.create(name="Earth2", orbits=star, planet_type="TE", orbital_distance_au=1.0)
        self.station = Station.objects.create(name="Earth2 Orbital Control", orbits=self.planet)

        self.ship = Ship.objects.create(name="Ship", current_location=self.station, size="M", cargo="X", status="DOCK")
        self.pilot = Pilot.objects.create(name="Pilot", ship=self.ship)
        self.controller = Controller.objects.create(name="Earth2 Control", location=self.station)

        self.llm = Mock(temperature=0.25)
        self.service = ScriptService(self.llm)

        self.nav_event = NavigationEvent(
            origin=self.station,
            current=self.station,
            next=self.planet,
            destination=self.planet,
            maneuver=ManeuverType.TRANSFER,
            controller=self.station,
        )

    def test_build_nav_context_requires_location_names(self):
        bad_location = SimpleNamespace()  # no .name
        bad_nav_event = replace(self.nav_event, current=bad_location)
        with self.assertRaises(ValueError):
            self.service._build_nav_context(bad_nav_event, self.ship)

    def test_get_controller_prefers_assigned_controller_instance(self):
        assigned = Controller.objects.create(name="Assigned Controller", location=None)
        nav_event = replace(self.nav_event, controller=assigned)
        assert self.service._get_controller(nav_event) == assigned

    def test_get_controller_resolves_assigned_location_to_controller_actor(self):
        # controller field contains a Location (e.g., a station), resolve to Controller actor
        nav_event = replace(self.nav_event, controller=self.station)
        assert self.service._get_controller(nav_event).name == self.controller.name

    def test_get_controller_raises_when_assigned_location_has_no_controller(self):
        station2 = Station.objects.create(name="No Controller Station", orbits=self.planet)
        nav_event = replace(self.nav_event, controller=station2)
        with self.assertRaises(ValueError):
            self.service._get_controller(nav_event)

    def test_get_controller_uses_effective_controller_when_unassigned(self):
        nav_event = replace(self.nav_event, controller=None)
        with patch("mysite.universe.services.script_server.RouteService.effective_controller", return_value=self.controller):
            assert self.service._get_controller(nav_event) == self.controller

    def test_convert_messages_to_events_sets_actor_and_metadata(self):
        nav_event = replace(self.nav_event, controller=None)
        msgs = [
            (
                DialogueMessage.model_construct(
                    role=Role.PILOT,
                    speaker_callsign="PILOT",
                    recipient_callsign="CTRL",
                    message="REQUESTING CLEARANCE",
                ),
                0.0,
            ),
            (
                DialogueMessage.model_construct(
                    role=Role.CONTROLLER,
                    speaker_callsign="CTRL",
                    recipient_callsign="PILOT",
                    message="CLEARED",
                ),
                1.5,
            ),
        ]

        with patch.object(self.service, "_get_controller", return_value=self.controller):
            events = self.service._convert_messages_to_events(msgs, nav_event, self.ship)

        assert [e.timestamp for e in events] == [0.0, 1.5]
        assert events[0].actor == self.pilot
        assert events[1].actor == self.controller
        assert events[0].metadata["control_name"] == self.controller.name
        assert events[0].metadata["ship_name"] == self.ship.name.upper()
        assert "dialogue_message" in events[0].metadata

    def test_iter_navigation_events_maps_relative_to_absolute_and_applies_physics_gaps(self):
        nav1 = replace(self.nav_event, maneuver=ManeuverType.TRANSFER)
        nav2 = replace(self.nav_event, maneuver=ManeuverType.CIRCULARIZE)

        # Each chain has two events at offsets 0.0 and 1.0 with duration 2.0 on last event
        chain = [
            SimpleNamespace(timestamp=0.0, duration=2.0),
            SimpleNamespace(timestamp=1.0, duration=2.0),
        ]

        def parse_nav_event(_nav, _ship):
            # Return fresh copies so mutation isn't shared
            return [
                replace(Mock(spec=["timestamp", "duration"]), timestamp=0.0, duration=2.0),
                replace(Mock(spec=["timestamp", "duration"]), timestamp=1.0, duration=2.0),
            ]

        # We need real DialogueEvent dataclasses yielded; easiest is to patch parse_navigation_event
        # to return two DialogueEvents directly.
        from mysite.universe.models.event import DialogueEvent as DialogueEventDC

        chain_events = [
            DialogueEventDC(timestamp=0.0, actor=self.pilot, text="A", duration=2.0, metadata={}),
            DialogueEventDC(timestamp=1.0, actor=self.controller, text="B", duration=2.0, metadata={}),
        ]

        with (
            patch.object(self.service, "parse_navigation_event", return_value=chain_events),
            patch("mysite.universe.services.script_server.route_service.get_event_duration", return_value=10.0),
        ):
            out = list(self.service.iter_navigation_events([nav1, nav2], self.ship, use_physics_delays=True))

        # First chain is 그대로: 0.0, 1.0
        assert out[0].timestamp == 0.0
        assert out[1].timestamp == 1.0
        # Chain end = 0.0 + 1.0 + 2.0 = 3.0, next chain starts at 3.0 + 10.0 = 13.0
        assert out[2].timestamp == 13.0
        assert out[3].timestamp == 14.0

    def test_iter_navigation_events_advances_by_default_when_chain_empty(self):
        nav1 = replace(self.nav_event, maneuver=ManeuverType.TRANSFER)
        nav2 = replace(self.nav_event, maneuver=ManeuverType.CIRCULARIZE)

        from mysite.universe.models.event import DialogueEvent as DialogueEventDC

        with patch.object(self.service, "parse_navigation_event", side_effect=[[], [DialogueEventDC(timestamp=0.0, actor=self.pilot, text="A", duration=1.0, metadata={})]]):
            out = list(self.service.iter_navigation_events([nav1, nav2], self.ship, use_physics_delays=False))

        # Empty chain advances start by 2.0, so next chain's event at 0.0 becomes 2.0
        assert len(out) == 1
        assert out[0].timestamp == 2.0


class TestScriptServiceSingletonAndParsing(TestCase):
    def setUp(self):
        galaxy = Galaxy.objects.create(name="G3", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="S3",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Sol3", orbits=system, star_type="G")
        self.planet = Planet.objects.create(name="Earth3", orbits=star, planet_type="TE", orbital_distance_au=1.0)
        self.station = Station.objects.create(name="Earth3 Orbital Control", orbits=self.planet)
        self.ship = Ship.objects.create(name="Ship3", current_location=self.station, size="M", cargo="X", status="DOCK")
        self.pilot = Pilot.objects.create(name="Pilot3", ship=self.ship)
        self.controller = Controller.objects.create(name="Earth3 Control", location=self.station)

        self.nav_event = NavigationEvent(
            origin=self.station,
            current=self.station,
            next=self.planet,
            destination=self.planet,
            maneuver=ManeuverType.TRANSFER,
            controller=self.station,
        )

    def test_get_instance_is_singleton_and_resettable(self):
        ScriptService.reset_instance()
        llm1 = Mock(temperature=0.1)
        llm2 = Mock(temperature=0.9)

        s1 = ScriptService.get_instance(llm=llm1)
        s2 = ScriptService.get_instance(llm=llm1)
        assert s1 is s2

        # Passing a new llm updates instance.llm
        s3 = ScriptService.get_instance(llm=llm2)
        assert s3 is s1
        assert s3.llm is llm2

        ScriptService.reset_instance()
        s4 = ScriptService.get_instance(llm=llm1)
        assert s4 is not s1

    def test_parse_navigation_event_raises_without_pilot(self):
        ship = Ship.objects.create(name="NoPilot", current_location=self.station, size="M", cargo="X", status="DOCK")
        service = ScriptService(Mock())
        with self.assertRaises(ValueError):
            service.parse_navigation_event(self.nav_event, ship)

    def test_parse_navigation_event_converts_dialogue_messages_to_events(self):
        service = ScriptService(Mock(temperature=0.25))

        msg1 = DialogueMessage.model_construct(
            role=Role.PILOT,
            speaker_callsign=self.pilot.name.upper(),
            recipient_callsign=self.controller.name.upper(),
            message="REQUESTING TRANSFER",
        )
        msg2 = DialogueMessage.model_construct(
            role=Role.CONTROLLER,
            speaker_callsign=self.controller.name.upper(),
            recipient_callsign=self.pilot.name.upper(),
            message="CLEARED",
        )

        with (
            patch.object(service, "_get_controller", return_value=self.controller),
            patch.object(service, "_build_nav_context", return_value={"ship_name": self.ship.name.upper()}),
            patch.object(service.dialogue_service, "generate_chain_from_nav_event", return_value=[(msg1, 0.0), (msg2, 1.0)]),
        ):
            events = service.parse_navigation_event(self.nav_event, self.ship)

        assert [e.timestamp for e in events] == [0.0, 1.0]
        assert events[0].actor == self.pilot
        assert events[1].actor == self.controller
        assert events[0].metadata["ship_name"] == self.ship.name.upper()


class TestScriptServiceCommsCheck(TestCase):
    def setUp(self):
        galaxy = Galaxy.objects.create(name="G4", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="S4",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Sol4", orbits=system, star_type="G")
        planet = Planet.objects.create(name="Earth4", orbits=star, planet_type="TE", orbital_distance_au=1.0)
        station = Station.objects.create(name="Earth4 Orbital Control", orbits=planet)

        self.ship = Ship.objects.create(name="Ship4", current_location=station, size="M", cargo="X", status="DOCK")
        self.pilot = Pilot.objects.create(name="Pilot4", ship=self.ship)
        self.satellite = Satellite.objects.create(name="Earth4 Navsat")
        self.service = ScriptService(Mock(temperature=0.25))

    def test_generate_comms_check_chain_creates_two_events_with_roles(self):
        initial_particle = object()
        msg_pilot = DialogueMessage.model_construct(
            role=Role.PILOT,
            speaker_callsign="PILOT4",
            recipient_callsign="EARTH4 NAVSAT",
            message="COMMS CHECK",
        )
        msg_sat = DialogueMessage.model_construct(
            role=Role.SATELLITE,
            speaker_callsign="EARTH4 NAVSAT",
            recipient_callsign="PILOT4",
            message="LOUD AND CLEAR",
        )

        with (
            patch.object(self.service.dialogue_service.particle_factory, "create_particle", return_value=initial_particle),
            patch.object(self.service.dialogue_service, "generate_chain_iteratively", return_value=[(msg_pilot, 0.0), (msg_sat, 1.0)]),
        ):
            events = self.service.generate_comms_check_chain(
                pilot=self.pilot,
                satellite=self.satellite,
                ship=self.ship,
                base_timestamp=50.0,
            )

        assert len(events) == 2
        assert events[0].timestamp == 50.0
        assert events[1].timestamp == 51.0
        assert events[0].actor == self.pilot
        assert events[1].actor == self.satellite
        assert events[0].metadata["type"] == "comms_check"
        assert events[1].metadata["type"] == "satellite_response"

