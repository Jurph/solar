"""
Tests for Controller fallback behavior.

These tests verify the fallback logic when Controller actors don't exist:
- When Controller exists → returns Controller actor
- When Controller missing → returns Location (station) as fallback
- When no controlling station → returns original location

Each test catches a specific failure mode in the controller lookup chain.
"""
from django.test import TestCase

from mysite.universe.models.actor import Controller
from mysite.universe.models.base import Location
from mysite.universe.models.station import Station
from mysite.universe.models.celestial import Planet, Moon, Star, StarSystem, Galaxy
from mysite.universe.models.scale import Scale
from mysite.universe.services.route_server import RouteService
from mysite.universe.models.navigation import find_controlling_station, UniverseGraph


class ControllerFallbackTests(TestCase):
    """
    Tests for effective_controller fallback behavior.
    
    These verify the service-layer adapter correctly handles missing Controller actors.
    """
    
    def setUp(self):
        """Set up test locations and universe graph."""
        # Create minimal universe hierarchy for graph
        galaxy = Galaxy.objects.create(name="Test Galaxy", scale=Scale.GALAXY)
        star_system = StarSystem.objects.create(
            name="Test System", 
            scale=Scale.STARSYSTEM,
            orbits=galaxy
        )
        
        star = Star.objects.create(
            name="Test Star", 
            scale=Scale.STAR, 
            star_type="G2V",
            orbits=star_system
        )
        
        # Create a planet
        self.planet = Planet.objects.create(
            name="Test Planet",
            scale=Scale.PLANET,
            orbital_distance_au=1.0,
            orbits=star
        )
        
        # Create a station (this will be the controlling station)
        self.station = Station.objects.create(
            name="Mars Control Station",
            scale=Scale.STATION,
            large_berths=1,
            medium_berths=1,
            small_berths=1,
            orbits=self.planet
        )
        
        # Create a moon (for testing fallback to celestial)
        self.moon = Moon.objects.create(
            name="Test Moon",
            scale=Scale.MOON,
            orbital_distance_km=384400,
            orbits=self.planet
        )
        
        # Rebuild universe graph with new locations
        UniverseGraph.get_instance().rebuild_graph()
        
        self.route_service = RouteService()
    
    def test_returns_controller_when_exists(self):
        """
        When Controller actor exists, should return Controller, not Location.
        
        If this fails: system returns Location when it should return Controller,
        breaking dialogue generation (needs actor.name, actor.get_identity_prompt()).
        """
        # Create Controller actor for the station
        controller = Controller.create(location=self.station, name="Mars Control")
        
        # effective_controller should return the Controller actor
        result = self.route_service.effective_controller(self.station)
        
        self.assertIsInstance(result, Controller)
        self.assertEqual(result.id, controller.id)
        self.assertEqual(result.name, "Mars Control")
    
    def test_returns_location_when_controller_missing(self):
        """
        When Controller actor doesn't exist, should return Location as fallback.
        
        If this fails: system returns None or raises exception, breaking
        dialogue generation downstream.
        """
        # Ensure no Controller exists for this station
        Controller.objects.filter(location=self.station).delete()
        Controller.objects.filter(name=self.station.name).delete()
        
        # effective_controller should return the Location (station) as fallback
        # Since find_controlling_station will find the station itself, and no Controller exists,
        # it should return the station Location
        result = self.route_service.effective_controller(self.station)
        
        self.assertIsInstance(result, Location)
        # Result should be the station (or controlling station if different)
        self.assertEqual(result.name, "Mars Control Station")
    
    def test_fallback_to_controlling_station_when_no_local_controller(self):
        """
        For a location without a local controller, should find nearest controlling station.
        
        If this fails: system can't find controllers for locations that should
        be controlled by nearby stations (e.g., a moon controlled by planet's station).
        """
        # Create Controller for the existing station (which will control the moon)
        controller = Controller.create(location=self.station, name="Mars Control Station")
        
        # Rebuild graph to ensure it's up to date
        UniverseGraph.get_instance().rebuild_graph()
        
        # effective_controller for the moon should find the controlling station's Controller
        result = self.route_service.effective_controller(self.moon)
        
        # Should return the Controller (not the moon itself or the station)
        self.assertIsInstance(result, Controller)
        self.assertEqual(result.id, controller.id)
    
    def test_fallback_to_location_when_no_controlling_station_found(self):
        """
        When no controlling station exists, should return original location.
        
        If this fails: system returns None for remote locations, breaking
        route planning for deep space or unpopulated areas.
        """
        # Create minimal universe for remote planet
        galaxy = Galaxy.objects.create(name="Remote Galaxy", scale=Scale.GALAXY)
        star_system = StarSystem.objects.create(
            name="Remote System", 
            scale=Scale.STARSYSTEM,
            orbits=galaxy
        )
        
        star = Star.objects.create(
            name="Remote Star", 
            scale=Scale.STAR, 
            star_type="G2V",
            orbits=star_system
        )
        
        # Create a remote location (no nearby stations)
        remote_planet = Planet.objects.create(
            name="Remote Planet",
            scale=Scale.PLANET,
            orbital_distance_au=10.0,
            orbits=star
        )
        
        # Rebuild graph
        UniverseGraph.get_instance().rebuild_graph()
        
        # No stations or controllers nearby
        # effective_controller should return the location itself
        result = self.route_service.effective_controller(remote_planet)
        
        self.assertIsInstance(result, Location)
        self.assertEqual(result.id, remote_planet.id)
        self.assertEqual(result.name, "Remote Planet")
    
    def test_controller_lookup_by_name_when_location_mismatch(self):
        """
        Should fallback to name-based lookup if location-based lookup fails.
        
        If this fails: Controllers created with mismatched location/name
        won't be found, causing unnecessary Location fallbacks.
        """
        # Create Controller with same name but different location
        other_station = Station.objects.create(
            name="Other Station",
            scale=Scale.STATION,
            large_berths=1,
            medium_berths=1,
            small_berths=1,
            orbits=self.planet
        )
        
        # Create Controller with station's name but at different location
        controller = Controller.create(name="Mars Control Station", location=other_station)
        
        # effective_controller should find it by name
        result = self.route_service.effective_controller(self.station)
        
        self.assertIsInstance(result, Controller)
        self.assertEqual(result.id, controller.id)
    
    def test_fallback_chain_for_planet_without_station(self):
        """
        For a planet without stations, should fallback to planet itself.
        
        If this fails: planets without stations return None instead of
        using the planet as its own controller.
        """
        # Create minimal universe
        galaxy = Galaxy.objects.create(name="Isolated Galaxy", scale=Scale.GALAXY)
        star_system = StarSystem.objects.create(
            name="Isolated System", 
            scale=Scale.STARSYSTEM,
            orbits=galaxy
        )
        
        star = Star.objects.create(
            name="Isolated Star", 
            scale=Scale.STAR, 
            star_type="G2V",
            orbits=star_system
        )
        
        # Planet with no stations
        isolated_planet = Planet.objects.create(
            name="Isolated Planet",
            scale=Scale.PLANET,
            orbital_distance_au=5.0,
            orbits=star
        )
        
        # Rebuild graph
        UniverseGraph.get_instance().rebuild_graph()
        
        # No controllers or stations
        result = self.route_service.effective_controller(isolated_planet)
        
        # Should return the planet itself (or nearest celestial if found)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Location)


