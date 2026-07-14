"""
Audio pre-generation worker for TTS lookahead.

This management command runs a background loop that pre-generates TTS audio
for upcoming dialogue events. It processes one actor's lines at a time to avoid
GPU contention and ensure efficient TTS generation.

Usage:
    python manage.py audio_worker

The worker will:
1. Find all events in the next hour without rendered audio
2. Group them by actor
3. Pick the actor whose first uncached event is soonest
4. Render up to 3 of their events (full audio pipeline: TTS + quindars + room tone)
5. Save to disk and update database
6. Sleep 5 seconds, then repeat
"""

import json
import os
import time
import logging
import tempfile
import wave
from collections import defaultdict
from pathlib import Path
from typing import List, Dict

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.simulation import SimulationState
from mysite.universe.services.tts_service import ChatterboxTTSService
from mysite.universe.services.audio_plans import build_audio_plan_for_dialogue_event
from mysite.universe.services.audio_synth import (
    SineBeep,
    WavFileClip,
    LoopedAudioFragment,
    ModemNoise,
    render_wav_bytes,
)

logger = logging.getLogger(__name__)

# Grace period for events slightly in the past (60 seconds)
# This allows the worker to catch events that just passed current sim time
GRACE_PERIOD = 60.0
AUDIO_WORKER_WAKE_KEY = "audio_worker_wake"


