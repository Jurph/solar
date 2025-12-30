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
    
    logger.info(f"event_feed: Fetching events with sim_time={sim_time:.2f}, after_ts={after_ts}, limit={limit}")
    logger.info(f"event_feed: Queryset returned {queryset.count()} events")
    
    # Check which events have cached TTS audio
    cached_event_ids = set()
    for event in queryset:
        cache_key = f"tts_audio:{event.id}"
        if cache.get(cache_key):
            cached_event_ids.add(event.id)
    
    logger.info(f"event_feed: {len(cached_event_ids)} events have cached audio, {queryset.count() - len(cached_event_ids)} need TTS")
    
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
            # Audio is generated on-demand - check if already cached
            'audio_ready': event.id in cached_event_ids,
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
    
    # TTS cache statistics
    events_with_audio = len(cached_event_ids)
    events_needing_audio = len(events) - events_with_audio
    
    logger.info(f"event_feed: Returning {len(events)} events (cached: {events_with_audio}, pending: {events_needing_audio})")
    if len(events) > 0:
        logger.info(f"event_feed: First event: id={events[0]['id']}, actor={events[0]['actor_name']}, audio_url={events[0]['audio_url']}, audio_ready={events[0]['audio_ready']}")
    
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
            'audio': {
                'cached': events_with_audio,
                'pending': events_needing_audio,
            },
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


