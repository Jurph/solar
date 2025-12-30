import logging
import threading
from collections import deque
from typing import Deque, Dict, Any


class InMemoryLogHandler(logging.Handler):
    def __init__(self, maxlen: int = 1000):
        super().__init__()
        self.buffer: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        # Filter out noisy DEBUG logs from numba and other low-level libraries
        if record.levelno == logging.DEBUG:
            # Skip numba byteflow/interpreter DEBUG spam
            if record.name.startswith("numba."):
                return
            # Skip other verbose DEBUG logs if needed
            # if record.name.startswith("transformers."):
            #     return
        
        msg = self.format(record)
        entry = {
            "level": record.levelname,
            "name": record.name,
            "message": msg,
        }
        with self._lock:
            self.buffer.append(entry)

    def tail(self, n: int = 100) -> list[Dict[str, Any]]:
        with self._lock:
            return list(self.buffer)[-n:]


_handler: InMemoryLogHandler | None = None


def get_log_handler() -> InMemoryLogHandler:
    global _handler
    if _handler is None:
        _handler = InMemoryLogHandler()
    return _handler

