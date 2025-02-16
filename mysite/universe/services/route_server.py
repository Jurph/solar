from typing import List
from mysite.universe.models.navigation import ManeuverType, NavigationStep
from mysite.universe.models.base import Location

class RouteService:
    """Service for generating navigation plans between locations"""
    
    @staticmethod
    def plan_route(origin: Location, destination: Location) -> List[NavigationStep]:
        """Generate a complete navigation plan between two points"""
        steps = []
        spatial_route = RouteService._get_spatial_route(origin, destination)
        
        # Generate steps based on location rules
        if origin.requires_launch_clearance():
            control = origin.get_control_station()
            steps.append(NavigationStep(
                contact_station=control,
                maneuver=ManeuverType.LAUNCH,
                target=origin.orbits
            ))
        
        # Generate transfer steps
        for i in range(len(spatial_route) - 1):
            current = spatial_route[i]
            next_loc = spatial_route[i + 1]
            control = current.get_control_station()
            
            steps.append(NavigationStep(
                contact_station=control,
                maneuver=ManeuverType.CIRCULARIZE,
                target=current
            ))
            steps.append(NavigationStep(
                contact_station=control,
                maneuver=ManeuverType.TRANSFER,
                target=next_loc
            ))
        
        # Add arrival steps based on destination rules
        if destination.requires_docking_clearance():
            control = destination.get_control_station()
            steps.append(NavigationStep(
                contact_station=control,
                maneuver=ManeuverType.DOCK,
                target=destination
            ))
            
        return steps

    @staticmethod
    def _get_spatial_route(origin: Location, destination: Location) -> List[Location]:
        """Find the physical route through space between two points"""
        # Build route by traversing up to common ancestor and back down
        origin_path = []
        dest_path = []
        
        # Traverse up from origin until we hit a common parent
        current = origin
        while current:
            origin_path.append(current)
            current = current.orbits
            
        # Traverse up from destination
        current = destination  
        while current:
            dest_path.append(current)
            current = current.orbits
            
        # Find first common ancestor
        common_ancestor = None
        for loc in origin_path:
            if loc in dest_path:
                common_ancestor = loc
                break
                
        if not common_ancestor:
            raise ValueError("No valid route exists between these locations")
            
        # Build final route
        route = []
        
        # Add origin path up to common ancestor
        for loc in origin_path:
            if loc == common_ancestor:
                break
            route.append(loc)
            
        # Add destination path in reverse from common ancestor
        dest_index = dest_path.index(common_ancestor)
        for loc in reversed(dest_path[:dest_index]):
            route.append(loc)
            
        return route