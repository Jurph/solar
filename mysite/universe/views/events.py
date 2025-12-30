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
import os

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.services.audio_plans import build_audio_plan_for_dialogue_event
from mysite.universe.services.audio_cache import AudioCache, AudioJob, AudioJobQueue, AudioWorker

logger = logging.getLogger(__name__)

# Prefetch/config knobs
_AUDIO_CACHE_CAPACITY = int(os.getenv("AUDIO_CACHE_CAPACITY", "24"))  # bump above 12 to allow horizon buffering
_AUDIO_PREFETCH_HORIZON_SECONDS = float(os.getenv("AUDIO_PREFETCH_HORIZON_SECONDS", "1800"))  # 30 minutes
_AUDIO_PREFETCH_MAX_EVENTS = int(os.getenv("AUDIO_PREFETCH_MAX_EVENTS", "200"))

# Lightweight in-memory audio cache/queue/worker (no disk writes)
_audio_cache: AudioCache | None = None
_audio_queue: AudioJobQueue | None = None
_audio_worker: AudioWorker | None = None


def _get_audio_cache() -> AudioCache:
    global _audio_cache
    if _audio_cache is None:
        _audio_cache = AudioCache(capacity=_AUDIO_CACHE_CAPACITY)
    return _audio_cache


def _get_audio_queue() -> AudioJobQueue:
    global _audio_queue
    if _audio_queue is None:
        _audio_queue = AudioJobQueue(capacity=50)
    return _audio_queue


def _ensure_worker():
    global _audio_worker
    if _audio_worker is None:
        _audio_worker = AudioWorker(cache=_get_audio_cache(), queue=_get_audio_queue())
        _audio_worker.start()


def _prefetch_audio_for_events(events):
    """
    Best-effort prefetch: enqueue events for which audio is not cached.
    """
    _ensure_worker()
    cache = _get_audio_cache()
    queue = _get_audio_queue()

    from mysite.universe.models.actor import Pilot, Controller, Satellite, Actor as BaseActor
    import logging
    log = logging.getLogger(__name__)

    for ev in events:
        if cache.get(ev.id):
            continue
        text = getattr(ev, "text", "") or ""
        if not text.strip():
            continue
        meta = getattr(ev, "metadata", None) or {}

        # Resolve voice from metadata or actor profile
        voice_id = meta.get("voice_id")
        if not voice_id:
            actor = (
                Pilot.objects.filter(name=ev.actor_name).order_by("-id").first()
                or Controller.objects.filter(name=ev.actor_name).order_by("-id").first()
                or Satellite.objects.filter(name=ev.actor_name).order_by("-id").first()
                or BaseActor.objects.filter(name=ev.actor_name).order_by("-id").first()
            )
            if actor:
                try:
                    profile = actor.audio_profile
                    vp = profile.get_voice_params() or {}
                    voice_id = vp.get("voice_template")
                except BaseActor.audio_profile.RelatedObjectDoesNotExist:
                    # Actor has no profile - use fallback
                    voice_id = None
        if not voice_id:
            # Fallback defaults
            voice_id = "pilot_default"

        # Sentence-case the text to avoid spelled-out ALL CAPS
        speak_text = _sentence_case(text)
        queue.enqueue(AudioJob(event_id=ev.id, text=speak_text, voice_id=voice_id))
        log.info("Prefetch enqueue event_id=%s voice=%s", ev.id, voice_id)


def _select_upcoming_events(sim_time, limit: int = 12):
    """
    Fetch upcoming events after sim_time within a horizon, ordered by timestamp/id.
    """
    horizon = sim_time + _AUDIO_PREFETCH_HORIZON_SECONDS
    qs = DialogueEventLog.objects.filter(timestamp__gt=sim_time, timestamp__lte=horizon).order_by("timestamp", "id")
    return qs[:min(limit, _AUDIO_PREFETCH_MAX_EVENTS)]


def _sentence_case(text: str) -> str:
    if not text:
        return text
    t = text.strip()
    if not t:
        return text
    if t.isupper():
        t = t.lower()
    for i, ch in enumerate(t):
        if ch.isalpha():
            return t[:i] + ch.upper() + t[i + 1 :]
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
    
    # Prefetch audio for returned events and additional upcoming events (best-effort)
    _prefetch_audio_for_events(list(queryset))
    remaining = max(0, _AUDIO_CACHE_CAPACITY - len(queryset))
    if remaining > 0:
        upcoming = _select_upcoming_events(sim_time=sim_time, limit=remaining)
        _prefetch_audio_for_events(list(upcoming))

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
            'audio_ready': bool(_get_audio_cache().get(event.id)),
            'audio_duration_s': (_get_audio_cache().get(event.id).duration_s if _get_audio_cache().get(event.id) else None),
            'audio_url': (f"/api/event_audio/{event.id}/" if _get_audio_cache().get(event.id) else None),
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
    entry = _get_audio_cache().get(int(event_id))
    if not entry:
        return JsonResponse({"status": "error", "message": "Audio not ready"}, status=404)
    resp = HttpResponse(entry.wav_bytes, content_type="audio/wav")
    resp["Cache-Control"] = "no-store"
    return resp


@require_http_methods(["POST"])
def ensure_audio_worker(request):
    """
    Ensure the audio worker is running; best-effort to start it if not.
    """
    try:
        _ensure_worker()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
