from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Any
import networkx as nx
from .base import Location
from .station import Station
from collections import deque
from django.core.exceptions import ObjectDoesNotExist
from .scale import OrderedScale

class ManeuverType(Enum):
    """Types of spacecraft maneuvers in our universe"""
    CIRCULARIZE = "circularize"
    DEORBIT = "deorbit"
    DIRECT_ASCENT = "direct ascent"
    DOCK = "dock"
    HYPERSPACE = "hyperspace"
    INSERTION = "insertion"         # always followed by circularization
    LANDING = "landing"
    LAUNCH = "launch"               # always followed by orbital insertion
    PLANE_CHANGE = "plane change"
    SUBLIGHT = "sublight"
    TRANSFER = "transfer"
    UNDOCK = "undock"               # always followed by orbital insertion
    # TODO: add AEROBRAKING as a subset of INSERTION
    # TODO: consider REENTRY as a future option, where we evaluate whether or not the target
    # has an atmosphere

@dataclass
class NavigationStep:
    """A single step in a navigation plan"""
    contact_station: Station
    maneuver: ManeuverType
    target: Location
    
@dataclass
class NavigationEvent:
    maneuver: ManeuverType
    target: Location
    description: str = ""


# -------------------------------------------------------------------
# Event Builder
#
# The following function builds a sequence of events using our world‑building rules:
#
#  · Departing from a Station requires a LAUNCH event. 
#  · After LAUNCH, we generally execute a CIRCULARIZE maneuver (to get into the proper orbit).
#  · For transfers between two Planets, we do a PLANE_CHANGE followed by a TRANSFER.
#  · Upon entering a Planet's or Moon's sphere of influence we circularize.
#  · The final event is either DOCK (if the target is a Station) or LAND (if it's a Moon/Planet).
#
# (Additional rules—like hyperspace transitions when changing StarSystems—can be inserted here.)
# -------------------------------------------------------------------
def build_navigation_events(path: List[Location]) -> List[NavigationEvent]:
    """
    Build a sequence of NavigationEvent objects from a path of Locations.
    
    Uses world-building rules (see World Building Rules.md):
    - If the starting location is a Station, begin with a LAUNCH event and then a CIRCULARIZE.
    - Traveling between two Planets requires a PLANE_CHANGE followed by a TRANSFER.
    - Approaching a Planet or Moon calls for a circularization.
    - The final maneuver is DOCK if the destination is a Station or LAND if it is not.
    
    This builder can be extended to include other events (e.g. HYPERSPACE) as needed.
    """
    events: List[NavigationEvent] = []
    if not path:
        return events

    # Helper: get the concrete type name from a location.
    def type_of(loc: Location) -> str:
        return loc.get_concrete_instance().get_type_name()
    
    # Determine the departure type of the first node.
    departure = path[0]
    depart_type = type_of(departure)
    if depart_type == "Station":
        events.append(NavigationEvent(
            maneuver=ManeuverType.LAUNCH,
            target=departure,
            description=f"Departing from station {departure.name}: Launch initiated."
        ))
        # Following a launch, we generally circularize.
        events.append(NavigationEvent(
            maneuver=ManeuverType.CIRCULARIZE,
            target=departure,
            description="Initial orbital circularization after launch."
        ))
    
    # Process each segment of the path.
    for i in range(len(path) - 1):
        current = path[i]
        nxt = path[i + 1]
        current_type = type_of(current)
        next_type = type_of(nxt)
        
        # Rule: If traveling between two Planets, perform a PLANE_CHANGE and then a TRANSFER.
        if current_type == "Planet" and next_type == "Planet":
            events.append(NavigationEvent(
                maneuver=ManeuverType.PLANE_CHANGE,
                target=nxt,
                description=f"Plane change maneuver from {current.name} to align for transfer orbit."
            ))
            events.append(NavigationEvent(
                maneuver=ManeuverType.TRANSFER,
                target=nxt,
                description=f"Transfer burn from {current.name} towards {nxt.name}."
            ))
        else:
            # Otherwise, a standard transfer burn between current and next.
            events.append(NavigationEvent(
                maneuver=ManeuverType.TRANSFER,
                target=nxt,
                description=f"Transfer burn from {current.name} towards {nxt.name}."
            ))
        
        # If the upcoming node is a Planet or Moon (i.e. a major body), perform circularization
        # to enter its sphere of influence.
        if next_type in ("Planet", "Moon"):
            events.append(NavigationEvent(
                maneuver=ManeuverType.CIRCULARIZE,
                target=nxt,
                description=f"Circularization maneuver upon entering {nxt.name}'s sphere of influence."
            ))
        
        # For the final leg, do a landing or docking maneuver.
        if i == len(path) - 2:
            if next_type == "Station":
                events.append(NavigationEvent(
                    maneuver=ManeuverType.DOCK,
                    target=nxt,
                    description=f"Dock at station {nxt.name}."
                ))
            elif next_type in ("Planet", "Moon"):
                events.append(NavigationEvent(
                    maneuver=ManeuverType.LANDING,
                    target=nxt,
                    description=f"Landing maneuver on {nxt.name}."
                ))
            # Additional final actions could be inserted here if needed.

    return events

