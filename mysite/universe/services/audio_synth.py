"""
Audio synthesis helpers (pure Python).

This module is intentionally "left" in the system: Python defines audio clips,
renders them into a single waveform (WAV bytes), and the browser only plays
the resulting waveform.

Current primitives:
- sine_beep: basic oscillator tone with envelope
- white_noise: noise source with optional simple filtering + envelope
"""

from __future__ import annotations

import io
import math
import random
import wave
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _exp_envelope(
    t: float, *, duration: float, attack: float, release: float
) -> float:
    """
    Smooth amplitude envelope in [0..1] that avoids clicks.

    Uses an exponential-ish curve by squaring a linear ramp.
    """
    if duration <= 0:
        return 0.0
    if t < 0 or t > duration:
        return 0.0

    a = max(0.0, min(attack, duration))
    r = max(0.0, min(release, duration))

    if a > 0 and t < a:
        x = t / a
        return x * x

    if r > 0 and t > duration - r:
        x = (duration - t) / r
        return x * x

    return 1.0


@dataclass(frozen=True)
class SineBeep:
    start_seconds: float = 0.0
    duration_seconds: float = 0.25
    frequency_hz: float = 440.0
    gain: float = 1.0
    attack_seconds: float = 0.005
    release_seconds: float = 0.02


@dataclass(frozen=True)
class WhiteNoise:
    start_seconds: float = 0.0
    duration_seconds: float = 0.25
    gain: float = 1.0
    attack_seconds: float = 0.001
    release_seconds: float = 0.02
    # Optional simple filters. If both are set, it approximates a band-pass.
    lowpass_hz: Optional[float] = None
    highpass_hz: Optional[float] = None


AudioComponent = SineBeep | WhiteNoise


def render_wav_bytes(
    components: Sequence[AudioComponent],
    *,
    sample_rate_hz: int = 48_000,
    pcm_bits: int = 16,
) -> bytes:
    """
    Render a list of components mixed into a single mono WAV.
    """
    if pcm_bits != 16:
        raise ValueError("Only 16-bit PCM output is currently supported.")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive.")

    duration = _compute_total_duration(components)
    # Ensure we return a valid WAV even for extremely short durations.
    duration = max(0.001, duration)
    total_frames = int(math.ceil(duration * sample_rate_hz))

    mix: list[float] = [0.0] * total_frames

    for comp in components:
        if isinstance(comp, SineBeep):
            _mix_sine_beep(mix, comp, sample_rate_hz)
        elif isinstance(comp, WhiteNoise):
            _mix_white_noise(mix, comp, sample_rate_hz)
        else:
            raise TypeError(f"Unsupported component type: {type(comp)!r}")

    # Hard clamp to [-1, 1]. (Future: soft limiter.)
    for i in range(total_frames):
        mix[i] = _clamp(mix[i], -1.0, 1.0)

    pcm = _float_to_int16_le_bytes(mix)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate_hz)
        wf.writeframes(pcm)
    return buf.getvalue()


def _compute_total_duration(components: Iterable[AudioComponent]) -> float:
    end = 0.0
    for c in components:
        start = float(getattr(c, "start_seconds", 0.0) or 0.0)
        dur = float(getattr(c, "duration_seconds", 0.0) or 0.0)
        end = max(end, max(0.0, start) + max(0.0, dur))
    return end


def _mix_sine_beep(mix: list[float], beep: SineBeep, sr: int) -> None:
    start = max(0.0, beep.start_seconds)
    dur = max(0.0, beep.duration_seconds)
    if dur <= 0:
        return

    freq = max(1.0, beep.frequency_hz)
    gain = max(0.0, beep.gain)
    a = max(0.0, beep.attack_seconds)
    r = max(0.0, beep.release_seconds)

    start_i = int(start * sr)
    frame_count = int(math.ceil(dur * sr))
    end_i = min(len(mix), start_i + frame_count)

    for i in range(start_i, end_i):
        t = (i - start_i) / sr
        env = _exp_envelope(t, duration=dur, attack=a, release=r)
        s = math.sin(2.0 * math.pi * freq * t) * gain * env
        mix[i] += s


def _mix_white_noise(mix: list[float], noise: WhiteNoise, sr: int) -> None:
    start = max(0.0, noise.start_seconds)
    dur = max(0.0, noise.duration_seconds)
    if dur <= 0:
        return

    gain = max(0.0, noise.gain)
    a = max(0.0, noise.attack_seconds)
    r = max(0.0, noise.release_seconds)

    start_i = int(start * sr)
    frame_count = int(math.ceil(dur * sr))
    end_i = min(len(mix), start_i + frame_count)

    # Generate raw noise first.
    samples: list[float] = [random.uniform(-1.0, 1.0) for _ in range(end_i - start_i)]

    # Apply simple filters if requested.
    if noise.lowpass_hz is not None:
        samples = _one_pole_lowpass(samples, sr, max(1.0, float(noise.lowpass_hz)))
    if noise.highpass_hz is not None:
        samples = _one_pole_highpass(samples, sr, max(1.0, float(noise.highpass_hz)))

    for local_i, i in enumerate(range(start_i, end_i)):
        t = local_i / sr
        env = _exp_envelope(t, duration=dur, attack=a, release=r)
        mix[i] += samples[local_i] * gain * env


def _one_pole_lowpass(x: list[float], sr: int, cutoff_hz: float) -> list[float]:
    # RC low-pass: y[n] = y[n-1] + alpha * (x[n] - y[n-1])
    dt = 1.0 / sr
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    alpha = dt / (rc + dt)
    y: list[float] = []
    prev = 0.0
    for s in x:
        prev = prev + alpha * (s - prev)
        y.append(prev)
    return y


def _one_pole_highpass(x: list[float], sr: int, cutoff_hz: float) -> list[float]:
    # RC high-pass: y[n] = alpha * (y[n-1] + x[n] - x[n-1])
    dt = 1.0 / sr
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    alpha = rc / (rc + dt)
    y: list[float] = []
    prev_y = 0.0
    prev_x = 0.0
    for s in x:
        prev_y = alpha * (prev_y + s - prev_x)
        prev_x = s
        y.append(prev_y)
    return y


def _float_to_int16_le_bytes(samples: Sequence[float]) -> bytes:
    # Manual pack to avoid extra dependencies.
    out = bytearray()
    for s in samples:
        v = int(round(_clamp(float(s), -1.0, 1.0) * 32767.0))
        if v < 0:
            v += 65536
        out.append(v & 0xFF)
        out.append((v >> 8) & 0xFF)
    return bytes(out)


