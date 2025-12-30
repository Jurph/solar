"""
In-memory audio cache and simple job queue for event TTS clips.
Bounded to avoid unbounded memory usage and avoid disk writes.

All operations are explicit about success/failure - no silent failures.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional
from enum import Enum

from mysite.universe.services.tts_service import get_tts_service


@dataclass
class AudioEntry:
    event_id: int
    voice_id: str
    duration_s: float
    wav_bytes: bytes
    created_at: float


class EnqueueResult(Enum):
    """Result of attempting to enqueue a job."""
    SUCCESS = "success"
    DUPLICATE = "duplicate"  # Already queued or in-flight
    QUEUE_FULL = "queue_full"  # Queue at capacity


class AudioCache:
    def __init__(self, capacity: int = 12):
        self.capacity = capacity
        self._lock = threading.Lock()
        self._entries: Dict[int, AudioEntry] = {}
        self._order: Deque[int] = deque()
        self._evictions = 0  # Track evictions for diagnostics

    def get(self, event_id: int) -> Optional[AudioEntry]:
        """Get audio entry for event_id. Returns None if not found (never cached or evicted)."""
        with self._lock:
            return self._entries.get(event_id)

    def put(self, entry: AudioEntry) -> bool:
        """
        Store audio entry in cache.
        
        Returns:
            True if entry was stored (new or replaced existing)
            False if entry already exists (no-op)
        """
        with self._lock:
            if entry.event_id in self._entries:
                return False  # Already exists
            self._entries[entry.event_id] = entry
            self._order.append(entry.event_id)
            evicted = 0
            while len(self._order) > self.capacity:
                evict_id = self._order.popleft()
                self._entries.pop(evict_id, None)
                evicted += 1
            if evicted > 0:
                self._evictions += evicted
            return True

    def get_stats(self) -> dict:
        """Get cache statistics for diagnostics."""
        with self._lock:
            return {
                'cached': len(self._entries),
                'capacity': self.capacity,
                'evictions': self._evictions,
            }


class AudioJob:
    def __init__(self, event_id: int, text: str, voice_id: str):
        self.event_id = event_id
        self.text = text
        self.voice_id = voice_id


class AudioJobQueue:
    def __init__(self, capacity: int = 50):
        self.capacity = capacity
        self._lock = threading.Lock()
        self._queue: Deque[AudioJob] = deque()
        self._inflight = set()
        self._rejects_duplicate = 0  # Track duplicate rejections
        self._rejects_full = 0  # Track full-queue rejections

    def enqueue(self, job: AudioJob) -> EnqueueResult:
        """
        Enqueue a job for processing.
        
        Returns:
            EnqueueResult.SUCCESS if job was enqueued
            EnqueueResult.DUPLICATE if job already queued or in-flight
            EnqueueResult.QUEUE_FULL if queue is at capacity
        """
        with self._lock:
            if job.event_id in self._inflight or any(j.event_id == job.event_id for j in self._queue):
                self._rejects_duplicate += 1
                return EnqueueResult.DUPLICATE
            if len(self._queue) >= self.capacity:
                self._rejects_full += 1
                return EnqueueResult.QUEUE_FULL
            self._queue.append(job)
            return EnqueueResult.SUCCESS

    def pop(self) -> Optional[AudioJob]:
        """Pop next job from queue. Returns None if queue is empty."""
        with self._lock:
            if not self._queue:
                return None
            job = self._queue.popleft()
            self._inflight.add(job.event_id)
            return job

    def complete(self, job: AudioJob) -> None:
        """Mark job as complete (remove from in-flight)."""
        with self._lock:
            self._inflight.discard(job.event_id)

    def get_stats(self) -> dict:
        """Get queue statistics for diagnostics."""
        with self._lock:
            return {
                'queued': len(self._queue),
                'in_flight': len(self._inflight),
                'capacity': self.capacity,
                'rejects_duplicate': self._rejects_duplicate,
                'rejects_full': self._rejects_full,
            }


class AudioWorker(threading.Thread):
    def __init__(self, cache: AudioCache, queue: AudioJobQueue, sample_rate: int = 48000):
        super().__init__(daemon=True)
        self.cache = cache
        self.queue = queue
        self.sample_rate = sample_rate
        self._stop = threading.Event()
        self._last_activity = time.time()  # Track last successful job completion
        self._tts_available = False  # Track if TTS service is available
        self._jobs_processed = 0
        self._jobs_failed = 0
        self._jobs_skipped_no_tts = 0
        import os
        # Defensive env to dodge protobuf descriptor issues
        os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
        os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
    
    def is_alive_and_healthy(self, max_idle_seconds: float = 300.0) -> bool:
        """Check if worker is alive and has been active recently."""
        if not self.is_alive():
            return False
        # If worker has been idle too long, consider it unhealthy (may be stuck)
        idle_time = time.time() - self._last_activity
        return idle_time < max_idle_seconds
    
    def get_stats(self) -> dict:
        """Get worker statistics for diagnostics."""
        return {
            'alive': self.is_alive(),
            'healthy': self.is_alive_and_healthy(),
            'tts_available': self._tts_available,
            'jobs_processed': self._jobs_processed,
            'jobs_failed': self._jobs_failed,
            'jobs_skipped_no_tts': self._jobs_skipped_no_tts,
            'last_activity': self._last_activity,
        }

    def run(self):
        import logging
        log = logging.getLogger(__name__)
        log.info("AudioWorker thread starting")
        
        # Try to get TTS service - if this fails, worker can't process jobs
        try:
            svc = get_tts_service()
            log.info("AudioWorker TTS service loaded successfully")
            self._tts_available = True
        except Exception as e:
            log.error("AudioWorker failed to load TTS service: %s", e, exc_info=True)
            # Worker will still run but all jobs will fail
            svc = None
            self._tts_available = False
        
        while not self._stop.is_set():
            job = self.queue.pop()
            if not job:
                time.sleep(0.1)
                continue
            
            if svc is None:
                log.error("Cannot process job %s: TTS service not available", job.event_id)
                self._jobs_skipped_no_tts += 1
                self.queue.complete(job)
                continue
                
            try:
                log.info("TTS generate start event_id=%s voice=%s text_len=%d", 
                        job.event_id, job.voice_id, len(job.text))
                wav_bytes = svc.generate(text=job.text, voice_id=job.voice_id)
                
                if not wav_bytes or len(wav_bytes) == 0:
                    raise ValueError(f"TTS returned empty audio for event_id={job.event_id}")
                
                import wave
                import io

                with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate() or self.sample_rate
                    duration = frames / float(rate)

                entry = AudioEntry(
                    event_id=job.event_id,
                    voice_id=job.voice_id,
                    duration_s=duration,
                    wav_bytes=wav_bytes,
                    created_at=time.time(),
                )
                stored = self.cache.put(entry)
                if not stored:
                    log.warning("Audio entry for event_id=%s already existed in cache (race condition?)", job.event_id)
                
                log.info("TTS generate done event_id=%s duration=%.2fs bytes=%d cached=%s", 
                        job.event_id, duration, len(wav_bytes), stored)
                self._last_activity = time.time()  # Track successful completion
                self._jobs_processed += 1
            except Exception as e:
                # Log error but don't crash worker - mark job complete so queue doesn't block
                log.error("TTS generate failed for event_id=%s voice=%s: %s", 
                         job.event_id, job.voice_id, e, exc_info=True)
                self._jobs_failed += 1
                # Job will be marked complete in finally, but no cache entry = audio_ready stays False
            finally:
                self.queue.complete(job)
                # Update activity even on failure (worker is still processing)
                self._last_activity = time.time()

    def stop(self):
        self._stop.set()