"""
Encapsulates graph-based navigational logic for the universe.

This module represents the universe as a NetworkX graph built from Location objects.
It provides helper methods to:
  1. Build or rebuild the universe graph.
  2. Return the neighbors for a given node.
  3. Retrieve a "local" graph, i.e. all nodes reachable from a given location within a maximum scale.
  4. Find the nearest node from a starting location that satisfies a specified condition.

These functions will be used by the RouteServer for advanced route planning and maneuver determination.
"""



class UniverseGraph:
    _instance = None

    def __init__(self):
        self._graph = None

    @staticmethod
    def get_instance():
        if UniverseGraph._instance is None:
            UniverseGraph._instance = UniverseGraph()
        if UniverseGraph._instance._graph is None:
            UniverseGraph._instance.rebuild_graph()
        return UniverseGraph._instance

    def rebuild_graph(self):
        """
        Rebuilds the universe graph using orbital relationships.
        Each edge represents an orbital relationship between two bodies.
        Because Location uses multi‑table inheritance, we must use each object's
        concrete instance (via get_concrete_instance()) so that the 'orbits' attribute is
        available.
        
        The graph is undirected so that an edge from A to B is traversable both ways.
        """
        self._graph = nx.Graph()
        for loc in Location.objects.all():
            concrete = loc.get_concrete_instance()
            self._graph.add_node(concrete.id, location=concrete)

            if hasattr(concrete, "orbits") and concrete.orbits is not None:
                # Ensure the parent is also concrete.
                parent = concrete.orbits.get_concrete_instance()
                self._graph.add_edge(concrete.id, parent.id)

    def get_neighbors(self, location: Location) -> List[Location]:
        """
        Returns the neighboring Location objects connected to the given Location in the graph.
        """
        try:
            neighbors_ids = list(self._graph.neighbors(location.id))
            return [self._graph.nodes[nid]['location'] for nid in neighbors_ids]
        except nx.NetworkXError:
            return []

    def get_path(self, origin: Location, destination: Location) -> List[Location]:
        """
        Calculate the shortest path between two Locations in the universe graph.

        This method finds the shortest path from the origin Location to the destination Location
        using the universe graph. It returns a list of Location objects representing the path.
        
        Parameters:
        - origin (Location): The starting point of the path.
        - destination (Location): The endpoint of the path.

        Returns:
        - List[Location]: A list of Location objects representing the shortest path from origin to destination.

        Raises:
        - ValueError: If no valid path exists between the origin and destination.
        """
        if self._graph is None:
            self.rebuild_graph()
        try:
            path = []
            origin_id = origin.get_concrete_instance().id
            dest_id = destination.get_concrete_instance().id
            path_ids = nx.shortest_path(self._graph, origin_id, dest_id)
            print(f"Calculated path from {origin.name} to {destination.name}:")
            for nid in path_ids:
                path.append(Location.objects.get(id=nid).get_concrete_instance())
            for node in path:   
                print(f" - {node.name} (Scale: {node.scale})")
            print(f"Total nodes in path: {len(path)}")
            return [Location.objects.get(id=nid).get_concrete_instance() for nid in path_ids]
        except nx.NetworkXNoPath:
            raise ValueError(f"No valid route exists between {origin.name} and {destination.name}")
        
        
        
    def get_local_graph(self, relative_location: Location, max_scale: Optional[OrderedScale] = None) -> List[Location]:
        """
        Returns all Location objects reachable from 'relative_location' whose scale is less than or equal to 'max_scale'.
        If 'max_scale' is None, it defaults to the scale of 'relative_location'.
        """
        concrete = relative_location.get_concrete_instance()
        if max_scale is None:
            max_scale = concrete.scale
        elif not isinstance(max_scale, OrderedScale):
            max_scale = OrderedScale(max_scale)

        visited = set()
        queue = deque([concrete])
        local_nodes = []

        while queue:
            current = queue.popleft()
            if current.id in visited:
                continue
            visited.add(current.id)

            # Ensure we're doing the scale comparison correctly
            current_scale = OrderedScale(current.scale) if not isinstance(current.scale, OrderedScale) else current.scale
            if current_scale <= max_scale:
                local_nodes.append(current)
                for neighbor in self.get_neighbors(current):
                    if neighbor.id not in visited:
                        queue.append(neighbor)

        return local_nodes

    def find_nearest_node(self, start: Location, condition, max_scale=None):
        """
        Finds and returns the nearest Location from 'start' that satisfies the given condition.
        If 'max_scale' is provided, only nodes with scale <= max_scale are considered.
        """
        visited = set()
        queue = deque([start.get_concrete_instance()])
        while queue:
            current = queue.popleft()
            if max_scale and current.scale > max_scale:
                continue
            if condition(current):
                return current
            visited.add(current.id)
            for neighbor in self.get_neighbors(current):
                if neighbor.id not in visited:
                    queue.append(neighbor)
        return None

