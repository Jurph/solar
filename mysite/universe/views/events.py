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
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.cache import cache

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.services.audio_plans import build_audio_plan_for_dialogue_event
from mysite.universe.views.dev_guard import state_changing_dev_only

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
        logger.warning(
            "Event %s missing actor reference (name='%s'), using fallback voice",
            event.id,
            event.actor_name,
        )
        return "pilot_default"

    actor = event.actor

    # Get or create audio profile
    from mysite.universe.models.audio_profile import AudioProfile
    from mysite.universe.models.actor import Pilot, Controller, Satellite

    try:
        profile = actor.audio_profile
    except AudioProfile.DoesNotExist:
        # Profile missing - assign on-demand
        logger.info(
            "Event %s actor (id=%s, name='%s') missing audio_profile, assigning on-demand",
            event.id,
            actor.id,
            actor.name,
        )

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
        logger.warning(
            "Event %s actor (id=%s, name='%s') has no voice_template, using fallback",
            event.id,
            actor.id,
            actor.name,
        )
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
            return t[:i] + ch.upper() + t[i + 1 :]
    return t


def _event_audio_file_available(event: DialogueEventLog) -> bool:
    """Return True only when the stored audio file can actually be opened."""
    if not event.audio_file:
        return False

    try:
        with event.audio_file.open("rb") as f:
            f.read(1)
        return True
    except FileNotFoundError:
        logger.warning("event_feed: stored audio file missing for event %s", event.id)
        return False


@require_http_methods(["GET"])
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
    after_id = request.GET.get("after_id")
    after_ts = request.GET.get("after_ts")
    raw_limit = request.GET.get("limit", "100")
    try:
        limit = int(raw_limit)
    except ValueError:
        return JsonResponse(
            {"status": "error", "message": "Invalid limit; must be an integer."},
            status=400,
        )
    if limit < 0:
        return JsonResponse(
            {"status": "error", "message": "limit must be non-negative."},
            status=400,
        )

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

    logger.debug(
        "event_feed: sim_time=%.2f after_ts=%s limit=%s",
        sim_time,
        after_ts,
        limit,
    )

    # Check which events have cached mixed audio
    cached_event_ids = set()
    for event in queryset:
        cache_key = f"mixed_audio:{event.id}"
        if cache.get(cache_key):
            cached_event_ids.add(event.id)

    # Convert to list of dicts with only essential fields
    events = []
    for event in queryset:
        try:
            audio_plan = build_audio_plan_for_dialogue_event(event)
        except ValueError:
            logger.error(
                "event_feed: actor-less event %s (actor_name=%r) — audio plan skipped",
                event.id,
                event.actor_name,
            )
            audio_plan = []
        audio_ready = _event_audio_file_available(event) or event.id in cached_event_ids
        events.append(
            {
                "id": event.id,
                "timestamp": event.timestamp,
                "actor_name": event.actor_name,
                "text": event.text,
                "metadata": event.metadata if event.metadata is not None else {},
                # Python-defined audio plan (client just queues & plays waveforms)
                "audio_plan": audio_plan,
                # Audio is ready if pre-rendered OR cached
                "audio_ready": audio_ready,
                "audio_duration_s": None,  # Client can determine from WAV headers
                "audio_url": f"/api/event_audio/{event.id}/",
            }
        )

    # Get latest ID for client to track progress
    latest_id = events[-1]["id"] if events else None
    latest_cursor = (
        {"timestamp": events[-1]["timestamp"], "id": events[-1]["id"]}
        if events
        else None
    )

    # Debug: count how many events are pending (future) vs available (past)
    total_events = DialogueEventLog.objects.count()
    available_events = DialogueEventLog.objects.filter(timestamp__lte=sim_time).count()
    pending_events = total_events - available_events

    # Find the next pending event (first event with timestamp > sim_time)
    next_event = (
        DialogueEventLog.objects.filter(timestamp__gt=sim_time)
        .order_by("timestamp")
        .first()
    )
    next_event_timestamp = next_event.timestamp if next_event else None
    time_until_next = (
        (next_event_timestamp - sim_time) if next_event_timestamp else None
    )

    # TTS cache statistics
    events_with_audio = len(cached_event_ids)
    events_needing_audio = len(events) - events_with_audio

    logger.debug(
        "event_feed: returning %d events (cached=%d pending=%d)",
        len(events),
        events_with_audio,
        events_needing_audio,
    )

    return JsonResponse(
        {
            "events": events,
            "debug": {
                "sim_time": sim_time,
                "total_events": total_events,
                "available_events": available_events,
                "pending_events": pending_events,
                "after_id": after_id,
                "after_ts": after_ts,
                "cursor_mode": "timestamp",
                "returned_count": len(events),
                "next_event_timestamp": next_event_timestamp,
                "time_until_next": time_until_next,
                "audio": {
                    "cached": events_with_audio,
                    "pending": events_needing_audio,
                },
            },
            "latest_id": latest_id,
            "latest_cursor": latest_cursor,
            "simulation_time": sim_time,
        }
    )


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


