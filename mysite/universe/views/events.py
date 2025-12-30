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
from mysite.universe.services.audio_cache import AudioCache, AudioJob, AudioJobQueue, AudioWorker, EnqueueResult

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
    """Ensure audio worker is running and healthy; restart if dead or stuck."""
    global _audio_worker
    import logging
    log = logging.getLogger(__name__)
    
    if _audio_worker is None or not _audio_worker.is_alive_and_healthy():
        # Stop old worker if it exists but is dead
        if _audio_worker is not None:
            try:
                was_alive = _audio_worker.is_alive()
                _audio_worker.stop()
                _audio_worker.join(timeout=2.0)
                if was_alive:
                    log.warning("Audio worker was alive but unhealthy, restarting")
                else:
                    log.warning("Audio worker was dead, restarting")
            except Exception as e:
                log.error("Error stopping old worker: %s", e, exc_info=True)
        
        try:
            _audio_worker = AudioWorker(cache=_get_audio_cache(), queue=_get_audio_queue())
            _audio_worker.start()
            # Give it a moment to start, then verify
            import time
            time.sleep(0.1)
            if _audio_worker.is_alive():
                log.info("Audio worker started successfully (thread alive)")
            else:
                log.error("Audio worker thread died immediately after start!")
        except Exception as e:
            log.error("Failed to start audio worker: %s", e, exc_info=True)
            _audio_worker = None


def _prefetch_audio_for_events(events):
    """
    Prefetch audio for events. Explicitly tracks and logs all failure modes.
    
    Returns:
        dict with statistics: enqueued, skipped_cached, skipped_no_text, 
        skipped_no_actor, skipped_no_voice, rejected_duplicate, rejected_full
    """
    _ensure_worker()
    cache = _get_audio_cache()
    queue = _get_audio_queue()

    from mysite.universe.models.actor import Pilot, Controller, Satellite, Actor as BaseActor
    import logging
    log = logging.getLogger(__name__)

    stats = {
        'enqueued': 0,
        'skipped_cached': 0,
        'skipped_no_text': 0,
        'skipped_no_actor': 0,
        'skipped_no_voice': 0,
        'rejected_duplicate': 0,
        'rejected_full': 0,
    }

    for ev in events:
        # Check if already cached
        if cache.get(ev.id):
            stats['skipped_cached'] += 1
            log.debug("Prefetch skip event_id=%s (already cached)", ev.id)
            continue
        
        # Check for text
        text = getattr(ev, "text", "") or ""
        if not text.strip():
            stats['skipped_no_text'] += 1
            log.warning("Prefetch skip event_id=%s (no text)", ev.id)
            continue
        
        meta = getattr(ev, "metadata", None) or {}

        # Resolve voice from metadata or actor profile
        voice_id = meta.get("voice_id")
        actor = None
        actor_lookup_method = None
        
        if not voice_id:
            # Prefer actor_id from metadata to avoid name collisions
            actor_id = meta.get("actor_id")
            if actor_id:
                try:
                    actor = BaseActor.objects.get(id=actor_id)
                    actor_lookup_method = "actor_id"
                except BaseActor.DoesNotExist:
                    log.warning("Event %s references non-existent actor_id=%s", ev.id, actor_id)
            
            # Fallback to name lookup if no actor_id
            if not actor:
                actors = list(Pilot.objects.filter(name=ev.actor_name).order_by("-id"))
                actors.extend(Controller.objects.filter(name=ev.actor_name).order_by("-id"))
                actors.extend(Satellite.objects.filter(name=ev.actor_name).order_by("-id"))
                actors.extend(BaseActor.objects.filter(name=ev.actor_name).order_by("-id"))
                
                if len(actors) > 1:
                    log.warning("Multiple actors found with name '%s' (count=%d), using most recent (id=%s) for event %s",
                               ev.actor_name, len(actors), actors[0].id, ev.id)
                actor = actors[0] if actors else None
                if actor:
                    actor_lookup_method = "name"
            
            if not actor:
                # Actor not found - will use fallback voice, but log the issue
                log.warning("Event %s actor not found (name='%s', actor_id=%s), will use fallback voice", 
                           ev.id, ev.actor_name, meta.get("actor_id"))
                voice_id = None
            else:
                # Actor found - try to get voice from profile
                try:
                    profile = actor.audio_profile
                    vp = profile.get_voice_params() or {}
                    voice_id = vp.get("voice_template")
                except BaseActor.audio_profile.RelatedObjectDoesNotExist:
                    log.warning("Event %s actor (id=%s, name='%s', lookup=%s) has no audio_profile", 
                               ev.id, actor.id, actor.name, actor_lookup_method)
                    voice_id = None
        
        if not voice_id:
            # Fallback defaults - but log that we're using fallback
            voice_id = "pilot_default"
            if actor is None:
                stats['skipped_no_actor'] += 1
                log.warning("Prefetch event_id=%s using fallback voice='%s' (no actor found)", 
                           ev.id, voice_id)
            else:
                stats['skipped_no_voice'] += 1
                log.warning("Prefetch event_id=%s using fallback voice='%s' (actor had no voice_template)", 
                           ev.id, voice_id)

        # Sentence-case the text to avoid spelled-out ALL CAPS
        speak_text = _sentence_case(text)
        job = AudioJob(event_id=ev.id, text=speak_text, voice_id=voice_id)
        
        # Enqueue with explicit result tracking
        result = queue.enqueue(job)
        if result == EnqueueResult.SUCCESS:
            stats['enqueued'] += 1
            log.info("Prefetch enqueue event_id=%s voice=%s actor_lookup=%s", 
                    ev.id, voice_id, actor_lookup_method or "metadata")
        elif result == EnqueueResult.DUPLICATE:
            stats['rejected_duplicate'] += 1
            log.debug("Prefetch skip event_id=%s (already queued or in-flight)", ev.id)
        elif result == EnqueueResult.QUEUE_FULL:
            stats['rejected_full'] += 1
            log.warning("Prefetch REJECTED event_id=%s (queue full, capacity=%d)", 
                       ev.id, queue.capacity)
    
    # Log summary if any events were processed
    if sum(stats.values()) > 0:
        log.info("Prefetch summary: %s", stats)
    
    return stats


