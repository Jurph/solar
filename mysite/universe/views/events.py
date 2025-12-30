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

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.cache import cache

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.services.audio_plans import build_audio_plan_for_dialogue_event

logger = logging.getLogger(__name__)


def _resolve_voice_for_event(event: DialogueEventLog) -> str:
    """
    Resolve voice_id for a dialogue event.
    
    Returns:
        Voice ID string (e.g., "pilot-M-002_canonical_all")
    """
    meta = getattr(event, "metadata", None) or {}
    
    # Check metadata first
    voice_id = meta.get("voice_id")
    if voice_id:
        return voice_id
    
    # Use actor ForeignKey to get voice from profile
    if not event.actor:
        logger.warning("Event %s missing actor reference (name='%s'), using fallback voice", 
                      event.id, event.actor_name)
        return "pilot_default"
    
    actor = event.actor
    
    # Get or create audio profile
    from mysite.universe.models.audio_profile import AudioProfile
    from mysite.universe.models.actor import Pilot, Controller, Satellite
    
    try:
        profile = actor.audio_profile
    except AudioProfile.DoesNotExist:
        # Profile missing - assign on-demand
        logger.info("Event %s actor (id=%s, name='%s') missing audio_profile, assigning on-demand", 
                   event.id, actor.id, actor.name)
        
        if isinstance(actor, Pilot):
            Pilot.assign_audio_profile(actor)
        elif isinstance(actor, Controller):
            Controller.assign_audio_profile(actor)
        elif isinstance(actor, Satellite):
            Satellite.assign_audio_profile(actor)
        else:
            profile = AudioProfile.create_default_for_actor(actor)
        
        profile = actor.audio_profile
    
    # Get voice_template from profile
    vp = profile.get_voice_params() or {}
    voice_id = vp.get("voice_template")
    
    if not voice_id:
        logger.warning("Event %s actor (id=%s, name='%s') has no voice_template, using fallback", 
                      event.id, actor.id, actor.name)
        return "pilot_default"
    
    return voice_id


def _sentence_case(text: str) -> str:
    """Convert text to sentence case (lowercase with first letter capitalized)."""
    if not text:
        return text
    t = text.strip()
    if not t:
        return text
    if t.isupper():
        t = t.lower()
    for i, ch in enumerate(t):
        if ch.isalpha():
            return t[:i] + ch.upper() + t[i + 1:]
    return t


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
            # Audio is generated on-demand when requested, not prefetched
            'audio_ready': True,  # Always true - we generate synchronously if not cached
            'audio_duration_s': None,  # Client can determine from WAV headers
            'audio_url': f"/api/event_audio/{event.id}/",
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


@require_http_methods(["GET"])
def event_audio(request, event_id: int):
    """
    Serve audio WAV for an event, generating on-demand if not cached.
    
    Simple architecture:
    - Check Django cache for generated audio
    - If miss, generate synchronously using TTS service
    - Cache result for future requests
    - Serve WAV bytes
    
    Returns:
        200 with WAV bytes if audio generated successfully
        404 if event not found
        500 if TTS generation fails
    """
    from mysite.universe.services.tts_service import get_tts_service
    
    # Get event
    try:
        event = DialogueEventLog.objects.get(id=event_id)
    except DialogueEventLog.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": f"Event {event_id} not found",
        }, status=404)
    
    # Check cache first
    cache_key = f"tts_audio:{event_id}"
    wav_bytes = cache.get(cache_key)
    
    if wav_bytes:
        logger.debug("TTS cache hit for event %s", event_id)
        resp = HttpResponse(wav_bytes, content_type="audio/wav")
        resp["Cache-Control"] = "public, max-age=3600"
        return resp
    
    # Cache miss - generate synchronously
    logger.info("TTS cache miss for event %s, generating...", event_id)
    
    # Get text and voice
    text = event.text
    if not text or not text.strip():
        return JsonResponse({
            "status": "error",
            "message": f"Event {event_id} has no text",
        }, status=400)
    
    voice_id = _resolve_voice_for_event(event)
    
    # Sentence-case to avoid spelled-out ALL CAPS
    speak_text = _sentence_case(text)
    
    # Generate TTS
    try:
        tts_service = get_tts_service()
        wav_bytes = tts_service.generate(text=speak_text, voice_id=voice_id)
        
        if not wav_bytes or len(wav_bytes) == 0:
            raise ValueError("TTS service returned empty audio")
        
        # Cache for 1 hour
        cache.set(cache_key, wav_bytes, timeout=3600)
        
        logger.info("TTS generated for event %s: voice=%s, bytes=%d", 
                   event_id, voice_id, len(wav_bytes))
        
        resp = HttpResponse(wav_bytes, content_type="audio/wav")
        resp["Cache-Control"] = "public, max-age=3600"
        return resp
        
    except Exception as e:
        logger.error("TTS generation failed for event %s: %s", event_id, e, exc_info=True)
        return JsonResponse({
            "status": "error",
            "message": f"TTS generation failed: {str(e)}",
        }, status=500)
