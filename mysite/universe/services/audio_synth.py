"""
Audio synthesis helpers (pure Python).

This module is intentionally "left" in the system: Python defines audio clips,
renders them into a single waveform (WAV bytes), and the browser only plays
the resulting waveform.

Current primitives:
- sine_beep: basic oscillator tone with envelope
- white_noise: noise source with optional simple filtering + envelope
- modem_noise: 1200-baud Kermit FSK encoding (text -> telephone modem tones)
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
    """
    White noise generator with configurable filtering.
    
    TODO: Room Tone Enhancement
    - Add engine_rumble component: low-frequency noise (20-200 Hz) with ship-size-based
      frequency profile (larger ships = lower rumble, more harmonics)
    - Add reverb/echo parameters: delay_ms, decay_factor, room_size_hint
      (larger cockpits = longer reverb tail, more diffuse reflections)
    - Ship size should drive: rumble frequency range, reverb decay time, overall gain
    - Consider a separate RoomTone component that mixes engine_rumble + filtered noise
      + reverb, rather than extending WhiteNoise (keeps concerns separated)
    """
    start_seconds: float = 0.0
    duration_seconds: float = 0.25
    gain: float = 1.0
    attack_seconds: float = 0.001
    release_seconds: float = 0.02
    # Optional simple filters. If both are set, it approximates a band-pass.
    lowpass_hz: Optional[float] = None
    highpass_hz: Optional[float] = None
    # Additional configurability for static-like noise
    intensity: float = 1.0  # Multiplier for noise amplitude (0.0 to 1.0+)
    bandwidth_hz: Optional[float] = None  # If set, applies bandpass around center frequency


@dataclass(frozen=True)
class ModemNoise:
    """
    1200-baud Kermit FSK modem encoding.
    
    Encodes text as Frequency Shift Keying (FSK) tones:
    - Mark (1): 1200 Hz
    - Space (0): 2200 Hz
    - Optional carrier tone at 1800 Hz (center frequency)
    
    Protocol: 7-bit ASCII, even parity, 1 start bit, 1 stop bit (10 bits/char).
    At 1200 baud: 120 characters/second, ~0.833ms per bit.
    """
    start_seconds: float = 0.0
    text: str = ""
    gain: float = 1.0
    baud_rate: int = 1200  # Bits per second
    mark_frequency_hz: float = 1200.0  # Frequency for bit=1
    space_frequency_hz: float = 2200.0  # Frequency for bit=0
    carrier_frequency_hz: Optional[float] = 1800.0  # Optional background carrier
    carrier_gain: float = 0.1  # Carrier amplitude relative to data tones
    attack_seconds: float = 0.01  # Modem handshake ramp-up
    release_seconds: float = 0.01  # Modem handshake ramp-down


AudioComponent = SineBeep | WhiteNoise | ModemNoise


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
        elif isinstance(comp, ModemNoise):
            _mix_modem_noise(mix, comp, sample_rate_hz)
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
        if isinstance(c, ModemNoise):
            # Calculate duration from text encoding
            if c.text:
                bits = _kermit_encode_text(c.text)
                bit_duration = 1.0 / float(c.baud_rate)
                dur = len(bits) * bit_duration + c.attack_seconds + c.release_seconds
            else:
                dur = 0.0
        else:
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

    gain = max(0.0, noise.gain) * max(0.0, noise.intensity)
    a = max(0.0, noise.attack_seconds)
    r = max(0.0, noise.release_seconds)

    start_i = int(start * sr)
    frame_count = int(math.ceil(dur * sr))
    end_i = min(len(mix), start_i + frame_count)

    # Generate raw noise first.
    samples: list[float] = [random.uniform(-1.0, 1.0) for _ in range(end_i - start_i)]

    # Apply bandwidth filter if specified (bandpass approximation).
    if noise.bandwidth_hz is not None:
        center = (noise.lowpass_hz or 2000.0) + (noise.highpass_hz or 0.0)
        if noise.lowpass_hz and noise.highpass_hz:
            center = (noise.lowpass_hz + noise.highpass_hz) / 2.0
        elif noise.lowpass_hz:
            center = noise.lowpass_hz
        elif noise.highpass_hz:
            center = noise.highpass_hz
        else:
            center = 2000.0  # Default center
        
        bw = max(1.0, float(noise.bandwidth_hz))
        low_cut = max(1.0, center - bw / 2.0)
        high_cut = center + bw / 2.0
        samples = _one_pole_lowpass(samples, sr, high_cut)
        samples = _one_pole_highpass(samples, sr, low_cut)
    else:
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


def _kermit_encode_text(text: str) -> list[int]:
    """
    Encode text as Kermit protocol bits (7-bit ASCII, even parity, start/stop).
    
    Returns a list of bits (0 or 1) ready for FSK modulation.
    """
    bits: list[int] = []
    for char in text:
        # Get 7-bit ASCII value
        ascii_val = ord(char) & 0x7F
        
        # Calculate even parity
        parity = 0
        for i in range(7):
            if (ascii_val >> i) & 1:
                parity ^= 1
        
        # Kermit frame: start bit (0), 7 data bits (LSB first), parity, stop bit (1)
        bits.append(0)  # Start bit
        for i in range(7):
            bits.append((ascii_val >> i) & 1)  # Data bits (LSB first)
        bits.append(parity)  # Even parity bit
        bits.append(1)  # Stop bit
    
    return bits


def _mix_modem_noise(mix: list[float], modem: ModemNoise, sr: int) -> None:
    """
    Render 1200-baud Kermit FSK modem tones.
    """
    if not modem.text:
        return
    
    # Encode text to bits
    bits = _kermit_encode_text(modem.text)
    if not bits:
        return
    
    # Calculate timing
    bit_duration = 1.0 / float(modem.baud_rate)
    total_duration = len(bits) * bit_duration
    total_duration += modem.attack_seconds + modem.release_seconds  # Add handshake time
    
    start = max(0.0, modem.start_seconds)
    start_i = int(start * sr)
    frame_count = int(math.ceil(total_duration * sr))
    end_i = min(len(mix), start_i + frame_count)
    
    # Mix carrier tone if requested (continuous background)
    if modem.carrier_frequency_hz is not None:
        carrier_freq = max(1.0, modem.carrier_frequency_hz)
        carrier_gain = max(0.0, modem.carrier_gain) * max(0.0, modem.gain)
        for i in range(start_i, end_i):
            t = (i - start_i) / sr
            if t < total_duration:
                mix[i] += math.sin(2.0 * math.pi * carrier_freq * t) * carrier_gain
    
    # Mix FSK data tones
    mark_freq = max(1.0, modem.mark_frequency_hz)
    space_freq = max(1.0, modem.space_frequency_hz)
    data_gain = max(0.0, modem.gain)
    a = max(0.0, modem.attack_seconds)
    r = max(0.0, modem.release_seconds)
    
    handshake_start = a
    handshake_end = total_duration - r
    
    for bit_idx, bit in enumerate(bits):
        bit_start_time = handshake_start + (bit_idx * bit_duration)
        bit_end_time = bit_start_time + bit_duration
        
        # Choose frequency based on bit value
        freq = mark_freq if bit == 1 else space_freq
        
        # Render this bit
        bit_start_i = int((start + bit_start_time) * sr)
        bit_end_i = min(end_i, int((start + bit_end_time) * sr))
        
        for i in range(bit_start_i, bit_end_i):
            t = (i - start_i) / sr
            if t < handshake_start or t > handshake_end:
                continue  # Outside data region
            
            # Envelope for this bit (smooth transitions)
            bit_local_t = t - bit_start_time
            if bit_local_t < 0 or bit_local_t > bit_duration:
                continue
            
            # Simple envelope per bit (avoid clicks)
            bit_env = 1.0
            if bit_local_t < 0.001:  # Quick attack per bit
                bit_env = bit_local_t / 0.001
            elif bit_local_t > bit_duration - 0.001:  # Quick release per bit
                bit_env = (bit_duration - bit_local_t) / 0.001
            
            # Overall handshake envelope
            overall_env = _exp_envelope(
                t - handshake_start,
                duration=handshake_end - handshake_start,
                attack=a,
                release=r,
            )
            
            phase = 2.0 * math.pi * freq * (t - bit_start_time)
            mix[i] += math.sin(phase) * data_gain * bit_env * overall_env


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