def _select_upcoming_events(sim_time, limit: int = 12):
    """
    Fetch upcoming events after sim_time within a horizon, ordered by timestamp/id.
    Prioritizes near-term events by using a smaller horizon first, then expanding.
    """
    # First, try to get events within a shorter horizon (5 minutes) to prioritize near-term
    near_horizon = sim_time + min(300.0, _AUDIO_PREFETCH_HORIZON_SECONDS / 6)
    near_events = list(DialogueEventLog.objects.filter(
        timestamp__gt=sim_time, 
        timestamp__lte=near_horizon
    ).order_by("timestamp", "id")[:limit])
    
    # If we have room, expand to full horizon
    if len(near_events) < limit:
        far_horizon = sim_time + _AUDIO_PREFETCH_HORIZON_SECONDS
        far_events = DialogueEventLog.objects.filter(
            timestamp__gt=near_horizon,
            timestamp__lte=far_horizon
        ).order_by("timestamp", "id")[:limit - len(near_events)]
        near_events.extend(far_events)
    
    return near_events[:min(limit, _AUDIO_PREFETCH_MAX_EVENTS)]


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
    
    # Worker/queue/cache status for debugging - explicit failure tracking
    worker_status = {}
    if _audio_worker is not None:
        worker_status = _audio_worker.get_stats()
        worker_status['exists'] = True
    else:
        worker_status = {
            'exists': False,
            'alive': False,
            'healthy': False,
            'tts_available': False,
        }
    
    queue_status = _get_audio_queue().get_stats()
    cache_status = _get_audio_cache().get_stats()
    
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
            'worker': worker_status,
            'queue': queue_status,
            'cache': cache_status,
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
    Serve audio WAV for an event.
    
    Returns:
        200 with WAV bytes if audio is ready
        404 with error details if audio not found (never generated, evicted, or generation failed)
    """
    cache = _get_audio_cache()
    queue = _get_audio_queue()
    event_id_int = int(event_id)
    
    entry = cache.get(event_id_int)
    if not entry:
        # Check if it's in queue or in-flight (being processed)
        with queue._lock:
            in_queue = any(j.event_id == event_id_int for j in queue._queue)
            in_flight = event_id_int in queue._inflight
        
        reason = "not_found"
        if in_flight:
            reason = "generating"
        elif in_queue:
            reason = "queued"
        else:
            # Check cache stats to see if it was evicted
            cache_stats = cache.get_stats()
            if cache_stats['evictions'] > 0:
                reason = "possibly_evicted"
        
        return JsonResponse({
            "status": "error",
            "message": f"Audio not ready for event {event_id_int}",
            "reason": reason,
            "in_queue": in_queue,
            "in_flight": in_flight,
        }, status=404)
    
    resp = HttpResponse(entry.wav_bytes, content_type="audio/wav")
    resp["Cache-Control"] = "no-store"
    return resp


@require_http_methods(["POST"])
def ensure_audio_worker(request):
    """
    Ensure the audio worker is running; explicitly reports status.
    
    Returns:
        200 with worker status (exists, alive, healthy, tts_available)
        500 if worker failed to start
    """
    import logging
    log = logging.getLogger(__name__)
    
    try:
        _ensure_worker()
        worker = _audio_worker
        if worker is None:
            return JsonResponse({
                "status": "error",
                "message": "Worker is None after _ensure_worker()",
            }, status=500)
        
        # Give it a moment to initialize
        import time
        time.sleep(0.2)
        
        stats = worker.get_stats() if hasattr(worker, 'get_stats') else {}
        status = {
            "status": "ok",
            "worker": {
                "exists": True,
                "alive": worker.is_alive(),
                "healthy": worker.is_alive_and_healthy() if hasattr(worker, 'is_alive_and_healthy') else worker.is_alive(),
                **stats,
            }
        }
        
        if not worker.is_alive():
            log.error("Worker thread died after start")
            status["status"] = "error"
            status["message"] = "Worker thread died immediately after start"
            return JsonResponse(status, status=500)
        
        return JsonResponse(status)
    except Exception as e:
        log.error("Failed to ensure audio worker: %s", e, exc_info=True)
        return JsonResponse({
            "status": "error",
            "message": str(e),
            "worker": {
                "exists": _audio_worker is not None,
                "alive": _audio_worker.is_alive() if _audio_worker else False,
            }
        }, status=500)
