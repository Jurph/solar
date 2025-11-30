from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.core.management import call_command
from django.views.decorators.http import require_http_methods
import threading
from mysite.universe.models import Galaxy
from mysite.universe.models.event import DialogueEventLog


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