"""
In-memory audio cache and simple job queue for event TTS clips.
Bounded to avoid unbounded memory usage and avoid disk writes.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

from mysite.universe.services.tts_service import get_tts_service


@dataclass
class AudioEntry:
    event_id: int
    voice_id: str
    duration_s: float
    wav_bytes: bytes
    created_at: float


class AudioCache:
    def __init__(self, capacity: int = 12):
        self.capacity = capacity
        self._lock = threading.Lock()
        self._entries: Dict[int, AudioEntry] = {}
        self._order: Deque[int] = deque()

    def get(self, event_id: int) -> Optional[AudioEntry]:
        with self._lock:
            return self._entries.get(event_id)

    def put(self, entry: AudioEntry) -> None:
        with self._lock:
            if entry.event_id in self._entries:
                return
            self._entries[entry.event_id] = entry
            self._order.append(entry.event_id)
            while len(self._order) > self.capacity:
                evict_id = self._order.popleft()
                self._entries.pop(evict_id, None)


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

    def enqueue(self, job: AudioJob) -> None:
        with self._lock:
            if job.event_id in self._inflight or any(j.event_id == job.event_id for j in self._queue):
                return
            if len(self._queue) >= self.capacity:
                return
            self._queue.append(job)

    def pop(self) -> Optional[AudioJob]:
        with self._lock:
            if not self._queue:
                return None
            job = self._queue.popleft()
            self._inflight.add(job.event_id)
            return job

    def complete(self, job: AudioJob) -> None:
        with self._lock:
            self._inflight.discard(job.event_id)


class AudioWorker(threading.Thread):
    def __init__(self, cache: AudioCache, queue: AudioJobQueue, sample_rate: int = 48000):
        super().__init__(daemon=True)
        self.cache = cache
        self.queue = queue
        self.sample_rate = sample_rate
        self._stop = threading.Event()
        import os
        # Defensive env to dodge protobuf descriptor issues
        os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
        os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

    def run(self):
        import logging
        log = logging.getLogger(__name__)
        svc = get_tts_service()
        while not self._stop.is_set():
            job = self.queue.pop()
            if not job:
                time.sleep(0.1)
                continue
            try:
                log.info("TTS generate start event_id=%s voice=%s", job.event_id, job.voice_id)
                wav_bytes = svc.generate(text=job.text, voice_id=job.voice_id)
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
                self.cache.put(entry)
                log.info("TTS generate done event_id=%s duration=%.2fs bytes=%d", job.event_id, duration, len(wav_bytes))
            finally:
                self.queue.complete(job)

    def stop(self):
        self._stop.set()

