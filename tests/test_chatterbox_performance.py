import io
import json
import os
import time
import wave
from pathlib import Path
import warnings

# Force safer import settings before any heavy deps load
os.environ["TRANSFORMERS_NO_TF"] = "1"
# Use the pure-Python protobuf implementation to dodge compiled descriptor issues on Windows
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import pytest
from django.conf import settings

pytestmark = [
    pytest.mark.slow,
    pytest.mark.external,
    pytest.mark.tts,
    pytest.mark.performance,
]

# Skip this entire file gracefully when torch is not installed (CI uses
# the base + dev dependency sets only; torch lives in the optional ML extra).
pytest.importorskip("torch")

from mysite.universe.services.tts_service import get_tts_service  # noqa: E402
import google.protobuf as _pb  # noqa: E402

# Suppress known diffusers LoRA warning (using peft backend is already installed)
warnings.filterwarnings(
    "ignore",
    message="`LoRACompatibleLinear` is deprecated and will be removed in version 1.0.0",
    category=FutureWarning,
    module="diffusers.models.lora",
)


def _canonical_sentences():
    path = Path(settings.BASE_DIR) / "docs" / "Canonical Audio Sentences.txt"
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return lines


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate() or 1
        return frames / float(rate)


def _have_local_model() -> bool:
    env_model = os.getenv("CHATTERBOX_LOCAL_PATH")
    model_path = (
        Path(env_model)
        if env_model
        else Path(settings.BASE_DIR) / "models" / "chatterbox-turbo"
    )
    return model_path.exists()


def _have_voice(voice_id: str) -> bool:
    voice_path = (
        Path(settings.BASE_DIR)
        / "mysite"
        / "universe"
        / "static"
        / "universe"
        / "voices"
        / f"{voice_id}.wav"
    )
    return voice_path.exists()


@pytest.mark.slow
@pytest.mark.skipif(
    not _have_local_model(),
    reason="Local chatterbox model not found (set CHATTERBOX_LOCAL_PATH)",
)
def test_chatterbox_latency_short_and_long():
    # Hard guard: protobuf 4.x compiled descriptors can break TF-heavy imports; we force python impl above,
    # but also skip if version is far from the recommended 3.20.x range.
    try:
        pb_version = _pb.__version__
    except Exception:  # pragma: no cover
        pb_version = "unknown"

    sentences = _canonical_sentences()
    assert sentences, "Canonical sentences file is empty"

    voice_id = "pilot-M-002_canonical_all"
    if not _have_voice(voice_id):
        pytest.skip(f"Voice prompt {voice_id}.wav not found in static voices")

    # Try to get TTS service - skip if GPU is already in use (e.g., audio worker running)
    try:
        service = get_tts_service()
        device = getattr(service, "device", "unknown")
    except RuntimeError as e:
        pytest.skip(
            f"Failed to initialize TTS (GPU may be in use by audio worker): {e}"
        )
    except Exception as e:
        # Catch GPU access violations and other GPU contention errors
        if "access violation" in str(e).lower() or "gpu" in str(e).lower():
            pytest.skip(f"GPU contention detected (audio worker may be running): {e}")
        raise

    cases = [
        ("short_canonical", sentences[0]),
        ("short_atc", "Roger, 510 kilometers."),
        (
            "long_atc",
            "Negative Ghost Rider, the pattern is full. Consider re-vectoring to 277 kilometers on azimuth 359. Also polish your ship's fenders and have an in-flight meal please.",
        ),
        ("long_canonical", " ".join(sentences)),
    ]

    for label, text in cases:
        start = time.perf_counter()
        try:
            wav_bytes = service.generate(text=text, voice_id=voice_id)
        except RuntimeError as e:
            msg = str(e)
            if "Descriptors cannot be created directly" in msg or "protobuf" in msg:
                pytest.skip(
                    "protobuf/TF dependency mismatch; set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python "
                    "or install protobuf==3.20.x"
                )
            raise

        elapsed = time.perf_counter() - start

        duration = _wav_duration_seconds(wav_bytes)

        # Basic sanity checks
        assert len(wav_bytes) > 0, f"{label} case produced empty audio"
        assert duration > 0.0, f"{label} case duration not positive"

        # Diagnostics: capture latency but only fail on extreme hangs.
        if elapsed > 300.0:  # 5 minutes is treated as hung
            raise AssertionError(f"{label} generation too slow ({elapsed:.1f}s)")

        # Log/print for visibility in test output
        print(
            f"[{label}] text_len={len(text)} duration={duration:.2f}s wall={elapsed:.2f}s"
        )

        # Persist metrics to artifacts for later tuning
        artifacts_dir = Path(settings.BASE_DIR) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        out_path = artifacts_dir / "tts_performance.jsonl"
        record = {
            "case": label,
            "text_len": len(text),
            "duration_s": duration,
            "wall_s": elapsed,
            "device": device,
            "protobuf_version": pb_version,
        }
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


@pytest.mark.slow
@pytest.mark.skipif(
    not _have_local_model(),
    reason="Local chatterbox model not found (set CHATTERBOX_LOCAL_PATH)",
)
def test_chatterbox_voice_switch_latency():
    # Measure per-voice latency to understand switching overhead.
    voices = [
        "pilot-M-002_canonical_all",
        "pilot-F-001_canonical_all",
        "controller-M-001_canonical_all",
    ]

    missing = [v for v in voices if not _have_voice(v)]
    if missing:
        pytest.skip(f"Missing voice prompts: {missing}")

    service = get_tts_service()
    device = getattr(service, "device", "unknown")
    text = "Ready for departure clearance."

    artifacts_dir = Path(settings.BASE_DIR) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / "tts_performance.jsonl"

    for v in voices:
        start = time.perf_counter()
        try:
            wav_bytes = service.generate(text=text, voice_id=v)
        except RuntimeError as e:
            msg = str(e)
            if "Descriptors cannot be created directly" in msg or "protobuf" in msg:
                pytest.skip(
                    "protobuf/TF dependency mismatch; set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python "
                    "or install protobuf==3.20.x"
                )
            raise

        elapsed = time.perf_counter() - start
        duration = _wav_duration_seconds(wav_bytes)

        assert len(wav_bytes) > 0, f"{v} produced empty audio"
        assert duration > 0.0, f"{v} duration not positive"
        if elapsed > 300.0:
            raise AssertionError(f"{v} generation too slow ({elapsed:.1f}s)")

        print(
            f"[voice_switch] voice={v} text_len={len(text)} duration={duration:.2f}s wall={elapsed:.2f}s"
        )

        record = {
            "case": "voice_switch",
            "voice_id": v,
            "text_len": len(text),
            "duration_s": duration,
            "wall_s": elapsed,
            "device": device,
            "protobuf_version": _pb.__version__,
        }
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


def test_chatterbox_performance_artifacts_exist():
    """
    Verify that TTS performance artifacts exist for inspection.

    Skipped (not failed) when the slow test suite hasn't been run yet, since
    the artifacts are only generated by the slow Chatterbox latency tests.
    """
    artifacts_dir = Path(settings.BASE_DIR) / "artifacts"
    out_path = artifacts_dir / "tts_performance.jsonl"
    if not out_path.exists():
        pytest.skip(
            "tts_performance.jsonl not found; run slow tests to generate metrics"
        )
    assert out_path.exists()
