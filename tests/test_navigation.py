from __future__ import annotations


from django.test import TestCase

import io
from contextlib import redirect_stdout

from mysite.universe.models.base import Location
from mysite.universe.models.celestial import Galaxy, StarSystem, Star, Planet, Moon
from mysite.universe.models.constants import TypeName
from mysite.universe.models.navigation import (
    ManeuverType,
    NavigationEvent,
    UniverseGraph,
    build_navigation_events,
    find_controlling_station,
    get_concrete_type,
    is_planetary,
    requires_plane_change,
    find_nearest_node as bfs_find_nearest_node,
    print_tree,
    _is_control_station,
    _normalize,
)
from mysite.universe.models.scale import Scale
from mysite.universe.models.station import Station


class TestBuildNavigationEvents(TestCase):
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
        self.earth = Planet.objects.create(
            name="Earth", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )
        self.mars = Planet.objects.create(
            name="Mars", orbits=star, planet_type="TE", orbital_distance_au=1.5
        )
        self.station = Station.objects.create(
            name="Earth Orbital Control", orbits=self.earth, scale=Scale.STATION
        )

    def test_empty_path_returns_empty_events(self):
        assert build_navigation_events([]) == []

    def test_station_departure_prepends_undock_and_initial_circularize(self):
        events = build_navigation_events([self.station, self.earth])
        assert events[0].maneuver == ManeuverType.UNDOCK
        assert events[1].maneuver == ManeuverType.CIRCULARIZE
        assert events[0].origin is None

    def test_planet_to_planet_inserts_plane_change_then_transfer(self):
        events = build_navigation_events([self.earth, self.mars])
        maneuvers = [e.maneuver for e in events]
        assert maneuvers[0] == ManeuverType.PLANE_CHANGE
        assert maneuvers[1] == ManeuverType.TRANSFER

    def test_final_maneuver_dock_when_destination_station(self):
        events = build_navigation_events([self.earth, self.station])
        assert events[-1].maneuver == ManeuverType.DOCK

    def test_final_maneuver_landing_when_destination_planet(self):
        events = build_navigation_events([self.station, self.earth])
        # Last leg ends at Earth (planetary body)
        assert events[-1].maneuver == ManeuverType.LANDING


class TestNavigationHelpers(TestCase):
    def setUp(self):
        galaxy = Galaxy.objects.create(name="G2", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="S2",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="Star", orbits=system, star_type="G")
        self.earth = Planet.objects.create(
            name="Earth2", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )
        self.moon = Moon.objects.create(name="Moon2", orbits=self.earth, moon_type="R")
        self.station = Station.objects.create(
            name="Earth2 Control", orbits=self.earth, scale=Scale.STATION
        )

        UniverseGraph.get_instance().rebuild_graph()

    def test_get_concrete_type(self):
        assert get_concrete_type(self.earth) == "Planet"

    def test_is_planetary_true_for_planet_orbiting_star(self):
        assert is_planetary(self.earth) is True

    def test_is_planetary_false_for_moon_orbiting_planet(self):
        # moon's parent is a planet, not a star
        assert is_planetary(self.moon) is False

    def test_requires_plane_change_true_when_parents_differ(self):
        # current and destination orbit different parents => plane change required
        other_star = Star.objects.create(
            name="Other", orbits=self.earth.orbits.orbits, star_type="G"
        )
        other_planet = Planet.objects.create(
            name="OtherPlanet",
            orbits=other_star,
            planet_type="TE",
            orbital_distance_au=2.0,
        )

        ev = NavigationEvent(
            origin=self.earth,
            current=self.earth,
            next=other_planet,
            destination=other_planet,
            maneuver=ManeuverType.TRANSFER,
        )
        assert requires_plane_change(ev) is True

    def test_requires_plane_change_false_when_parents_missing(self):
        # If any orbits are missing, function should return False (can't reason).
        loc = Location.objects.create(name="Loose", scale=Scale.STATION)
        ev = NavigationEvent(
            origin=loc,
            current=loc,
            next=loc,
            destination=loc,
            maneuver=ManeuverType.TRANSFER,
        )
        assert requires_plane_change(ev) is False

    def test_find_controlling_station_prefers_keyword_station(self):
        # Already have "Earth2 Control" which includes "Control"
        controller = find_controlling_station(self.earth)
        assert controller is not None
        assert controller.name == "Earth2 Control"

    def test_find_controlling_station_returns_nearest_planetary_when_no_stations(self):
        # Remove stations in this local area
        Station.objects.all().delete()
        UniverseGraph.get_instance().rebuild_graph()
        controller = find_controlling_station(self.moon)
        assert controller is not None
        assert controller.get_type_name() in TypeName.PLANETARY_BODIES

    def test_find_controlling_station_returns_none_for_galaxy_when_filtered_to_planet_scale(
        self,
    ):
        # For a galaxy, local_graph with PLANET scale returns empty, so controller is None.
        galaxy_loc = Galaxy.objects.create(
            name="Remote Galaxy", galaxy_type="SP", galaxy_size="L"
        )
        UniverseGraph.get_instance().rebuild_graph()
        assert find_controlling_station(galaxy_loc) is None

    def test_module_level_find_nearest_node_bfs(self):
        # Simple BFS over a small graph, without touching UniverseGraph.
        a, b, c = object(), object(), object()

        neighbors = {a: [b], b: [c], c: []}

        def get_neighbors(x):
            return neighbors.get(x, [])

        found = bfs_find_nearest_node(
            a, target_check=lambda x: x is c, get_neighbors=get_neighbors
        )
        assert found is c


