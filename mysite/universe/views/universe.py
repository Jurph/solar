"""
Views for the universe browser and celestial object details.

Contains:
- universe_view: Hierarchical universe browser
- object_details: Baseball card API endpoint for celestial objects
"""
import logging

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404

from mysite.universe.models import (
    Galaxy, StarSystem, Star, Planet, Moon, Station
)
from mysite.universe.views.serializers import get_serializer_for_instance

logger = logging.getLogger(__name__)


# Map URL object_type strings to model classes
MODEL_MAP = {
    'galaxy': Galaxy,
    'system': StarSystem,
    'star': Star,
    'planet': Planet,
    'moon': Moon,
    'station': Station,
}


def universe_view(request):
    """
    Render the universe browser page with hierarchical tree view.
    
    Displays all galaxies as the root level, with expandable nodes
    for star systems, stars, planets, moons, and stations.
    """
    galaxies = Galaxy.objects.all()
    return render(request, 'universe/index.html', {'galaxies': galaxies})


def object_details(request, object_type, object_id):
    """
    API endpoint to get details for a celestial object or station.
    
    Returns a JSON object with relevant properties for display in the baseball card.
    Uses type-specific serializers to format the response.
    
    Args:
        request: HTTP request
        object_type: String type identifier ('galaxy', 'system', 'star', 'planet', 'moon', 'station')
        object_id: Integer primary key of the object
    
    Returns:
        JsonResponse with serialized object details, or error response
    """
    logger.debug(f"object_details: type={object_type}, id={object_id}")
    
    try:
        if object_type not in MODEL_MAP:
            return JsonResponse({'error': 'Invalid object type'}, status=400)
        
        model = MODEL_MAP[object_type]
        obj = get_object_or_404(model, pk=object_id)
        
        # Use the serializer to build the response
        serializer = get_serializer_for_instance(obj)
        details = serializer.serialize()
        
        return JsonResponse(details)
    
    except Exception as e:
        logger.exception(f"object_details: Error for {object_type}/{object_id}")
        return JsonResponse({'error': str(e)}, status=500)