@state_changing_dev_only
@require_http_methods(["POST"])
def clear_events(request):
    """
    API endpoint to clear all dialogue events from the database.

    Also deletes associated audio files from media/rendered_audio/.
    Useful for starting fresh without restarting the server.
    Resets the event queue to empty state.

    Returns:
        JSON with status and count of cleared events
    """
    import os

    try:
        # Get all events before deleting to clean up audio files
        events_with_audio = DialogueEventLog.objects.exclude(audio_file="").exclude(
            audio_file__isnull=True
        )
        audio_files_deleted = 0

        for event in events_with_audio:
            try:
                if event.audio_file and os.path.exists(event.audio_file.path):
                    event.audio_file.delete(save=False)
                    audio_files_deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete audio file for event {event.id}: {e}")

        # Delete all events from database
        count, _ = DialogueEventLog.objects.all().delete()

        # Clear Django cache
        cache.clear()

        return JsonResponse(
            {
                "status": "success",
                "message": f"Cleared {count} dialogue events and {audio_files_deleted} audio files from the database.",
            }
        )
    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": f"Failed to clear events: {str(e)}"},
            status=500,
        )


@require_http_methods(["GET", "HEAD"])
def event_audio(request, event_id: int):
    """
    Serve fully-mixed audio WAV for an event (quindars + TTS + room tone).

    Architecture:
    - Check for pre-rendered file (from audio_worker)
    - Check Django cache for final mixed audio
    - If miss, return 202 Accepted (worker will generate)

    The web server ONLY serves pre-rendered audio. All TTS generation
    happens in the background audio_worker to avoid blocking the web server.

    Supports HEAD requests to check cache status without generating.

    Returns:
        200 with mixed WAV bytes (GET) or headers only (HEAD) if audio available
        202 if audio not yet generated (worker will process)
        404 if event not found
    """

    logger.debug("event_audio: %s request for event %s", request.method, event_id)

    # Get event
    try:
        event = DialogueEventLog.objects.get(id=event_id)
    except DialogueEventLog.DoesNotExist:
        logger.error(f"event_audio: Event {event_id} not found in database")
        return JsonResponse(
            {
                "status": "error",
                "message": f"Event {event_id} not found",
            },
            status=404,
        )

    # Actor-less events are a critical invariant violation — audio can never be generated.
    if not event.actor:
        logger.error(
            "event_audio: Event %s has no actor reference (actor_name=%r) — cannot serve audio.",
            event_id,
            event.actor_name,
        )
        return JsonResponse(
            {
                "status": "error",
                "message": f"Event {event_id} has no actor — audio cannot be generated for actor-less events.",
            },
            status=400,
        )

    # Check cache first
    cache_key = f"mixed_audio:{event_id}"
    mixed_wav_bytes = cache.get(cache_key)

    # HEAD requests: only check cache and pre-rendered files, don't generate
    if request.method == "HEAD":
        # Check for pre-rendered file first
        if event.audio_file:
            try:
                # Verify file exists and get size
                with event.audio_file.open("rb") as f:
                    file_size = len(f.read())
                logger.debug(
                    f"event_audio: HEAD request - pre-rendered file found for event {event_id}"
                )
                resp = HttpResponse(content_type="audio/wav")
                resp["Cache-Control"] = "public, max-age=3600"
                resp["Content-Length"] = file_size
                return resp
            except FileNotFoundError:
                logger.warning(
                    f"event_audio: HEAD request - pre-rendered file missing for event {event_id}"
                )
                # Fall through to cache check
        # Check cache
        if mixed_wav_bytes:
            logger.debug(f"event_audio: HEAD request - cache hit for event {event_id}")
            resp = HttpResponse(content_type="audio/wav")
            resp["Cache-Control"] = "public, max-age=3600"
            resp["Content-Length"] = len(mixed_wav_bytes)
            return resp
        else:
            # Audio not ready - return 202 (same as GET)
            logger.debug(
                f"event_audio: HEAD request - audio not ready for event {event_id}, returning 202"
            )
            return JsonResponse(
                {"status": "pending", "message": "Audio not yet generated."}, status=202
            )

    # Check for pre-rendered file (from audio worker)
    if event.audio_file:
        logger.debug("event_audio: serving pre-rendered audio for event %s", event_id)
        try:
            # Use Django's storage backend to read the file
            with event.audio_file.open("rb") as f:
                pre_rendered_wav = f.read()
            resp = HttpResponse(pre_rendered_wav, content_type="audio/wav")
            resp["Cache-Control"] = "public, max-age=3600"
            return resp
        except FileNotFoundError:
            logger.warning(
                f"event_audio: Pre-rendered file missing for event {event_id}"
            )
            # Fall through to cache check

    # Check cache
    if mixed_wav_bytes:
        logger.debug("Mixed audio cache hit for event %s", event_id)
        resp = HttpResponse(mixed_wav_bytes, content_type="audio/wav")
        resp["Cache-Control"] = "public, max-age=3600"
        return resp

    # Cache miss - audio not ready yet
    # The audio_worker should handle generation; web server only serves pre-rendered files
    logger.info(
        "Event %s audio not ready (no pre-rendered file, not in cache). Worker should generate.",
        event_id,
    )
    return JsonResponse(
        {
            "status": "pending",
            "message": "Audio not yet generated. Background worker will process this event.",
        },
        status=202,
    )
