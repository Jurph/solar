"""
Signal receivers for the universe app.

This module contains receivers that respond to Django signals, such as
saving dialogue events to the database for real-time display.
"""

import logging

from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.exceptions import ObjectDoesNotExist

from mysite.universe.signals import dialogue_event_processed
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.actor import Actor, Pilot, Controller, Satellite

logger = logging.getLogger(__name__)


@receiver(dialogue_event_processed)
def save_dialogue_event_to_db(sender, event, **kwargs):
    """
    Save dialogue events to the database for real-time display.

    This receiver listens to the dialogue_event_processed signal and
    persists dialogue events to the DialogueEventLog model. Errors
    are logged but don't interrupt the simulation.

    Args:
        sender: The sender of the signal (typically SimulationQueue)
        event: The DialogueEvent dataclass instance
        **kwargs: Additional signal arguments
    """
    try:
        # Reject events from non-model actors (e.g. DummyActor used in tests).
        # Real Actor subclasses are Django models; anything else is test scaffolding
        # that should never reach the production signal handler.
        from mysite.universe.models.actor import Actor

        if not isinstance(event.actor, Actor):
            logger.warning(
                "save_dialogue_event_to_db: actor %r is not an Actor model instance "
                "(type=%s) — skipping DB write",
                getattr(event.actor, "name", event.actor),
                type(event.actor).__name__,
            )
            return

        # Extract actor name from the event
        actor_name = (
            event.actor.name if hasattr(event.actor, "name") else str(event.actor)
        )

        # Optional debug logging:
        # Writing ad-hoc log files is hostile to deployment, so this is opt-in.
        # Set DIALOGUE_EVENT_DEBUG_LOG_FILE to a filepath to enable.
        import os

        debug_log_path = os.getenv("DIALOGUE_EVENT_DEBUG_LOG_FILE")
        debug_logger = logging.getLogger("dialogue_event_debug")
        debug_logger.setLevel(logging.DEBUG)
        if debug_log_path and not debug_logger.handlers:
            handler = logging.FileHandler(debug_log_path, mode="a", encoding="utf-8")
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
                )
            )
            debug_logger.addHandler(handler)

        debug_logger.debug("=== SAVING DIALOGUE EVENT ===")
        debug_logger.debug(
            f"Actor: {actor_name} (type: {type(event.actor)}, role: {getattr(event.actor, 'role', 'N/A')})"
        )
        debug_logger.debug(f"Event text (raw): {event.text[:200]}")
        debug_logger.debug(f"Metadata: {event.metadata}")
        debug_logger.debug("=== END SAVING DIALOGUE EVENT ===\n")

        # CRITICAL: Extract natural language text from event.text
        # event.text should NEVER be JSON - it should always be natural language
        # But we add a safety check in case JSON somehow got through
        display_text = event.text

        # Safety check: if text looks like JSON, try to extract the message field
        if display_text.strip().startswith("{") or '"message"' in display_text:
            try:
                import json
                from mysite.universe.schemas.dialogue_schema import DialogueMessage

                # Try to find and extract JSON object
                start = display_text.find("{")
                end = display_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = display_text[start:end]
                    json_data = json.loads(json_str)

                    # If it's a dict with 'message' field, extract it
                    if isinstance(json_data, dict) and "message" in json_data:
                        display_text = json_data["message"]
                    # If it's already a DialogueMessage-like structure
                    elif isinstance(json_data, dict):
                        try:
                            msg_obj = DialogueMessage(**json_data)
                            display_text = msg_obj.message
                        except (ValueError, TypeError):
                            # Try to get message field directly
                            display_text = json_data.get("message", display_text)
                else:
                    # Try regex extraction as fallback
                    import re

                    # Match "message": "..." with proper escaping
                    match = re.search(
                        r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', display_text
                    )
                    if match:
                        # Unescape the message
                        display_text = (
                            match.group(1)
                            .replace('\\"', '"')
                            .replace("\\n", "\n")
                            .replace("\\\\", "\\")
                        )
                    else:
                        # If all else fails, use a fallback
                        debug_logger.error(
                            f"Could not extract message from JSON in event text: {display_text[:200]}"
                        )
                        display_text = "[Error: Could not extract dialogue message]"
            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                # If JSON parsing fails, try regex extraction
                import re

                match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', display_text)
                if match:
                    display_text = (
                        match.group(1)
                        .replace('\\"', '"')
                        .replace("\\n", "\n")
                        .replace("\\\\", "\\")
                    )
                else:
                    debug_logger.error(
                        f"Failed to parse JSON in event text: {e}. Text: {display_text[:200]}"
                    )
                    display_text = "[Error: Could not parse dialogue response]"

        # Create and save the log entry with natural language text only
        # Note: TTS enqueue happens via post_save signal (enqueue_tts_on_log_save)
        # to avoid double-enqueueing
        # Store event with actor ForeignKey reference
        # actor_name is cached from actor.name for display (survives if actor is deleted)
        DialogueEventLog.objects.create(
            timestamp=event.timestamp,
            actor=event.actor if hasattr(event, "actor") else None,
            actor_name=actor_name,
            text=display_text,
            metadata=dict(event.metadata)
            if hasattr(event, "metadata") and event.metadata
            else {},
        )

    except Exception as e:
        # Log the error but don't crash the simulation
        logger.error(f"Failed to save dialogue event to database: {e}", exc_info=True)


@receiver(post_save, sender=Actor)
@receiver(post_save, sender=Pilot)
@receiver(post_save, sender=Controller)
@receiver(post_save, sender=Satellite)
def ensure_actor_audio_profile(sender, instance, created, **kwargs):
    """
    Ensure actors have audio profiles assigned after save.

    This catches any actors created via .objects.create() that bypass .create() methods.
    Idempotent - only assigns if profile is missing or incomplete.
    """
    # Only assign on creation to avoid unnecessary work on updates
    if not created:
        return

    # Check if profile exists
    try:
        profile = instance.audio_profile
        # Check if profile is complete (has voice_template)
        vp = profile.get_voice_params() or {}
        if vp.get("voice_template"):
            return  # Profile exists and is complete
    except ObjectDoesNotExist:
        pass  # Profile missing, will assign below

    # Assign profile based on actor type
    # This is idempotent - won't overwrite existing voice_template
    if isinstance(instance, Pilot):
        Pilot.assign_audio_profile(instance)
    elif isinstance(instance, Controller):
        Controller.assign_audio_profile(instance)
    elif isinstance(instance, Satellite):
        Satellite.assign_audio_profile(instance)
    else:
        Actor.assign_audio_profile(instance)