class TestCelestialScaleDefaults(TestCase):
    def test_celestial_subclasses_override_location_default_scale(self):
        """
        Location.scale defaults to STATION; Celestial subclasses should override that
        when callers don't explicitly pass scale.
        """
        galaxy = Galaxy.objects.create(name="DG", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="DS",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="DStar", orbits=system, star_type="G")
        planet = Planet.objects.create(
            name="DPlanet", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )
        moon = Moon.objects.create(name="DMoon", orbits=planet, moon_type="R")

        assert galaxy.scale == Scale.GALAXY
        assert system.scale == Scale.STARSYSTEM
        assert star.scale == Scale.STAR
        assert planet.scale == Scale.PLANET
        assert moon.scale == Scale.MOON


class TestUniverseGraphEdgeCases(TestCase):
    def setUp(self):
        galaxy = Galaxy.objects.create(name="UG", galaxy_type="SP", galaxy_size="L")
        system = StarSystem.objects.create(
            name="US",
            orbits=galaxy,
            galactic_x_ly=0.0,
            galactic_y_ly=0.0,
            galactic_z_ly=0.0,
        )
        star = Star.objects.create(name="UStar", orbits=system, star_type="G")
        self.planet = Planet.objects.create(
            name="UPlanet", orbits=star, planet_type="TE", orbital_distance_au=1.0
        )
        self.station = Station.objects.create(
            name="UStation", orbits=self.planet, scale=Scale.STATION
        )
        self.universe = UniverseGraph.get_instance()
        self.universe.rebuild_graph()

    def test_get_neighbors_returns_empty_for_deleted_location(self):
        # Cover the "graph might be stale" branch: create a new node after the graph
        # was built; get_neighbors should rebuild and then return correct neighbors.
        new_station = Station.objects.create(
            name="UStation2", orbits=self.planet, scale=Scale.STATION
        )
        neighbors = self.universe.get_neighbors(new_station)
        assert {n.name for n in neighbors} == {"UPlanet"}

    def test_get_neighbors_returns_empty_for_unsaved_location(self):
        # Unsaved objects have no id and will not exist in the graph.
        unsaved = Location(name="Unsaved", scale=Scale.PLANET)
        assert self.universe.get_neighbors(unsaved) == []

    def test_get_path_raises_value_error_when_no_path_exists(self):
        # A plain Location node has no orbital edges; it's disconnected from the celestial graph.
        disconnected = Location.objects.create(name="Disconnected", scale=Scale.PLANET)
        self.universe.rebuild_graph()
        with self.assertRaises(ValueError):
            self.universe.get_path(self.planet, disconnected)

    def test_get_local_graph_accepts_numeric_max_scale(self):
        # Pass a numeric OrderedScale value; should behave like PLANET scale.
        local = self.universe.get_local_graph(self.station, max_scale=3)
        names = {loc.name for loc in local}
        assert "UStation" in names
        assert "UPlanet" in names

    def test_get_local_graph_defaults_to_location_scale_when_max_scale_none(self):
        # station scale defaults to STATION; should not include larger-scale neighbors (planet).
        local = self.universe.get_local_graph(self.station, max_scale=None)
        assert [loc.name for loc in local] == ["UStation"]

    def test_get_local_graph_visited_skip_branch_with_cycle(self):
        # Construct a 3-cycle using Moon.orbits (valid FK type) to force re-queueing.
        a = Moon.objects.create(name="CycleA", orbits=self.planet, moon_type="R")
        b = Moon.objects.create(name="CycleB", orbits=a, moon_type="R")
        c = Moon.objects.create(name="CycleC", orbits=b, moon_type="R")
        a.orbits = c
        a.save()
        self.universe.rebuild_graph()

        local = self.universe.get_local_graph(a, max_scale=Scale.MOON)
        names = {loc.name for loc in local}
        assert {"CycleA", "CycleB", "CycleC"} <= names

    def test_find_nearest_node_respects_max_scale_filter(self):
        # Start at station; a planet is reachable, but if max_scale is STATION, it should skip planet.
        found = self.universe.find_nearest_node(
            start=self.station,
            condition=lambda loc: loc.get_type_name() == TypeName.PLANET,
            max_scale=Scale.STATION,
        )
        assert found is None

    def test_find_nearest_node_returns_first_match(self):
        found = self.universe.find_nearest_node(
            start=self.station,
            condition=lambda loc: loc.get_type_name() == TypeName.PLANET,
            max_scale=Scale.PLANET,
        )
        assert found is not None
        assert found.name == "UPlanet"

    def test_get_neighbors_rebuilds_if_graph_none(self):
        self.universe._graph = None
        neighbors = self.universe.get_neighbors(self.station)
        assert {n.name for n in neighbors} == {"UPlanet"}

    def test_get_path_rebuilds_if_graph_none(self):
        self.universe._graph = None
        path = self.universe.get_path(self.station, self.planet)
        assert [p.name for p in path] == ["UStation", "UPlanet"]

    def test_print_tree_smoke(self):
        # Ensure the debug helper doesn't crash and includes expected node names.
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_tree(self.universe, self.planet.id)
        out = buf.getvalue()
        assert "UPlanet" in out