@require_http_methods(["GET", "HEAD"])
def event_audio(request, event_id: int):
    """
    Serve fully-mixed audio WAV for an event (quindars + TTS + room tone).
    
    Architecture:
    - Check Django cache for final mixed audio
    - If miss, generate synchronously:
      1. Generate TTS WAV
      2. Get audio_plan from event (quindars, room tone, modem noise)
      3. Mix all components into single WAV
      4. Cache and serve
    
    Supports HEAD requests to check cache status without generating.
    
    Returns:
        200 with mixed WAV bytes (GET) or headers only (HEAD) if audio available
        404 if event not found or audio not cached (HEAD only)
        500 if generation/mixing fails
    """
    from mysite.universe.services.tts_service import get_tts_service
    from mysite.universe.services.audio_synth import (
        SineBeep, WavFileClip, LoopedAudioFragment, ModemNoise, render_wav_bytes
    )
    import tempfile
    import wave
    import os
    
    logger.info(f"event_audio: {request.method} request for event {event_id}")
    
    # Get event
    try:
        event = DialogueEventLog.objects.get(id=event_id)
        logger.info(f"event_audio: Found event {event_id}, actor={event.actor_name}, text={event.text[:50]}")
    except DialogueEventLog.DoesNotExist:
        logger.error(f"event_audio: Event {event_id} not found in database")
        return JsonResponse({
            "status": "error",
            "message": f"Event {event_id} not found",
        }, status=404)
    
    # Check cache first
    cache_key = f"mixed_audio:{event_id}"
    mixed_wav_bytes = cache.get(cache_key)
    
    # HEAD requests: only check cache, don't generate
    if request.method == "HEAD":
        if mixed_wav_bytes:
            logger.debug(f"event_audio: HEAD request - cache hit for event {event_id}")
            resp = HttpResponse(content_type="audio/wav")
            resp["Cache-Control"] = "public, max-age=3600"
            resp["Content-Length"] = len(mixed_wav_bytes)
            return resp
        else:
            logger.debug(f"event_audio: HEAD request - cache miss for event {event_id}, returning 404")
            return HttpResponse(status=404)
    
    if mixed_wav_bytes:
        logger.debug("Mixed audio cache hit for event %s", event_id)
        resp = HttpResponse(mixed_wav_bytes, content_type="audio/wav")
        resp["Cache-Control"] = "public, max-age=3600"
        return resp
    
    # Cache miss - generate and mix synchronously
    logger.info("Mixed audio cache miss for event %s, generating...", event_id)
    
    # Get text and voice
    text = event.text
    if not text or not text.strip():
        logger.warning("Event %s has no text for TTS", event_id)
        return JsonResponse({
            "status": "error",
            "message": f"Event {event_id} has no text",
        }, status=400)
    
    logger.info("Event %s text: %s", event_id, text[:100])
    
    # Resolve voice
    try:
        voice_id = _resolve_voice_for_event(event)
        logger.info("Event %s resolved voice: %s", event_id, voice_id)
    except Exception as e:
        logger.error("Failed to resolve voice for event %s: %s", event_id, e, exc_info=True)
        return JsonResponse({
            "status": "error",
            "message": f"Voice resolution failed: {str(e)}",
        }, status=500)
    
    # Sentence-case to avoid spelled-out ALL CAPS
    speak_text = _sentence_case(text)
    logger.info("Event %s speak_text: %s", event_id, speak_text[:100])
    
    # Generate TTS
    tts_temp_file = None
    try:
        logger.info("Event %s: Getting TTS service...", event_id)
        tts_service = get_tts_service()
        logger.info("Event %s: Generating TTS (text=%d chars, voice=%s)", 
                   event_id, len(speak_text), voice_id)
        
        tts_wav_bytes = tts_service.generate(text=speak_text, voice_id=voice_id)
        
        if not tts_wav_bytes or len(tts_wav_bytes) == 0:
            logger.error("Event %s: TTS service returned empty audio", event_id)
            raise ValueError("TTS service returned empty audio")
        
        # Write TTS to temp file for mixing
        tts_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tts_temp_file.write(tts_wav_bytes)
        tts_temp_file.flush()
        tts_temp_path = tts_temp_file.name
        tts_temp_file.close()
        
        logger.info("TTS generated for event %s: %d bytes, temp path: %s", 
                   event_id, len(tts_wav_bytes), tts_temp_path)
        
        # Get TTS duration for room tone truncation
        tts_duration = 0.5  # fallback
        try:
            with wave.open(tts_temp_path, "rb") as wf:
                sr = wf.getframerate() or 0
                frames = wf.getnframes() or 0
            if sr > 0 and frames > 0:
                tts_duration = frames / float(sr)
            logger.info("Event %s: TTS duration = %.2f seconds", event_id, tts_duration)
        except Exception as e:
            logger.warning("Failed to read TTS duration for event %s: %s", event_id, e)
        
        # Build mixed audio from audio_plan
        components = []
        quindar_start_duration = 0.25
        quindar_gap = 0.05
        tts_start_time = 0.0
        
        # Parse audio_plan to build components
        audio_plan = event.audio_plan or []
        logger.info("Event %s: audio_plan has %d actions", event_id, len(audio_plan))
        
        # 1. Add "event_before" actions (quindar start)
        for action in audio_plan:
            if action.get("trigger") == "event_before":
                if action.get("preset") == "quindar_start":
                    components.append(SineBeep(
                        start_seconds=0.0,
                        duration_seconds=quindar_start_duration,
                        frequency_hz=2525.0,
                        gain=0.7
                    ))
                    tts_start_time = quindar_start_duration + quindar_gap
                    logger.info("Event %s: Added quindar_start at t=0.0", event_id)
        
        # 2. Add "event_during" actions (room tone - mixed with TTS)
        for action in audio_plan:
            if action.get("trigger") == "event_during":
                wav_url = action.get("wav_url")
                if wav_url:
                    # Room tone - loop for TTS duration, starting when TTS starts
                    from django.contrib.staticfiles import finders
                    # Extract filename from URL (e.g., /static/.../small_engine_noise.wav -> universe/audio/roomtone/small_engine_noise.wav)
                    wav_filename = os.path.basename(wav_url)
                    static_path = f"universe/audio/roomtone/{wav_filename}"
                    room_tone_path = finders.find(static_path)
                    if room_tone_path:
                        components.append(LoopedAudioFragment(
                            start_seconds=tts_start_time,
                            path=room_tone_path,
                            gain=0.3,  # Mix room tone quietly under voice
                            loop_duration_seconds=tts_duration
                        ))
                        logger.info("Event %s: Added room tone %s at t=%.2f, duration=%.2f", 
                                   event_id, wav_filename, tts_start_time, tts_duration)
                    else:
                        logger.warning("Event %s: Room tone file not found: %s", event_id, static_path)
        
        # 3. Add TTS voice
        components.append(WavFileClip(
            start_seconds=tts_start_time,
            path=tts_temp_path,
            gain=2.0  # Amplify voice so it's clear over room tone
        ))
        logger.info("Event %s: Added TTS at t=%.2f", event_id, tts_start_time)
        
        # 4. Add "event_after" actions (quindar end, modem noise)
        tts_end_time = tts_start_time + tts_duration
        quindar_end_time = tts_end_time + quindar_gap
        modem_start_time = quindar_end_time + quindar_start_duration + quindar_gap
        
        for action in audio_plan:
            if action.get("trigger") == "event_after":
                if action.get("preset") == "quindar_end":
                    components.append(SineBeep(
                        start_seconds=quindar_end_time,
                        duration_seconds=quindar_start_duration,
                        frequency_hz=2475.0,
                        gain=0.7
                    ))
                    logger.info("Event %s: Added quindar_end at t=%.2f", event_id, quindar_end_time)
                elif action.get("preset") == "modem_noise_example":
                    # Modem noise for satellites - plays after quindar end
                    modem_text = action.get("params", {}).get("text", "DATA")
                    components.append(ModemNoise(
                        start_seconds=modem_start_time,
                        text=modem_text,
                        gain=0.8,
                        baud_rate=300,
                        mark_frequency_hz=1200.0,
                        space_frequency_hz=2200.0,
                        carrier_frequency_hz=1800.0,
                        carrier_gain=0.15,
                    ))
                    logger.info("Event %s: Added modem noise at t=%.2f encoding '%s'", 
                               event_id, modem_start_time, modem_text[:20])
        
        # Mix all components into single WAV
        logger.info("Event %s: Mixing %d audio components...", event_id, len(components))
        mixed_wav_bytes = render_wav_bytes(components)
        logger.info("Event %s: Mixed audio generated: %d bytes", event_id, len(mixed_wav_bytes))
        
        # Cache for 1 hour
        cache.set(cache_key, mixed_wav_bytes, timeout=3600)
        
        # Clean up temp file
        if tts_temp_path and os.path.exists(tts_temp_path):
            os.unlink(tts_temp_path)
        
        resp = HttpResponse(mixed_wav_bytes, content_type="audio/wav")
        resp["Cache-Control"] = "public, max-age=3600"
        return resp
        
    except Exception as e:
        logger.error("Audio generation/mixing failed for event %s: %s", 
                    event_id, e, exc_info=True)
        # Clean up temp file on error
        if tts_temp_file and hasattr(tts_temp_file, 'name') and os.path.exists(tts_temp_file.name):
            try:
                os.unlink(tts_temp_file.name)
            except Exception:
                pass
        return JsonResponse({
            "status": "error",
            "message": f"Audio generation failed: {str(e)}",
            "voice_id": voice_id,
            "text_preview": speak_text[:50],
        }, status=500)
