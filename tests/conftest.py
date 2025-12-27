"""
Pytest hooks/fixtures.

This file implements optional LLM timing capture so that running pytest can emit a
machine-readable log of local inference speed (time-to-first-response, etc.).

Design goals:
- Never fail tests if logging can't be written (best-effort only)
- Capture per-call timings for LLMService.chat() and generate_with_system_prompt()
- Overwrite the benchmark file at the start of each test session (fresh data per run)
"""

from __future__ import annotations

import json
import os
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pytest


_CURRENT_TEST_NODEID: ContextVar[Optional[str]] = ContextVar("_CURRENT_TEST_NODEID", default=None)


def _get_benchmark_path() -> Optional[Path]:
    # Allow disabling entirely.
    if os.getenv("SOLAR_LLM_BENCH_DISABLE") == "1":
        return None

    # Default location under repo root; override via env var if desired.
    env_path = os.getenv("SOLAR_LLM_BENCH_FILE")
    if env_path:
        return Path(env_path)
    return Path("artifacts") / "llm_benchmark.jsonl"


def _safe_append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Best-effort only: never break tests due to logging issues.
        return


@pytest.fixture(autouse=True)
def _set_current_test_nodeid(request):
    token = _CURRENT_TEST_NODEID.set(request.node.nodeid)
    try:
        yield
    finally:
        _CURRENT_TEST_NODEID.reset(token)


@pytest.fixture(scope="session", autouse=True)
def _install_llm_benchmark_hooks():
    """
    Monkeypatch LLMService methods to record timings.

    This is session-scoped so it affects all tests consistently.
    Overwrites the benchmark file at the start of each test session.
    """
    path = _get_benchmark_path()
    if path is None:
        return

    # Overwrite the file at the start of each test session (remove any existing data)
    try:
        if path.exists():
            path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort only: never break tests due to logging issues.
        pass

    try:
        from mysite.universe.services.llm_service import LLMService
    except Exception:
        # If Django/settings aren't available for some reason, just skip instrumentation.
        return

    orig_chat = LLMService.chat
    orig_gen = LLMService.generate_with_system_prompt

    def wrapped_chat(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        ok = True
        exc: Optional[str] = None
        result: Optional[str] = None
        try:
            result = orig_chat(self, *args, **kwargs)
            return result
        except Exception as e:
            ok = False
            exc = f"{type(e).__name__}: {e}"
            raise
        finally:
            end = time.perf_counter()
            nodeid = _CURRENT_TEST_NODEID.get()

            messages = None
            if args:
                # Signature: chat(self, messages, ...)
                messages = args[0]
            messages = kwargs.get("messages", messages)

            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "test": nodeid,
                "method": "LLMService.chat",
                "ok": ok,
                "seconds": end - start,
                "messages_count": len(messages) if isinstance(messages, list) else None,
                "input_chars": sum(len(m.get("content", "")) for m in messages) if isinstance(messages, list) else None,
                "output_chars": len(result) if isinstance(result, str) else None,
                "temperature": kwargs.get("temperature", None),
                "max_tokens": kwargs.get("max_tokens", None),
                "use_structured_output": kwargs.get("use_structured_output", None),
                "format_provided": kwargs.get("format", None) is not None,
                "exception": exc,
            }
            _safe_append_jsonl(path, record)

    def wrapped_generate_with_system_prompt(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        ok = True
        exc: Optional[str] = None
        result: Optional[str] = None
        try:
            result = orig_gen(self, *args, **kwargs)
            return result
        except Exception as e:
            ok = False
            exc = f"{type(e).__name__}: {e}"
            raise
        finally:
            end = time.perf_counter()
            nodeid = _CURRENT_TEST_NODEID.get()

            user_message = kwargs.get("user_message", args[0] if len(args) > 0 else None)
            system_prompt = kwargs.get("system_prompt", args[1] if len(args) > 1 else None)

            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "test": nodeid,
                "method": "LLMService.generate_with_system_prompt",
                "ok": ok,
                "seconds": end - start,
                "input_chars": (len(system_prompt) if isinstance(system_prompt, str) else 0)
                + (len(user_message) if isinstance(user_message, str) else 0),
                "output_chars": len(result) if isinstance(result, str) else None,
                "temperature": kwargs.get("temperature", None),
                "max_tokens": kwargs.get("max_tokens", None),
                "exception": exc,
            }
            _safe_append_jsonl(path, record)

    # Install wrappers
    LLMService.chat = wrapped_chat  # type: ignore[method-assign]
    LLMService.generate_with_system_prompt = wrapped_generate_with_system_prompt  # type: ignore[method-assign]

    yield

    # Restore originals at end of session
    LLMService.chat = orig_chat  # type: ignore[method-assign]
    LLMService.generate_with_system_prompt = orig_gen  # type: ignore[method-assign]