class TestControlStationKeywordHelpers(TestCase):
    def test_is_control_station_keywords(self):
        assert _is_control_station("Luna Orbital Control") is True
        assert _is_control_station("Freight Dispatch") is True
        assert _is_control_station("Research Platform") is False


class TestNavigationEdgeCases(TestCase):
    """
    Covers uncovered branches in navigation.py utility functions.
    """

    def test_bfs_find_nearest_node_returns_none_when_no_match(self):
        """
        find_nearest_node exhausts the graph without finding a match and
        returns None (navigation.py line 455).
        """
        a, b, c = object(), object(), object()
        neighbors_map = {a: [b], b: [c], c: []}

        result = bfs_find_nearest_node(
            a,
            target_check=lambda x: False,  # never matches
            get_neighbors=lambda x: neighbors_map.get(x, []),
        )
        assert result is None

    def test_normalize_passes_model_instance_through(self):
        """_normalize returns a non-tuple item unchanged (line 464)."""
        sentinel = object()
        assert _normalize(sentinel) is sentinel

    def test_normalize_extracts_first_element_from_tuple(self):
        """_normalize extracts item[0] when given a tuple (lines 462-463)."""
        inner = object()
        result = _normalize((inner, "extra"))
        assert result is inner

    def test_is_planetary_false_for_planet_with_no_orbits(self):
        """
        A Location at PLANET scale with no `orbits` attribute (raw Location row,
        not a Planet subclass) triggers the `orbits is None` branch (line 392).
        """
        raw_loc = Location.objects.create(name="NavEdge Planet Loc", scale=Scale.PLANET)
        # get_concrete_instance() on a raw Location returns self, which has no orbits
        assert is_planetary(raw_loc) is False

    def test_print_tree_handles_node_with_no_location_data(self):
        """
        print_tree prints a fallback 'Unknown' line when a graph node has no
        'location' key in its data dict (navigation.py line 553).
        """
        import networkx as nx

        # Build a minimal UniverseGraph-like object whose internal graph has
        # a node without 'location' data.
        universe = UniverseGraph.__new__(UniverseGraph)
        g = nx.Graph()
        g.add_node(99)  # no 'location' key in node data
        universe._graph = g

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_tree(universe, 99)
        out = buf.getvalue()
        assert "Unknown" in out