class Command(BaseCommand):
    help = "Run the audio pre-generation worker for TTS lookahead"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=3,
            help="Number of events to render per actor per batch (default: 3)",
        )
        parser.add_argument(
            "--sleep-interval",
            type=int,
            default=5,
            help="Seconds to sleep between batches (default: 5)",
        )
        parser.add_argument(
            "--lookahead-hours",
            type=float,
            default=1.0,
            help="How many hours ahead (in simulation time) to pre-generate audio (default: 1.0)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        sleep_interval = options["sleep_interval"]
        lookahead_hours = options["lookahead_hours"]
        lookahead_seconds = lookahead_hours * 3600

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting audio worker (batch_size={batch_size}, "
                f"sleep={sleep_interval}s, lookahead={lookahead_hours}h)"
            )
        )

        # Initialize TTS service
        try:
            tts_service = ChatterboxTTSService()
            self.stdout.write(self.style.SUCCESS("TTS service initialized"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to initialize TTS: {e}"))
            return

        # Run warmup test to verify TTS + file I/O + database
        try:
            import datetime
            import torch

            warmup_start = time.time()
            self.stdout.write(
                f"Running warmup test... [{datetime.datetime.now().strftime('%H:%M:%S')}]"
            )
            self.stdout.write("(If no progress in 30 seconds, test may be hanging)")

            _vram_free_mb_before_warmup: int = 0
            if torch.cuda.is_available():
                _free_bytes, _total_bytes = torch.cuda.mem_get_info(0)
                _vram_free_mb_before_warmup = _free_bytes // (1024 * 1024)
                self.stdout.write(
                    f"VRAM before warmup: {_vram_free_mb_before_warmup} MB free "
                    f"/ {_total_bytes // (1024 * 1024)} MB total"
                )

            warmup_success = self._warmup_test(tts_service)
            warmup_duration = time.time() - warmup_start

            if torch.cuda.is_available() and _vram_free_mb_before_warmup:
                _free_bytes_after, _ = torch.cuda.mem_get_info(0)
                _vram_free_mb_after_warmup = _free_bytes_after // (1024 * 1024)
                _delta_mb = _vram_free_mb_before_warmup - _vram_free_mb_after_warmup
                self.stdout.write(
                    f"VRAM after warmup: {_vram_free_mb_after_warmup} MB free "
                    f"({_delta_mb} MB consumed by TTS model load)"
                )

            if not warmup_success:
                self.stdout.write(
                    self.style.ERROR(
                        f"Warmup test failed after {warmup_duration:.1f}s - aborting"
                    )
                )
                self.stdout.write(self.style.ERROR("Check logs for details"))
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"[READY] Audio worker ready [{datetime.datetime.now().strftime('%H:%M:%S')}] "
                    f"(warmup took {warmup_duration:.1f}s)"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Warmup test crashed: {e}"))
            import traceback

            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            logger.error("Warmup test failed", exc_info=True)
            return

        # Clean up stale locks from previous crashes
        stale_locks = self._cleanup_stale_locks()
        if stale_locks > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Cleared {stale_locks} stale locks from previous crash"
                )
            )

        # Delete past-due events that can never be played
        past_due = self._delete_past_due_events()
        if past_due > 0:
            self.stdout.write(
                self.style.WARNING(f"Deleted {past_due} past-due events on startup")
            )

        # Main loop
        iteration = 0
        while True:
            iteration += 1
            try:
                # Clean up old files first
                cleaned = self._cleanup_old_files()

                sim_state = SimulationState.objects.first()
                time_scale = sim_state.time_scale if sim_state else 1.0
                effective_lookahead_seconds = self._effective_lookahead_seconds(
                    lookahead_seconds, sleep_interval, time_scale
                )

                # Process new events
                processed = self._process_batch(
                    tts_service, batch_size, effective_lookahead_seconds
                )

                if processed > 0 or cleaned > 0:
                    self.stdout.write(
                        f"[{iteration}] Processed {processed} events, cleaned {cleaned} old files"
                    )

                # Write heartbeat so the web server health_check can see
                # this worker's VRAM and TTS stats (cross-process bridge).
                self._write_heartbeat()

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\nShutting down audio worker"))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in batch: {e}"))
                logger.error("Audio worker batch error", exc_info=True)

            self._sleep_until_next_batch(sleep_interval)

    def _effective_lookahead_seconds(
        self,
        base_lookahead_seconds: float,
        sleep_interval: float,
        time_scale: float,
    ) -> float:
        """Return a lookahead window large enough to cover the next sleep."""
        return max(base_lookahead_seconds, sleep_interval * time_scale)

    def _sleep_until_next_batch(self, sleep_interval: float) -> None:
        """Sleep in short chunks so dev skip controls can wake the worker."""
        remaining = max(0.0, float(sleep_interval))
        while remaining > 0:
            if cache.get(AUDIO_WORKER_WAKE_KEY):
                cache.delete(AUDIO_WORKER_WAKE_KEY)
                return
            chunk = min(1.0, remaining)
            time.sleep(chunk)
            remaining -= chunk

    def _warmup_test(self, tts_service: ChatterboxTTSService) -> bool:
        """
        Warmup test: Verify TTS model, file I/O, and Django storage work.

        Does NOT create any DialogueEventLog records — a ghost event with
        timestamp=0 would appear in the event scroller before cleanup.

        Returns:
            True if warmup succeeded, False otherwise
        """
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        try:
            # 1. Test TTS generation (uses fallback pilot voice)
            logger.info("Warmup: Testing TTS generation...")
            tts_wav = tts_service.generate("check", "pilot_default")
            logger.info("Warmup: TTS generated (%d bytes)", len(tts_wav))

            # 2. Test Django storage round-trip (same code path as real render)
            logger.info("Warmup: Testing Django storage...")
            warmup_path = default_storage.save(
                "rendered_audio/warmup_probe.wav", ContentFile(tts_wav)
            )
            try:
                with default_storage.open(warmup_path, "rb") as f:
                    read_back = f.read()
                if len(read_back) != len(tts_wav):
                    logger.error(
                        "Warmup: Storage round-trip size mismatch (%d vs %d)",
                        len(read_back),
                        len(tts_wav),
                    )
                    return False
                logger.info("Warmup: Storage round-trip OK")
            finally:
                try:
                    default_storage.delete(warmup_path)
                except Exception:
                    pass

            logger.info("Warmup: All checks passed")
            return True

        except Exception as e:
            logger.error("Warmup test failed: %s", e, exc_info=True)
            return False

    def _cleanup_stale_locks(self) -> int:
        """
        Clear locks from previous worker crashes on startup.

        Finds events with audio_generating=True but no audio_file,
        which indicates a crash during generation.

        Returns:
            Number of locks cleared
        """
        try:
            from django.db.models import Q

            # Find events with lock but no file (crash during generation)
            stale_events = DialogueEventLog.objects.filter(
                Q(audio_file="") | Q(audio_file__isnull=True), audio_generating=True
            )

            count = stale_events.count()
            if count > 0:
                stale_events.update(audio_generating=False)
                logger.warning(f"Cleared {count} stale locks from previous crash")

            return count

        except Exception as e:
            logger.error(f"Error during stale lock cleanup: {e}")
            return 0

    def _delete_past_due_events(self) -> int:
        """
        Delete DialogueEventLog entries whose timestamp is before
        (current_sim_time - GRACE_PERIOD).  These events can never play;
        leaving them in the DB causes queue build-up and confuses worker health
        metrics.  Runs once on startup, before the main loop.

        Returns:
            Number of events deleted
        """
        try:
            sim_state = SimulationState.objects.first()
            if not sim_state:
                return 0
            cutoff = sim_state.get_simulation_time() - GRACE_PERIOD
            past_due = DialogueEventLog.objects.filter(timestamp__lt=cutoff)
            count = past_due.count()
            if count > 0:
                past_due.delete()
                logger.info(
                    "Deleted %d past-due events on startup (cutoff=%.1f)", count, cutoff
                )
            return count
        except Exception as e:
            logger.error("Error during past-due event cleanup: %s", e)
            return 0

    def _cleanup_old_files(self) -> int:
        """
        Clean up pre-rendered audio files for events that have passed.
        Deletes files for events at least 10 minutes behind current sim time.

        Returns:
            Number of files cleaned up
        """
        try:
            sim_state = SimulationState.objects.first()
            if not sim_state:
                return 0

            # Delete files for events at least 10 minutes (600s) in the past.
            # Only match events that actually have a file (exclude "" and NULL).
            cleanup_threshold = sim_state.get_simulation_time() - 600
            old_events = (
                DialogueEventLog.objects.filter(timestamp__lt=cleanup_threshold)
                .exclude(audio_file="")
                .exclude(audio_file__isnull=True)
            )

            cleaned_count = 0
            for event in old_events:
                try:
                    event_id = event.id
                    event.audio_file.delete(save=False)
                    event.delete()
                    logger.info(f"Cleaned up audio file and event {event_id}")
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete audio for event {event.id}: {e}")

            return cleaned_count

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    def _write_heartbeat(self) -> None:
        """Write a health snapshot to artifacts/audio_worker_heartbeat.json.

        This file is the cross-process bridge that lets the web server's
        health_check endpoint see the audio_worker's VRAM usage and TTS
        health — data that is otherwise invisible because the worker runs
        as a separate subprocess.
        """
        try:
            from mysite.universe.services.tts_service import get_tts_health

            heartbeat: dict = {
                "pid": os.getpid(),
                "wall_clock": time.time(),
                "tts": get_tts_health(),
            }

            try:
                import torch

                if torch.cuda.is_available():
                    props = torch.cuda.get_device_properties(0)
                    free_bytes, total_bytes = torch.cuda.mem_get_info(0)
                    allocated_mb = torch.cuda.memory_allocated(0) // (1024 * 1024)
                    reserved_mb = torch.cuda.memory_reserved(0) // (1024 * 1024)
                    heartbeat["vram"] = {
                        "device": props.name,
                        "total_mb": total_bytes // (1024 * 1024),
                        "free_mb": free_bytes // (1024 * 1024),
                        "allocated_mb": allocated_mb,
                        "reserved_mb": reserved_mb,
                    }
            except Exception:
                pass  # VRAM info is best-effort

            heartbeat_path = (
                Path(__file__).resolve().parents[4]
                / "artifacts"
                / "audio_worker_heartbeat.json"
            )
            heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: write to temp file, then rename
            tmp_path = heartbeat_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(heartbeat, indent=2))
            tmp_path.replace(heartbeat_path)
        except Exception as e:
            logger.debug("Heartbeat write failed (non-fatal): %s", e)

    def _process_batch(
        self,
        tts_service: ChatterboxTTSService,
        batch_size: int,
        lookahead_seconds: float,
    ) -> int:
        """
        Process one batch of events.

        Returns:
            Number of events processed
        """
        # Get current sim time
        try:
            sim_state = SimulationState.objects.first()
            if not sim_state:
                logger.warning("No SimulationState found")
                return 0
            current_sim_time = sim_state.get_simulation_time()
        except Exception as e:
            logger.error(f"Failed to get simulation time: {e}")
            return 0

        # Find events in lookahead window without audio (and not currently generating)
        # Include a grace period for events slightly in the past (e.g., events that just passed)
        start_time = current_sim_time - GRACE_PERIOD
        end_time = current_sim_time + lookahead_seconds

        # FileField is either NULL or empty string '' when not set
        # Use Q object to check both conditions
        from django.db.models import Q

        events_to_render = (
            DialogueEventLog.objects.filter(
                Q(audio_file="") | Q(audio_file__isnull=True),
                timestamp__gte=start_time,
                timestamp__lte=end_time,
                audio_generating=False,
            )
            .select_related("actor")
            .order_by("timestamp")
        )

        events_list = list(events_to_render)
        if not events_list:
            return 0

        # Group by actor
        events_by_actor: Dict[int, List[DialogueEventLog]] = defaultdict(list)
        for event in events_list:
            if event.actor:
                events_by_actor[event.actor.id].append(event)
            else:
                # Event without actor is a CRITICAL BUG - should never happen
                logger.error(
                    f"CRITICAL: Event {event.id} has no actor! This indicates a serious bug in event creation."
                )

        if not events_by_actor:
            logger.error(
                f"CRITICAL: No events with actors found (all {len(events_list)} events had actor=None)"
            )
            return 0

        # Pick actor whose first event is soonest
        soonest_actor_id = min(
            events_by_actor.keys(), key=lambda aid: events_by_actor[aid][0].timestamp
        )

        # Render up to batch_size events for this actor
        events_to_process = events_by_actor[soonest_actor_id][:batch_size]

        processed_count = 0
        for event in events_to_process:
            try:
                success = self._render_event(event, tts_service)
                if success:
                    processed_count += 1
            except Exception as e:
                logger.error(f"Failed to render event {event.id}: {e}", exc_info=True)

        return processed_count

    def _render_event(
        self, event: DialogueEventLog, tts_service: ChatterboxTTSService
    ) -> bool:
        """
        Render a single event: TTS + mixing + save to disk.
        Uses atomic database locking to prevent concurrent generation.

        Returns:
            True if successful, False otherwise
        """
        event_id = event.id

        # Atomically claim this event for generation
        with transaction.atomic():
            # Re-fetch with lock to ensure we have latest state
            try:
                locked_event = DialogueEventLog.objects.select_for_update().get(
                    id=event_id
                )
            except DialogueEventLog.DoesNotExist:
                logger.warning(f"Event {event_id} disappeared during processing")
                return False

            # Check if already generated or being generated
            if locked_event.audio_file or locked_event.audio_generating:
                logger.info(f"Event {event_id} already claimed or generated, skipping")
                return False

            # Claim it
            locked_event.audio_generating = True
            locked_event.save(update_fields=["audio_generating"])

        # Now we have exclusive claim on this event
        try:
            text = event.text

            # Get voice ID from event's actor
            from mysite.universe.views.events import _resolve_voice_for_event

            try:
                voice_id = _resolve_voice_for_event(event)
            except Exception as e:
                logger.error(f"Event {event_id}: Failed to resolve voice: {e}")
                return False

            # Generate TTS
            logger.info(f"Event {event_id}: Generating TTS (voice={voice_id})")
            try:
                tts_wav = tts_service.generate(text, voice_id)
            except Exception as e:
                logger.error(f"Event {event_id}: TTS generation failed: {e}")
                return False

            # Save TTS to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(tts_wav)
                tts_temp_path = tmp.name

            try:
                # Get audio plan
                audio_plan = build_audio_plan_for_dialogue_event(event)

                # Build mixed audio (quindars + TTS + room tone)
                mixed_wav = self._mix_audio(event_id, tts_temp_path, audio_plan)

                # Save to media directory using Django's storage system
                from django.core.files.base import ContentFile

                output_filename = f"event_{event_id}.wav"

                # Use Django's FileField.save() - it handles storage location
                event.audio_file.save(
                    output_filename, ContentFile(mixed_wav), save=False
                )

                # Update database - mark complete and release lock
                # Note: audio_file is already set by .save() above
                event.audio_rendered_at = timezone.now()
                event.audio_generating = False
                event.save(
                    update_fields=[
                        "audio_file",
                        "audio_rendered_at",
                        "audio_generating",
                    ]
                )

                logger.info(f"Event {event_id}: Audio rendered successfully")
                return True

            finally:
                # Clean up temp file
                try:
                    os.unlink(tts_temp_path)
                except Exception:
                    pass

        except Exception as e:
            # If anything fails, release the lock
            logger.error(f"Event {event_id}: Unexpected error: {e}", exc_info=True)
            event.audio_generating = False
            event.save(update_fields=["audio_generating"])
            return False

        finally:
            # Final safety: ensure lock is always released
            event.refresh_from_db()
            if event.audio_generating and not event.audio_file:
                logger.warning(f"Event {event_id}: Releasing stuck lock")
                event.audio_generating = False
                event.save(update_fields=["audio_generating"])

    def _mix_audio(
        self, event_id: int, tts_wav_path: str, audio_plan: List[Dict]
    ) -> bytes:
        """
        Mix TTS with quindars and room tone according to audio plan.

        This is similar to the logic in views/events.py:event_audio()
        """
        # Read TTS duration
        tts_duration = 0.5  # fallback
        try:
            with wave.open(tts_wav_path, "rb") as wf:
                sr = wf.getframerate() or 0
                frames = wf.getnframes() or 0
            if sr > 0 and frames > 0:
                tts_duration = frames / float(sr)
            logger.info(f"Event {event_id}: TTS duration = {tts_duration:.2f} seconds")
        except Exception as e:
            logger.warning(f"Event {event_id}: Failed to read TTS duration: {e}")
            # Continue with fallback duration

        components = []

        # Timing constants
        quindar_start_duration = 0.2
        quindar_gap = 0.1
        tts_start_time = quindar_start_duration + quindar_gap
        tts_end_time = tts_start_time + tts_duration
        quindar_end_gap = 0.1
        quindar_end_time = tts_end_time + quindar_end_gap
        total_duration = quindar_end_time + quindar_start_duration + 0.1

        # 1. Add "event_start" actions (quindar start)
        for action in audio_plan:
            if action.get("trigger") == "event_start":
                if action.get("preset") == "quindar_start":
                    params = action.get("params", {})
                    # Reduce quindar gain - use 0.2 instead of plan's 0.9
                    quindar_gain = params.get("gain", 0.9) * 0.2
                    components.append(
                        SineBeep(
                            start_seconds=0.0,
                            duration_seconds=quindar_start_duration,
                            frequency_hz=params.get("frequency_hz", 2525.0),
                            gain=quindar_gain,
                        )
                    )

        # 2. Add room tone (continuous background)
        for action in audio_plan:
            if action.get("preset") == "room_tone":
                params = action.get("params", {})
                wav_url = params.get("wav_url")
                if wav_url:
                    # Resolve URL to filesystem path
                    from django.contrib.staticfiles import finders
                    import os

                    wav_filename = os.path.basename(wav_url)
                    static_path = f"universe/audio/roomtone/{wav_filename}"
                    room_tone_path = finders.find(static_path)

                    if room_tone_path:
                        # Use room tone gain from plan
                        room_tone_gain = params.get("gain", 0.15)
                        components.append(
                            LoopedAudioFragment(
                                path=room_tone_path,
                                start_seconds=0.0,
                                loop_duration_seconds=total_duration,
                                gain=room_tone_gain,
                            )
                        )
                        logger.info(
                            f"Event {event_id}: Added room tone {wav_filename}, gain={room_tone_gain:.2f}"
                        )
                    else:
                        logger.warning(
                            f"Event {event_id}: Room tone file not found: {static_path}"
                        )

        # 3. Add TTS - boost gain to make voice clearer
        components.append(
            WavFileClip(
                path=tts_wav_path,
                start_seconds=tts_start_time,
                gain=2.0,  # Amplify voice so it's clear over room tone
            )
        )

        # 4. Add "event_end" actions (quindar end, modem noise)
        for action in audio_plan:
            if action.get("trigger") == "event_end":
                if action.get("preset") == "quindar_end":
                    params = action.get("params", {})
                    # Reduce quindar gain - use 0.2 instead of plan's 0.9
                    quindar_gain = params.get("gain", 0.9) * 0.2
                    components.append(
                        SineBeep(
                            start_seconds=quindar_end_time,
                            duration_seconds=quindar_start_duration,
                            frequency_hz=params.get("frequency_hz", 2475.0),
                            gain=quindar_gain,
                        )
                    )
                elif action.get("preset") in ["modem_noise", "modem_noise_example"]:
                    params = action.get("params", {})
                    modem_text = params.get("text", "DATA")
                    components.append(
                        ModemNoise(
                            start_seconds=quindar_end_time,
                            text=modem_text,
                            gain=params.get("gain", 0.8),
                            baud_rate=params.get("baud_rate", 300),
                            mark_frequency_hz=params.get("mark_frequency_hz", 1200.0),
                            space_frequency_hz=params.get("space_frequency_hz", 2200.0),
                            carrier_frequency_hz=params.get(
                                "carrier_frequency_hz", 1800.0
                            ),
                            carrier_gain=params.get("carrier_gain", 0.15),
                        )
                    )
                    logger.info(
                        f"Event {event_id}: Added modem noise encoding {modem_text[:30]}"
                    )

        # Mix all components
        sample_rate = 22050
        mixed_wav = render_wav_bytes(components, sample_rate_hz=sample_rate)

        return mixed_wav
