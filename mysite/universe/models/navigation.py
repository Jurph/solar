from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Any
import networkx as nx
from itertools import chain
from django.db import models
from .base import Location
from .station import Station

class ManeuverType(Enum):
    """Types of spacecraft maneuvers in our universe"""
    CIRCULARIZE = "circularize"    
    DOCK = "dock"                  
    HYPERSPACE = "hyperspace"      
    LANDING = "landing"            
    LAUNCH = "launch"              
    PLANE_CHANGE = "plane_change"  
    TRANSFER = "transfer"          
    UNDOCK = "undock"              
    # TODO: consider REENTRY as a future option, where we evaluate whether or not the target
    # has an atmosphere 

@dataclass
class NavigationStep:
    """A single step in a navigation plan"""
    contact_station: Station
    maneuver: ManeuverType
    target: Location

class UniverseGraph:
    """Graph representation of the universe for navigation"""
    _instance = None
    _graph: Optional[nx.Graph] = None
    
    @classmethod
    def get_instance(cls) -> 'UniverseGraph':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.rebuild_graph()  # Build the graph immediately
        return cls._instance
                
    def _get_relation_items(self, obj: Any, attr_name: str):
        """Helper to safely obtain items from a reverse relationship."""
        items = getattr(obj, attr_name, [])
        # If the attribute has an .all() method (as Django managers do), use it.
        if hasattr(items, "all"):
            return items.all()
        # Otherwise assume it's already an iterable (list, etc.)
        return items

    def _normalize(self, item: Any) -> Any:
        """
        Normalize a related item to a model instance.
        If the item is a tuple, assume the first element is the model.
        """
        if isinstance(item, tuple):
            return item[0]
        return item

    def rebuild_graph(self) -> None:
        """Rebuild the universe graph from database relationships with full hierarchy"""
        G = nx.Graph()
        
        # Retrieve all subclass objects so that we get their real types.
        from mysite.universe.models import Galaxy, StarSystem, Star, Planet, Moon, Station
        
        objects = list(
            {
                obj.pk: obj
                for obj in chain(
                    Galaxy.objects.all(),
                    StarSystem.objects.all(),
                    Star.objects.all(),
                    Planet.objects.all(),
                    Moon.objects.all(),
                    Station.objects.all(),
                )
            }.values()
        )
        
        # First add all nodes
        for loc in objects:
            G.add_node(loc.id, name=loc.name)
            print(f"{loc.id}: {loc.name} is of type {type(loc)}")
        
        print("\nAdded all nodes. Now creating edges:")
        
        for loc in objects:
            # Upward edge: if this object defines an 'orbits' attribute
            if hasattr(loc, "orbits"):
                parent = loc.orbits  # May be None even if the attribute exists.
                if parent:
                    parent = self._normalize(parent)
                    if hasattr(parent, "id"):
                        G.add_edge(loc.id, parent.id)
                        print(f"Added upward edge: {loc.name} <-> {parent.name}")
            
            # Downward edges using reverse relationships:
            if hasattr(loc, "star_systems"):
                for system in self._get_relation_items(loc, "star_systems"):
                    system = self._normalize(system)
                    if hasattr(system, "id"):
                        G.add_edge(loc.id, system.id)
                        print(f"Added star system edge: {loc.name} <-> {system.name}")
            
            if hasattr(loc, "stars"):
                for star in self._get_relation_items(loc, "stars"):
                    star = self._normalize(star)
                    if hasattr(star, "id"):
                        G.add_edge(loc.id, star.id)
                        print(f"Added star edge: {loc.name} <-> {star.name}")
            
            if hasattr(loc, "planets"):
                for planet in self._get_relation_items(loc, "planets"):
                    planet = self._normalize(planet)
                    if hasattr(planet, "id"):
                        G.add_edge(loc.id, planet.id)
                        print(f"Added planet edge: {loc.name} <-> {planet.name}")
            
            if hasattr(loc, "moons"):
                for moon in self._get_relation_items(loc, "moons"):
                    moon = self._normalize(moon)
                    if hasattr(moon, "id"):
                        G.add_edge(loc.id, moon.id)
                        print(f"Added moon edge: {loc.name} <-> {moon.name}")
            
            if hasattr(loc, "orbiting_stations"):
                for station in self._get_relation_items(loc, "orbiting_stations"):
                    station = self._normalize(station)
                    if hasattr(station, "id"):
                        G.add_edge(loc.id, station.id)
                        print(f"Added station edge: {loc.name} <-> {station.name}")
        
        print(f"\nGraph built with {len(G.nodes)} nodes and {len(G.edges())} edges")
        self._graph = G

    def get_path(self, origin: Location, destination: Location) -> List[Location]:
        """Find shortest path between two locations"""
        if not self._graph:
            self.rebuild_graph()
            
        print(f"\nSearching for path from {origin.name} to {destination.name}")
        print(f"Origin ID: {origin.id}, Destination ID: {destination.id}")
        
        try:
            path = nx.shortest_path(self._graph, origin.id, destination.id)
            print(f"Found path: {path}")
            from mysite.universe.models import Location  # re-import for clarity
            return [Location.objects.get(id=node_id) for node_id in path]
        except nx.NetworkXNoPath:
            print("\nGraph state:")
            print(f"Nodes: {list(self._graph.nodes)}")
            print(f"Edges: {list(self._graph.edges)}")
            raise ValueError(f"No valid route exists between {origin.name} and {destination.name}")