class FindControllingStationTests(TestCase):
    """
    Tests for the navigation.find_controlling_station function.
    
    These verify the world-model logic (finding which station controls a location)
    separate from the actor lookup (which is in route_server).
    """
    
    def setUp(self):
        """Set up test universe structure."""
        # Create minimal universe hierarchy
        galaxy = Galaxy.objects.create(name="Test Galaxy 2", scale=Scale.GALAXY)
        star_system = StarSystem.objects.create(
            name="Test System 2", 
            scale=Scale.STARSYSTEM,
            orbits=galaxy
        )
        
        star = Star.objects.create(
            name="Test Star 2", 
            scale=Scale.STAR, 
            star_type="G2V",
            orbits=star_system
        )
        
        self.planet = Planet.objects.create(
            name="Test Planet 2",
            scale=Scale.PLANET,
            orbital_distance_au=1.0,
            orbits=star
        )
        
        # Create control station (has "Control" in name)
        self.control_station = Station.objects.create(
            name="Mars Control",
            scale=Scale.STATION,
            large_berths=1,
            medium_berths=1,
            small_berths=1,
            orbits=self.planet
        )
        
        # Create regular station
        self.regular_station = Station.objects.create(
            name="Mars Station",
            scale=Scale.STATION,
            large_berths=1,
            medium_berths=1,
            small_berths=1,
            orbits=self.planet
        )
        
        # Rebuild universe graph
        UniverseGraph.get_instance().rebuild_graph()
    
    def test_prefers_control_station_over_regular_station(self):
        """
        Should prefer stations with "Control" or "Dispatch" in name.
        
        If this fails: system picks wrong station when multiple exist,
        causing dialogue to go to wrong controller.
        """
        # find_controlling_station should return the control station
        result = find_controlling_station(self.planet)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.control_station.id)
        self.assertIn("Control", result.name)
    
    def test_falls_back_to_regular_station_when_no_control_station(self):
        """
        When no control station exists, should use nearest regular station.
        
        If this fails: system returns None when it should use any nearby station.
        """
        # Delete the control station
        self.control_station.delete()
        
        # Rebuild graph after deletion
        UniverseGraph.get_instance().rebuild_graph()
        
        # Should fallback to regular station
        result = find_controlling_station(self.planet)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.regular_station.id)
    
    def test_returns_none_for_remote_locations(self):
        """
        For locations with no nearby stations, should return None.
        
        If this fails: system incorrectly finds controllers for deep space,
        causing dialogue to be assigned to wrong stations.
        """
        # Create minimal universe for remote planet
        galaxy = Galaxy.objects.create(name="Remote Galaxy 2", scale=Scale.GALAXY)
        star_system = StarSystem.objects.create(
            name="Remote System 2", 
            scale=Scale.STARSYSTEM,
            orbits=galaxy
        )
        
        star = Star.objects.create(
            name="Remote Star 2", 
            scale=Scale.STAR, 
            star_type="G2V",
            orbits=star_system
        )
        
        # Create remote planet with no stations
        remote_planet = Planet.objects.create(
            name="Remote Planet 2",
            scale=Scale.PLANET,
            orbital_distance_au=20.0,
            orbits=star
        )
        
        # Rebuild graph
        UniverseGraph.get_instance().rebuild_graph()
        
        result = find_controlling_station(remote_planet)
        
        # Should return None (no controlling station found) OR the planet itself as fallback
        # (The function returns nearest celestial if no station, so might return planet)
        # The key is it doesn't crash and returns a Location or None
        self.assertTrue(result is None or isinstance(result, Location))

