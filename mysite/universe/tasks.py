"""
Celery tasks for async processing.

Currently handles:
- TTS generation (async, pre-generate before events play)
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_tts_async(
    self,
    text: str,
    voice_id: str,
    event_id: int,
    cfg_weight: float = 0.5,
    exaggeration: float = 0.5,
):
    """
    Generate TTS audio asynchronously and store result.
    
    This task is called when dialogue events are created, allowing TTS
    to be generated in the background before the event needs to play.
    
    Args:
        text: Text to synthesize
        voice_id: Voice identifier
        event_id: DialogueEventLog.id (for storing result)
        cfg_weight: Chatterbox CFG weight
        exaggeration: Chatterbox exaggeration parameter
        
    Returns:
        Cache key where TTS audio is stored
    """
    try:
        from mysite.universe.services.tts_service import get_tts_service
        
        tts_service = get_tts_service()
        
        # Generate TTS (this will cache automatically)
        wav_bytes = tts_service.generate(
            text=text,
            voice_id=voice_id,
            cfg_weight=cfg_weight,
            exaggeration=exaggeration,
        )
        
        # Store result in cache with event-specific key
        cache_key = f"tts_event:{event_id}"
        from django.core.cache import cache
        cache.set(cache_key, wav_bytes, timeout=86400)  # 24 hours
        
        # Also store in the main TTS cache (for reuse)
        tts_cache_key = tts_service._get_cache_key(text, voice_id, cfg_weight, exaggeration)
        cache.set(tts_cache_key, wav_bytes, timeout=3600)  # 1 hour
        
        logger.info(f"TTS generated async for event {event_id}, {len(wav_bytes)} bytes")
        return cache_key
        
    except Exception as e:
        logger.error(f"TTS generation failed for event {event_id}: {e}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def pregenerate_tts_for_events(event_ids: list[int]):
    """
    Pre-generate TTS for multiple events (batch processing).
    
    Useful when spawning missions with many dialogue events.
    
    Args:
        event_ids: List of DialogueEventLog.id values
    """
    from mysite.universe.models.event import DialogueEventLog
    from mysite.universe.models.actor import Actor
    from mysite.universe.models.audio_profile import AudioProfile
    
    for event_id in event_ids:
        try:
            event = DialogueEventLog.objects.get(id=event_id)
            
            # Get actor and voice profile
            actor = Actor.objects.filter(name=event.actor_name).first()
            if not actor:
                continue
            
            profile, _ = AudioProfile.objects.get_or_create(actor=actor)
            voice_params = profile.get_voice_params()
            voice_template = voice_params.get("voice_template")
            
            if not voice_template:
                # Try to infer from actor type
                from mysite.universe.models.actor import Pilot, Controller
                if isinstance(actor, Pilot):
                    voice_template = "pilot_default"
                elif isinstance(actor, Controller):
                    voice_template = "controller_default"
                else:
                    continue
            
            # Generate TTS asynchronously
            generate_tts_async.delay(
                text=event.text,
                voice_id=voice_template,
                event_id=event_id,
                cfg_weight=0.5,
                exaggeration=0.5,
            )
            
        except Exception as e:
            logger.error(f"Failed to pregenerate TTS for event {event_id}: {e}")

