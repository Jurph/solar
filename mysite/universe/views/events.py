"""
Views for the dialogue event feed and display.

Contains:
- event_feed: JSON API for polling dialogue events
- event_scroller: Scrolling terminal display (iframe content)
- event_scroller_wrapper: Main page with control panel
- clear_events: Clear all events from the database

The event system handles:
- Real-time polling of events based on simulation time
- Events only appear when simulation time reaches their timestamp
- Debug information for monitoring event queue status
"""
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.services.audio_plans import build_audio_plan_for_dialogue_event

logger = logging.getLogger(__name__)


def event_feed(request):
    """
    API endpoint that returns dialogue events as JSON for real-time display.
    
    Only returns events whose timestamp <= current simulation time.
    This allows events to be scheduled for the future and appear when
    simulation time reaches them.
    
    Query parameters:
        after_id: (optional int) Return events with id > after_id
        limit: (optional int, default=100) Maximum events to return
    
    Returns:
        JSON response with events array, latest_id, simulation_time, and debug info
    """
    from mysite.universe.models.simulation import get_simulation_time
    
    # Get current simulation time
    sim_time = get_simulation_time()
    
    # Get query parameters
    after_id = request.GET.get('after_id')
    after_ts = request.GET.get('after_ts')
    limit = int(request.GET.get('limit', 100))
    
    # Build query - only events whose time has arrived
    queryset = DialogueEventLog.objects.filter(timestamp__lte=sim_time)
    
    # Cursor filtering (single supported mode): (timestamp, id)
    #
    # Why timestamp cursor?
    # Events can be inserted out of timestamp order (e.g., background mission generation),
    # so relying on monotonic id can permanently skip events with lower ids but later timestamps.
    after_ts_f: float | None
    after_id_int = 0

    if after_ts is None:
        if after_id:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "after_id requires after_ts (cursor is timestamp-based).",
                },
                status=400,
            )
        after_ts_f = None
    else:
        try:
            after_ts_f = float(after_ts)
        except ValueError:
            return JsonResponse(
                {"status": "error", "message": "Invalid after_ts; must be a float."},
                status=400,
            )

        if after_id:
            try:
                after_id_int = int(after_id)
            except ValueError:
                return JsonResponse(
                    {"status": "error", "message": "Invalid after_id; must be an int."},
                    status=400,
                )

        queryset = queryset.filter(
            Q(timestamp__gt=after_ts_f)
            | (Q(timestamp=after_ts_f) & Q(id__gt=after_id_int))
        )

    queryset = queryset.order_by("timestamp", "id")[:limit]
    
    # Debug: Log what we're querying
    count_before_limit = DialogueEventLog.objects.filter(timestamp__lte=sim_time).count()
    count_with_id_filter = count_before_limit
    
    if count_with_id_filter > 0:
        logger.debug(
            f"event_feed: sim_time={sim_time:.1f}, after_id={after_id}, "
            f"due_events={count_before_limit}, filtered={count_with_id_filter}"
        )
    
    # Convert to list of dicts with only essential fields
    events = [
        {
            'id': event.id,
            'timestamp': event.timestamp,
            'actor_name': event.actor_name,
            'text': event.text,
            'metadata': event.metadata if event.metadata is not None else {},
            # Python-defined audio plan (client just queues & plays waveforms)
            'audio_plan': build_audio_plan_for_dialogue_event(event),
        }
        for event in queryset
    ]
    
    # Get latest ID for client to track progress
    latest_id = events[-1]['id'] if events else None
    latest_cursor = (
        {"timestamp": events[-1]["timestamp"], "id": events[-1]["id"]} if events else None
    )
    
    # Debug: count how many events are pending (future) vs available (past)
    total_events = DialogueEventLog.objects.count()
    available_events = DialogueEventLog.objects.filter(timestamp__lte=sim_time).count()
    pending_events = total_events - available_events
    
    # Find the next pending event (first event with timestamp > sim_time)
    next_event = DialogueEventLog.objects.filter(
        timestamp__gt=sim_time
    ).order_by('timestamp').first()
    next_event_timestamp = next_event.timestamp if next_event else None
    time_until_next = (next_event_timestamp - sim_time) if next_event_timestamp else None
    
    return JsonResponse({
        'events': events,
        'debug': {
            'sim_time': sim_time,
            'total_events': total_events,
            'available_events': available_events,
            'pending_events': pending_events,
            'after_id': after_id,
            'after_ts': after_ts,
            'cursor_mode': 'timestamp',
            'returned_count': len(events),
            'next_event_timestamp': next_event_timestamp,
            'time_until_next': time_until_next,
        },
        'latest_id': latest_id,
        'latest_cursor': latest_cursor,
        'simulation_time': sim_time,
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
def clear_events(request):
    """
    API endpoint to clear all dialogue events from the database.
    
    Useful for starting fresh without restarting the server.
    Resets the event queue to empty state.
    
    Returns:
        JSON with status and count of cleared events
    """
    try:
        count, _ = DialogueEventLog.objects.all().delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Cleared {count} dialogue events from the database.'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to clear events: {str(e)}'
        }, status=500)
