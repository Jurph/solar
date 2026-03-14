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
import subprocess
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

_CURRENT_TEST_NODEID: ContextVar[Optional[str]] = ContextVar(
    "_CURRENT_TEST_NODEID", default=None
)


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
                "input_chars": sum(len(m.get("content", "")) for m in messages)
                if isinstance(messages, list)
                else None,
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

            user_message = kwargs.get(
                "user_message", args[0] if len(args) > 0 else None
            )
            system_prompt = kwargs.get(
                "system_prompt", args[1] if len(args) > 1 else None
            )

            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "test": nodeid,
                "method": "LLMService.generate_with_system_prompt",
                "ok": ok,
                "seconds": end - start,
                "input_chars": (
                    len(system_prompt) if isinstance(system_prompt, str) else 0
                )
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


@pytest.fixture(scope="session", autouse=True)
def _log_vram_baseline():
    """
    Record driver-level VRAM at session start so we can see each process's footprint.

    Useful for deriving real thresholds: Ollama's model is already resident before
    any test runs, so this snapshot captures it as part of the baseline.
    Written to artifacts/vram_baseline.json alongside the LLM benchmark log.
    """
    if os.getenv("SOLAR_LOG_VRAM_BASELINE") != "1":
        return

    try:
        import torch

        if not torch.cuda.is_available():
            return

        free_bytes, total_bytes = torch.cuda.mem_get_info(0)
        props = torch.cuda.get_device_properties(0)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "gpu_name": props.name,
            "total_mb": total_bytes // (1024 * 1024),
            "free_mb": free_bytes // (1024 * 1024),
            "used_mb": (total_bytes - free_bytes) // (1024 * 1024),
        }
        path = Path("artifacts") / "vram_baseline.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                import json as _json

                _json.dump(record, f, indent=2)
        except Exception:
            pass
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def _tts_warmup_if_slow(pytestconfig):
    """
    If running slow tests, kick off a small TTS warmup early to pay the cold-start cost up front.
    Skipped automatically if the VRAM gate (pytest_collection_modifyitems) has already marked
    slow tests as skipped due to insufficient VRAM.
    """
    markers = pytestconfig.getoption("-m") or ""
    if "slow" not in markers:
        return
    if _free_vram_mb() is not None and _free_vram_mb() < _MIN_FREE_VRAM_MB:
        return  # VRAM gate will have skipped the slow tests; don't waste time loading the model
    try:
        from mysite.universe.services.tts_service import warm_tts_service

        warm_tts_service()
    except Exception:
        # Best-effort; don't fail collection if warmup is unavailable.
        pass


# ---------------------------------------------------------------------------
# VRAM gate: skip @slow tests when there isn't enough GPU memory
# ---------------------------------------------------------------------------

# Minimum free VRAM required to run @slow tests. Based on measured Chatterbox
# model footprint (~9,274 MB) plus a small buffer. Override via env var.
_MIN_FREE_VRAM_MB: int = int(os.getenv("SOLAR_MIN_FREE_VRAM_MB", "9500"))


def _free_vram_mb() -> Optional[int]:
    """Return driver-level free VRAM on device 0 in MB, or None if CUDA is unavailable."""
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        free_bytes, _ = torch.cuda.mem_get_info(0)
        return free_bytes // (1024 * 1024)
    except Exception:
        return None


def _gpu_process_table() -> str:
    """
    Build a human-readable table of GPU processes using nvidia-smi + psutil.

    On Windows WDDM, per-process VRAM is not reported by the driver, so the
    table shows PID, process name, and enough of the command line to identify
    the culprit (e.g. audio_worker, ollama).  Returns an empty string on any
    failure so callers never need to guard against exceptions.
    """
    try:
        import psutil

        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""

        rows: List[Tuple[str, str, str]] = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 1:
                continue
            pid_str = parts[0]
            mem_str = parts[2] if len(parts) > 2 else "[N/A]"
            try:
                proc = psutil.Process(int(pid_str))
                name = proc.name()
                # Last two cmdline tokens are usually enough to identify purpose
                cmdline_tail = " ".join((proc.cmdline() or [])[-2:])
            except Exception:
                # Fallback: basename of nvidia-smi's reported path
                raw_path = parts[1] if len(parts) > 1 else "?"
                name = raw_path.replace("\\", "/").split("/")[-1]
                cmdline_tail = ""
            rows.append((pid_str, mem_str, f"{name}  {cmdline_tail}".strip()))

        if not rows:
            return "  (no GPU compute processes found)"

        lines = ["  PID      VRAM     Process / Command"]
        lines.append("  -------  -------  " + "-" * 50)
        for pid_str, mem_str, label in rows:
            vram_col = mem_str if mem_str not in ("[N/A]", "N/A") else "N/A (WDDM)"
            lines.append(f"  {pid_str:>7}  {vram_col:<9}  {label}")
        return "\n".join(lines)
    except Exception:
        return ""


def pytest_collection_modifyitems(
    config: pytest.Config, items: List[pytest.Item]
) -> None:
    """
    Skip all @slow tests when free VRAM is below _MIN_FREE_VRAM_MB.

    Prints a process table to the terminal so the user can see what is
    consuming GPU memory and decide what to kill before retrying.
    Override the threshold via the SOLAR_MIN_FREE_VRAM_MB environment variable.
    """
    slow_items = [item for item in items if item.get_closest_marker("slow")]
    if not slow_items:
        return

    free = _free_vram_mb()
    if free is None or free >= _MIN_FREE_VRAM_MB:
        return

    tw = config.get_terminal_writer()
    tw.line()
    tw.line(
        f"VRAM gate: {free} MB free, {_MIN_FREE_VRAM_MB} MB required for @slow tests.",
        red=True,
    )
    table = _gpu_process_table()
    if table:
        tw.line("GPU processes:")
        tw.line(table)
    tw.line(
        f"Skipping {len(slow_items)} @slow test(s). "
        "Kill GPU-resident processes and retry, "
        "or set SOLAR_MIN_FREE_VRAM_MB to lower the threshold.",
        yellow=True,
    )
    tw.line()

    reason = (
        f"Insufficient VRAM: {free} MB free, {_MIN_FREE_VRAM_MB} MB required. "
        "Kill GPU-resident processes and retry."
    )
    skip_marker = pytest.mark.skip(reason=reason)
    for item in slow_items:
        item.add_marker(skip_marker)