"""
Helper functions for graph-based navigation queries.

These functions help answer common queries such as:
    - "Where is the nearest X?" (e.g., the nearest planet, station, or other celestial object)
    - "What is the concrete type of Node Y?"
    
They are designed to be small, atomic, and easily composable with other route and scheduling functions.
"""

def get_concrete_type(node):
    """
    Return the concrete type of the given node as a string.

    Args:
        node: The node instance (e.g., a Celestial body, Ship, Station, etc.).

    Returns:
        A string representing the concrete class name of the node.
    """
    return node.__class__.__name__


def find_nearest_node(start_node, target_check, get_neighbors):
    """
    Find the nearest node from a starting node that satisfies a given condition.

    This function performs a breadth-first search (BFS) starting from `start_node`
    across the graph defined by neighbors. It returns the first node for which 
    `target_check(node)` returns True.

    Args:
        start_node: The node where the search begins.
        target_check: A callable that takes a node and returns True if it meets the desired condition.
        get_neighbors: A callable that takes a node and returns an iterable of neighboring nodes.

    Returns:
        The nearest node satisfying the condition, or None if no such node is found.
    """
    visited = set()
    queue = deque([start_node])

    while queue:
        current = queue.popleft()
        if target_check(current):
            return current
        visited.add(current)
        for neighbor in get_neighbors(current):
            if neighbor not in visited:
                queue.append(neighbor)
                visited.add(neighbor)
    return None

def _normalize(item: Any) -> Any:
    """
    Normalize a related item to a model instance.
    If the item is a tuple, assume the first element is the model.
    """
    if isinstance(item, tuple):
        return item[0]
    return item

def effective_controller(location: Location) -> Optional[Station]:
    """
    Recursively determine the controlling station for a given location.

    World-building rules:
    - If the concrete instance is a Station:
           * If its name contains "Control", then that station controls departures.
           * Otherwise, defer to its parent's controller.
    - Otherwise, if the object (say, a Planet or Moon) has orbiting stations:
           * Return the one whose name includes "Control" (if one exists),
           * Or use the first available station as fallback.
    - If there are no orbiting stations, repeat the process using the parent
        (i.e. the object that this one orbits).

    Assumes that each location's concrete type is available via get_concrete_instance().
    """
    concrete = location.get_concrete_instance()
    print(f"[effective_controller] Checking {concrete.name} (type: {concrete.get_type_name()})")

    if concrete.get_type_name() == "Station":
        if "Control" in concrete.name:
            print(f"[effective_controller] {concrete.name} is a control station.")
            return concrete
        else:
            if concrete.orbits:
                print(f"[effective_controller] {concrete.name} is a station but not a control station; deferring to parent {concrete.orbits.name}.")
                return effective_controller(concrete.orbits)
            else:
                print(f"[effective_controller] {concrete.name} is a station with no parent; using self.")
                return concrete

    if hasattr(concrete, "orbiting_stations"):
        stations = list(
            concrete.orbiting_stations.all()
            if hasattr(concrete.orbiting_stations, "all")
            else concrete.orbiting_stations
        )
        if stations:
            control_stations = [s for s in stations if "Control" in s.name]
            if control_stations:
                print(f"[effective_controller] Found control station orbiting {concrete.name}: {control_stations[0].name}")
                return control_stations[0]
            else:
                print(f"[effective_controller] No control station orbiting {concrete.name}; using first available: {stations[0].name}")
                return stations[0]

    if concrete.orbits:
        print(f"[effective_controller] No orbiting stations on {concrete.name}; checking parent {concrete.orbits.name}.")
        return effective_controller(concrete.orbits)
    
    print(f"[effective_controller] No controlling station found for {concrete.name}.")
    return None

def print_tree(universe_graph, root_id, level=0, visited=None):
    if visited is None:
        visited = set()

    # Access the internal NetworkX graph
    graph = universe_graph._graph

    # Mark the current node as visited
    visited.add(root_id)

    # Print the current node with indentation based on its level
    node_data = graph.nodes[root_id]
    location = node_data.get('location')
    if location:
        print("  " * level + f"Node {root_id}: {location.name}")
    else:
        print("  " * level + f"Node {root_id}: {'Unknown'}")

    # Recursively print all unvisited children
    for neighbor in graph.neighbors(root_id):
        if neighbor not in visited:
            print_tree(universe_graph, neighbor, level + 1, visited)