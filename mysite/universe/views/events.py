from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.core.management import call_command
from django.views.decorators.http import require_http_methods
import threading
from mysite.universe.models import (
    Galaxy, StarSystem, Star, Planet, Moon, Station
)
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models import display


def universe_view(request):
    galaxies = Galaxy.objects.all()
    
    # Debug output
    print(f"Found {galaxies.count()} galaxies")
    for galaxy in galaxies:
        print(f"Galaxy: {galaxy.name}")
    
    return render(request, 'universe/index.html', {'galaxies': galaxies})


def event_feed(request):
    """
    API endpoint that returns dialogue events as JSON for real-time display.
    
    Query parameters:
        after_id: (optional int) Return events with id > after_id
        limit: (optional int, default=100) Maximum events to return
    
    Returns:
        JSON response with events array and latest_id
    """
    # Get query parameters
    after_id = request.GET.get('after_id')
    limit = int(request.GET.get('limit', 100))
    
    # Build query
    queryset = DialogueEventLog.objects.all()
    
    # Filter by ID if 'after_id' parameter provided
    if after_id:
        try:
            after_id_int = int(after_id)
            queryset = queryset.filter(id__gt=after_id_int)
        except ValueError:
            # Invalid after_id parameter, ignore it
            pass
    
    # Order by id (which also orders by insertion time) and limit results
    queryset = queryset.order_by('id')[:limit]
    
    # Convert to list of dicts with only essential fields
    events = [
        {
            'id': event.id,
            'timestamp': event.timestamp,
            'actor_name': event.actor_name,
            'text': event.text
        }
        for event in queryset
    ]
    
    # Get latest ID for client to track progress
    latest_id = events[-1]['id'] if events else None
    
    return JsonResponse({
        'events': events,
        'latest_id': latest_id
    })


@xframe_options_sameorigin
def event_scroller(request):
    """
    Renders the simulation event log page with scrolling dialogue display.
    This is the iframe content.
    """
    return render(request, "universe/event_scroller.html")


def event_scroller_wrapper(request):
    """
    Renders the wrapper page with control panel and iframe containing the scroller.
    """
    return render(request, "universe/event_scroller_wrapper.html")


@csrf_exempt
@require_http_methods(["POST"])
def run_demo(request):
    """
    API endpoint to run the character dialogue demo in the background.
    """
    def run_demo_command():
        """Run the demo command in a background thread."""
        try:
            # Run the management command with default temperature
            call_command('character_dialogue_demo', temperature=0.7, use_json=True)
        except Exception as e:
            print(f"Error running demo: {e}")
    
    # Start the demo in a background thread
    thread = threading.Thread(target=run_demo_command, daemon=True)
    thread.start()
    
    return JsonResponse({'status': 'started', 'message': 'Demo started in background'})