def _normalize(item: Any) -> Any:
    """
    Normalize a related item to a model instance.
    If the item is a tuple, assume the first element is the model.
    """
    if isinstance(item, tuple):
        return item[0]
    return item

def effective_contact_station(location: Location) -> Optional[Station]:
    """
    Recursively find the station in control for a location.

    - If the location itself is a station, it is the effective station.
    - Otherwise, look for any stations orbiting the location:
       * First, attempt to use the reverse relationship attribute "orbiting_stations".
       * If that is empty (or not available), fall back to a direct query from Station.
       * If one station is found, return it.
       * If several exist, prefer one whose name contains "Control",
         otherwise return the first available.
    - If no local station is found, traverse upward via the 'orbits' relationship
      (using normalization to handle tuple values).
      
    This ensures that, for example, a moon like Phobos (or Io when it has no local station)
    can inherit its effective control from its parent (e.g. Mars Control or Jupiter Control),
    but if a location has a local station (even if not flagged "Control"), that station is used.
    """
    # If the location itself is a Station, return it.
    if isinstance(location, Station):
        return location

    station_list = []
    # Try to retrieve reverse related stations (if defined).
    if hasattr(location, "orbiting_stations"):
        try:
            station_list = list(location.orbiting_stations.all())
        except Exception:
            station_list = []
    # Fall back: in case the reverse attribute isn't properly populated.
    if not station_list:
        station_list = list(Station.objects.filter(orbits=location))

    if station_list:
        if len(station_list) == 1:
            return station_list[0]
        # If multiple stations exist, prefer one with "Control" in its name.
        for s in station_list:
            if "Control" in s.name:
                return s
        return station_list[0]

    # If no local station is found, traverse upward using the "orbits" relationship.
    parent = getattr(location, "orbits", None)
    if parent:
        parent = _normalize(parent)
        return effective_contact_station(parent)
    return None

def plan_navigation_steps(path: List[Location]) -> List[NavigationStep]:
    """
    Given a list of Location objects representing the path from origin to destination,
    produce a list of NavigationStep objects that adhere to the rule:
    the effective (or current) contact station remains in control until a location
    with its own station is reached.
    """
    steps: List[NavigationStep] = []
    if not path:
        return steps

    # Initialize with the starting point
    # If we're starting at a station, that IS our contact station
    if isinstance(path[0], Station):
        current_station = path[0]
    else:
        current_station = effective_contact_station(path[0])
        if current_station is None:
            raise ValueError(f"No effective station found for starting location {path[0].name}")

    for from_node, to_node in zip(path, path[1:]):
        # Get the effective station for the destination
        dest_station = effective_contact_station(to_node)
        
        # Create the navigation step
        # If we're at a station, use it as the contact point
        if isinstance(from_node, Station):
            contact_station = from_node
        else:
            contact_station = current_station

        step = NavigationStep(
            contact_station=contact_station,
            maneuver=ManeuverType.TRANSFER,
            target=to_node,
        )
        steps.append(step)

        # Update the current station if we've reached a new control point
        if dest_station is not None:
            current_station = dest_station

    return steps