def object_details(request, object_type, object_id):
    """
    API endpoint to get details for a celestial object or station.
    
    Returns a JSON object with relevant properties for display in the baseball card.
    """
    print(f"[object_details] Called with type={object_type}, id={object_id}")
    import sys
    sys.stdout.flush()
    
    try:
        # Map object types to models
        model_map = {
            'galaxy': Galaxy,
            'system': StarSystem,
            'star': Star,
            'planet': Planet,
            'moon': Moon,
            'station': Station,
        }
        
        if object_type not in model_map:
            return JsonResponse({'error': 'Invalid object type'}, status=400)
        
        model = model_map[object_type]
        obj = get_object_or_404(model, pk=object_id)
        
        # Get concrete instance to access all properties
        concrete = obj.get_concrete_instance() if hasattr(obj, 'get_concrete_instance') else obj
        
        # Build response with common properties
        # Expand type name to full descriptive text
        type_name_map = {
            'Planet': 'Planet',
            'Moon': 'Moon',
            'Star': 'Star',
            'Station': 'Space Station',
            'StarSystem': 'Star System',
            'Galaxy': 'Galaxy',
        }
        type_name = obj.get_type_name() if hasattr(obj, 'get_type_name') else object_type.title()
        type_display = type_name_map.get(type_name, type_name)
        
        details = {
            'name': obj.name,
            'type': type_display,
            'type_code': type_name,  # Keep original for reference
            'scale': obj.scale if hasattr(obj, 'scale') else None,
        }
        
        # Add type-specific properties
        if isinstance(concrete, Star):
            details.update({
                'star_type': concrete.star_type if hasattr(concrete, 'star_type') else None,
                'star_magnitude': float(concrete.star_magnitude) if hasattr(concrete, 'star_magnitude') and concrete.star_magnitude else None,
                'temperature_k': concrete.temperature_k if hasattr(concrete, 'temperature_k') else None,
                'mass_kg': concrete.mass_kg if hasattr(concrete, 'mass_kg') else None,
                'mass_solar': concrete.mass_solar if hasattr(concrete, 'mass_solar') else None,
                'radius_km': concrete.radius_km if hasattr(concrete, 'radius_km') else None,
                'radius_solar': concrete.radius_solar if hasattr(concrete, 'radius_solar') else None,
            })
        elif isinstance(concrete, Planet):
            planet_type_display = None
            if hasattr(concrete, 'planet_type'):
                if hasattr(concrete, 'get_planet_type_display'):
                    try:
                        planet_type_display = concrete.get_planet_type_display()
                    except (AttributeError, ValueError):
                        planet_type_display = concrete.planet_type
                else:
                    planet_type_display = concrete.planet_type
            # Get parent body (star that planet orbits)
            parent_body_name = None
            parent_body_type = None
            try:
                if hasattr(concrete, 'orbits'):
                    parent_star = concrete.orbits
                    parent_body_name = parent_star.name
                    if hasattr(parent_star, 'star_type'):
                        parent_body_type = parent_star.get_star_type_display() if hasattr(parent_star, 'get_star_type_display') else parent_star.star_type
            except Exception as e:
                print(f"[object_details] Error getting parent body for planet: {e}")
            
            # Check for atmosphere relationship using ContentType
            has_atmosphere = False
            atmosphere_type = None
            atmosphere_height_km = None
            surface_pressure_bar = None
            scale_height_km = None
            try:
                from django.contrib.contenttypes.models import ContentType
                from mysite.universe.models import Atmosphere
                content_type = ContentType.objects.get_for_model(Planet)
                try:
                    atmosphere = Atmosphere.objects.get(content_type=content_type, object_id=concrete.id)
                    has_atmosphere = True
                    atmosphere_type = atmosphere.atmosphere_type
                    atmosphere_height_km = atmosphere.atmosphere_height_km
                    surface_pressure_bar = atmosphere.surface_pressure_bar
                    scale_height_km = atmosphere.scale_height_km
                except Atmosphere.DoesNotExist:
                    pass
            except Exception as e:
                # Atmosphere model might not exist yet or other error
                print(f"[object_details] Error checking atmosphere for planet: {e}")
                pass
            
            # Calculate surface gravity if we have mass and radius
            surface_gravity_ms2 = None
            if hasattr(concrete, 'mass_kg') and hasattr(concrete, 'radius_km'):
                mass_kg = getattr(concrete, 'mass_kg', None)
                radius_km = getattr(concrete, 'radius_km', None)
                if mass_kg and radius_km:
                    # g = GM/r², where G = 6.67430e-11 m³/(kg·s²)
                    G = 6.67430e-11
                    radius_m = radius_km * 1000
                    surface_gravity_ms2 = (G * mass_kg) / (radius_m ** 2)
            
            # Get raw values
            mass_kg = getattr(concrete, 'mass_kg', None)
            radius_km = getattr(concrete, 'radius_km', None)
            density_kg_m3 = getattr(concrete, 'density_kg_m3', None)
            albedo = getattr(concrete, 'albedo', None)
            equilibrium_temperature_k = getattr(concrete, 'equilibrium_temperature_k', None)
            orbital_period_days = getattr(concrete, 'orbital_period_days', None)
            orbital_eccentricity = getattr(concrete, 'orbital_eccentricity', None)
            orbital_inclination_deg = getattr(concrete, 'orbital_inclination_deg', None)
            rotation_period_hours = getattr(concrete, 'rotation_period_hours', None)
            axial_tilt_deg = getattr(concrete, 'axial_tilt_deg', None)
            is_tidally_locked = getattr(concrete, 'is_tidally_locked', None)
            
            # Calculate escape velocity and orbital velocity
            escape_velocity_ms = display.calculate_escape_velocity_ms(mass_kg, radius_km)
            orbital_velocity_ms = display.calculate_orbital_velocity_ms(mass_kg, radius_km)
            
            # Get surface composition hint
            surface_composition = display.get_surface_composition_hint(
                planet_type=concrete.planet_type if hasattr(concrete, 'planet_type') else None,
                density_kg_m3=density_kg_m3
            )
            
            details.update({
                'planet_type': planet_type_display,
                'parent_body_name': parent_body_name,
                'parent_body_type': parent_body_type,
                'orbital_distance_au': concrete.orbital_distance_au if hasattr(concrete, 'orbital_distance_au') else None,
                'mass_kg': mass_kg,
                'mass_formatted': display.format_number(mass_kg),
                'radius_km': radius_km,
                'radius_formatted': display.format_distance_km(radius_km),
                'density_kg_m3': density_kg_m3,
                'density_formatted': f"{density_kg_m3:.0f} kg/m³" if density_kg_m3 else None,
                'surface_gravity_ms2': surface_gravity_ms2,
                'surface_gravity_formatted': display.format_surface_gravity(surface_gravity_ms2),
                'surface_composition': surface_composition,
                'escape_velocity_ms': escape_velocity_ms,
                'escape_velocity_formatted': display.format_escape_velocity(escape_velocity_ms),
                'orbital_velocity_ms': orbital_velocity_ms,
                'orbital_velocity_formatted': display.format_orbital_velocity(orbital_velocity_ms),
                'albedo': albedo,
                'albedo_formatted': f"{albedo:.3f}" if albedo else None,
                'equilibrium_temperature_k': equilibrium_temperature_k,
                'equilibrium_temperature_formatted': display.format_temperature_k(equilibrium_temperature_k),
                'orbital_period_days': orbital_period_days,
                'orbital_period_formatted': display.format_orbital_period_days(orbital_period_days),
                'orbital_eccentricity': orbital_eccentricity,
                'orbital_eccentricity_formatted': f"{orbital_eccentricity:.3f}" if orbital_eccentricity else None,
                'orbital_inclination_deg': orbital_inclination_deg,
                'orbital_inclination_formatted': f"{orbital_inclination_deg:.2f}°" if orbital_inclination_deg else None,
                'rotation_period_hours': rotation_period_hours,
                'rotation_period_formatted': display.format_rotation_period_hours(rotation_period_hours),
                'axial_tilt_deg': axial_tilt_deg,
                'axial_tilt_formatted': f"{axial_tilt_deg:.2f}°" if axial_tilt_deg else None,
                'is_tidally_locked': is_tidally_locked,
                'has_atmosphere': has_atmosphere,
                'atmosphere_type': atmosphere_type,
                'atmosphere_height_km': atmosphere_height_km,
                'atmosphere_height_formatted': display.format_atmosphere_height(atmosphere_height_km),
                'scale_height_km': scale_height_km,
                'scale_height_formatted': display.format_atmosphere_height(scale_height_km),
                'surface_pressure_bar': surface_pressure_bar,
                'surface_pressure_formatted': f"{surface_pressure_bar:.3f} bar" if surface_pressure_bar else None,
            })
        elif isinstance(concrete, Moon):
            moon_type_display = None
            if hasattr(concrete, 'moon_type'):
                if hasattr(concrete, 'get_moon_type_display'):
                    try:
                        moon_type_display = concrete.get_moon_type_display()
                    except (AttributeError, ValueError):
                        moon_type_display = concrete.moon_type
                else:
                    moon_type_display = concrete.moon_type
            
            # Get parent body (planet that moon orbits)
            parent_body_name = None
            parent_body_type = None
            try:
                if hasattr(concrete, 'orbits'):
                    parent_location = concrete.orbits
                    parent_body_name = parent_location.name
                    # Get type name for parent (could be Planet or Star)
                    if hasattr(parent_location, 'get_type_name'):
                        parent_type_name = parent_location.get_type_name()
                        if parent_type_name == 'Planet':
                            if hasattr(parent_location, 'planet_type'):
                                parent_body_type = parent_location.get_planet_type_display() if hasattr(parent_location, 'get_planet_type_display') else parent_location.planet_type
                        elif parent_type_name == 'Star':
                            if hasattr(parent_location, 'star_type'):
                                parent_body_type = parent_location.get_star_type_display() if hasattr(parent_location, 'get_star_type_display') else parent_location.star_type
                    else:
                        parent_body_type = parent_location.get_type_name() if hasattr(parent_location, 'get_type_name') else 'Unknown'
            except Exception as e:
                print(f"[object_details] Error getting parent body for moon: {e}")
            
            # Check for atmosphere relationship using ContentType
            has_atmosphere = False
            atmosphere_type = None
            atmosphere_height_km = None
            surface_pressure_bar = None
            scale_height_km = None
            try:
                from django.contrib.contenttypes.models import ContentType
                from mysite.universe.models import Atmosphere
                content_type = ContentType.objects.get_for_model(Moon)
                try:
                    atmosphere = Atmosphere.objects.get(content_type=content_type, object_id=concrete.id)
                    has_atmosphere = True
                    atmosphere_type = atmosphere.atmosphere_type
                    atmosphere_height_km = atmosphere.atmosphere_height_km
                    surface_pressure_bar = atmosphere.surface_pressure_bar
                    scale_height_km = atmosphere.scale_height_km
                except Atmosphere.DoesNotExist:
                    pass
            except Exception as e:
                # Atmosphere model might not exist yet or other error
                print(f"[object_details] Error checking atmosphere for moon: {e}")
                pass
            
            # Calculate surface gravity if we have mass and radius
            surface_gravity_ms2 = None
            if hasattr(concrete, 'mass_kg') and hasattr(concrete, 'radius_km'):
                mass_kg = getattr(concrete, 'mass_kg', None)
                radius_km = getattr(concrete, 'radius_km', None)
                if mass_kg and radius_km:
                    # g = GM/r²
                    G = 6.67430e-11
                    radius_m = radius_km * 1000
                    surface_gravity_ms2 = (G * mass_kg) / (radius_m ** 2)
            
            # Get raw values
            mass_kg = getattr(concrete, 'mass_kg', None)
            radius_km = getattr(concrete, 'radius_km', None)
            density_kg_m3 = getattr(concrete, 'density_kg_m3', None)
            albedo = getattr(concrete, 'albedo', None)
            equilibrium_temperature_k = getattr(concrete, 'equilibrium_temperature_k', None)
            orbital_distance_km = getattr(concrete, 'orbital_distance_km', None)
            orbital_period_hours = getattr(concrete, 'orbital_period_hours', None)
            orbital_eccentricity = getattr(concrete, 'orbital_eccentricity', None)
            orbital_inclination_deg = getattr(concrete, 'orbital_inclination_deg', None)
            rotation_period_hours = getattr(concrete, 'rotation_period_hours', None)
            axial_tilt_deg = getattr(concrete, 'axial_tilt_deg', None)
            is_tidally_locked = getattr(concrete, 'is_tidally_locked', None)
            
            # Calculate escape velocity and orbital velocity
            escape_velocity_ms = display.calculate_escape_velocity_ms(mass_kg, radius_km)
            orbital_velocity_ms = display.calculate_orbital_velocity_ms(mass_kg, radius_km)
            
            # Get surface composition hint
            surface_composition = display.get_surface_composition_hint(
                moon_type=concrete.moon_type if hasattr(concrete, 'moon_type') else None,
                density_kg_m3=density_kg_m3
            )
            
            details.update({
                'moon_type': moon_type_display,
                'parent_body_name': parent_body_name,
                'parent_body_type': parent_body_type,
                'mass_kg': mass_kg,
                'mass_formatted': display.format_number(mass_kg),
                'radius_km': radius_km,
                'radius_formatted': display.format_distance_km(radius_km),
                'density_kg_m3': density_kg_m3,
                'density_formatted': f"{density_kg_m3:.0f} kg/m³" if density_kg_m3 else None,
                'surface_gravity_ms2': surface_gravity_ms2,
                'surface_gravity_formatted': display.format_surface_gravity(surface_gravity_ms2),
                'surface_composition': surface_composition,
                'escape_velocity_ms': escape_velocity_ms,
                'escape_velocity_formatted': display.format_escape_velocity(escape_velocity_ms),
                'orbital_velocity_ms': orbital_velocity_ms,
                'orbital_velocity_formatted': display.format_orbital_velocity(orbital_velocity_ms),
                'albedo': albedo,
                'albedo_formatted': f"{albedo:.3f}" if albedo else None,
                'equilibrium_temperature_k': equilibrium_temperature_k,
                'equilibrium_temperature_formatted': display.format_temperature_k(equilibrium_temperature_k),
                'orbital_distance_km': orbital_distance_km,
                'orbital_distance_formatted': display.format_distance_km(orbital_distance_km),
                'orbital_period_hours': orbital_period_hours,
                'orbital_period_formatted': display.format_orbital_period_hours(orbital_period_hours),
                'orbital_eccentricity': orbital_eccentricity,
                'orbital_eccentricity_formatted': f"{orbital_eccentricity:.3f}" if orbital_eccentricity else None,
                'orbital_inclination_deg': orbital_inclination_deg,
                'orbital_inclination_formatted': f"{orbital_inclination_deg:.2f}°" if orbital_inclination_deg else None,
                'rotation_period_hours': rotation_period_hours,
                'rotation_period_formatted': f"{rotation_period_hours:.2f} hours" if rotation_period_hours else None,
                'axial_tilt_deg': axial_tilt_deg,
                'axial_tilt_formatted': f"{axial_tilt_deg:.2f}°" if axial_tilt_deg else None,
                'is_tidally_locked': is_tidally_locked,
                'has_atmosphere': has_atmosphere,
                'atmosphere_type': atmosphere_type,
                'atmosphere_height_km': atmosphere_height_km,
                'atmosphere_height_formatted': display.format_atmosphere_height(atmosphere_height_km),
                'scale_height_km': scale_height_km,
                'scale_height_formatted': display.format_atmosphere_height(scale_height_km),
                'surface_pressure_bar': surface_pressure_bar,
                'surface_pressure_formatted': f"{surface_pressure_bar:.3f} bar" if surface_pressure_bar else None,
            })
        elif isinstance(concrete, Station):
            details.update({
                'large_berths': concrete.large_berths if hasattr(concrete, 'large_berths') else None,
                'medium_berths': concrete.medium_berths if hasattr(concrete, 'medium_berths') else None,
                'small_berths': concrete.small_berths if hasattr(concrete, 'small_berths') else None,
            })
        elif isinstance(concrete, Galaxy):
            galaxy_type_display = None
            galaxy_size_display = None
            if hasattr(concrete, 'galaxy_type'):
                if hasattr(concrete, 'get_galaxy_type_display'):
                    try:
                        galaxy_type_display = concrete.get_galaxy_type_display()
                    except (AttributeError, ValueError):
                        galaxy_type_display = concrete.galaxy_type
                else:
                    galaxy_type_display = concrete.galaxy_type
            if hasattr(concrete, 'galaxy_size'):
                if hasattr(concrete, 'get_galaxy_size_display'):
                    try:
                        galaxy_size_display = concrete.get_galaxy_size_display()
                    except (AttributeError, ValueError):
                        galaxy_size_display = concrete.galaxy_size
                else:
                    galaxy_size_display = concrete.galaxy_size
            details.update({
                'galaxy_type': galaxy_type_display,
                'galaxy_size': galaxy_size_display,
            })
        elif isinstance(concrete, StarSystem):
            details.update({
                'system_age_years': concrete.system_age_years if hasattr(concrete, 'system_age_years') else None,
            })
        
        print(f"[object_details] Successfully returning details for {object_type} {object_id}")
        print(f"[object_details] Details keys: {list(details.keys())}")
        import sys
        sys.stdout.flush()
        return JsonResponse(details)
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[object_details] ERROR: {str(e)}")
        print(f"[object_details] Traceback:\n{error_traceback}")
        import sys
        sys.stdout.flush()
        error_details = {
            'error': str(e),
            'traceback': error_traceback
        }
        return JsonResponse(error_details, status=500) 