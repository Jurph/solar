"""
Tests for audio_synth.py — pure-Python audio synthesis primitives.

Covers guard branches, error paths, and happy paths for all component types.
Synthetic WAV files are created in-memory or via tempfile where disk access
is needed; no real audio assets required.
"""

from __future__ import annotations

import math
import struct
import tempfile
import wave

import pytest

from mysite.universe.services.audio_synth import (
    Echo,
    LoopedAudioFragment,
    ModemNoise,
    SineBeep,
    WavFileClip,
    WhiteNoise,
    _apply_echo,
    _compute_total_duration,
    _exp_envelope,
    _get_wav_duration_seconds,
    _mix_looped_audio_fragment,
    _mix_modem_noise,
    _mix_sine_beep,
    _mix_wav_file_clip,
    _mix_white_noise,
    _read_wav_mono_float,
    _resample_linear,
    render_wav_bytes,
)


def _write_mono_wav(path: str, *, sr: int = 48000, frames: int = 480) -> None:
    """Write a minimal mono 16-bit WAV to *path*."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * frames)


def _write_stereo_wav(path: str, *, sr: int = 48000, frames: int = 480) -> None:
    """Write a minimal stereo 16-bit WAV to *path*."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        # Two channels interleaved: L=1000, R=-1000 so downmix ≈ 0
        pair = struct.pack("<hh", 1000, -1000)
        wf.writeframes(pair * frames)


# ---------------------------------------------------------------------------
# _exp_envelope
# ---------------------------------------------------------------------------


class TestExpEnvelope:
    def test_zero_duration_returns_zero(self):
        assert _exp_envelope(0.0, duration=0.0, attack=0.01, release=0.01) == 0.0

    def test_negative_duration_returns_zero(self):
        assert _exp_envelope(0.0, duration=-1.0, attack=0.01, release=0.01) == 0.0

    def test_t_before_start_returns_zero(self):
        assert _exp_envelope(-0.1, duration=1.0, attack=0.01, release=0.01) == 0.0

    def test_t_after_end_returns_zero(self):
        assert _exp_envelope(1.5, duration=1.0, attack=0.01, release=0.01) == 0.0

    def test_sustain_region_returns_one(self):
        """Mid-duration with short attack/release should be at full amplitude."""
        assert _exp_envelope(0.5, duration=1.0, attack=0.01, release=0.01) == 1.0


# ---------------------------------------------------------------------------
# render_wav_bytes — validation
# ---------------------------------------------------------------------------


class TestRenderWavBytesValidation:
    def test_bad_pcm_bits_raises(self):
        with pytest.raises(ValueError, match="16-bit"):
            render_wav_bytes([], pcm_bits=8)

    def test_zero_sample_rate_raises(self):
        with pytest.raises(ValueError, match="positive"):
            render_wav_bytes([], sample_rate_hz=0)

    def test_negative_sample_rate_raises(self):
        with pytest.raises(ValueError, match="positive"):
            render_wav_bytes([], sample_rate_hz=-44100)

    def test_unsupported_component_type_raises(self):
        with pytest.raises(TypeError, match="Unsupported"):
            render_wav_bytes(["not_a_component"])  # type: ignore[list-item]

    def test_empty_components_returns_valid_wav(self):
        """Empty component list still produces a valid (silent) WAV."""
        wav = render_wav_bytes([])
        assert wav[:4] == b"RIFF"
        assert b"WAVE" in wav[:64]


# ---------------------------------------------------------------------------
# _mix_sine_beep
# ---------------------------------------------------------------------------


class TestMixSineBeep:
    def test_zero_duration_is_noop(self):
        mix = [0.0] * 100
        _mix_sine_beep(mix, SineBeep(duration_seconds=0.0), 48000)
        assert all(s == 0.0 for s in mix)

    def test_negative_duration_is_noop(self):
        mix = [0.0] * 100
        _mix_sine_beep(mix, SineBeep(duration_seconds=-1.0), 48000)
        assert all(s == 0.0 for s in mix)


# ---------------------------------------------------------------------------
# _mix_white_noise
# ---------------------------------------------------------------------------


class TestMixWhiteNoise:
    def test_zero_duration_is_noop(self):
        mix = [0.0] * 100
        _mix_white_noise(mix, WhiteNoise(duration_seconds=0.0), 48000)
        assert all(s == 0.0 for s in mix)

    def test_bandwidth_hz_both_filters(self):
        """bandwidth_hz with both lowpass and highpass set uses their average as center."""
        mix = [0.0] * 4800
        noise = WhiteNoise(
            duration_seconds=0.1,
            bandwidth_hz=500.0,
            lowpass_hz=3000.0,
            highpass_hz=1000.0,
        )
        _mix_white_noise(mix, noise, 48000)
        assert any(s != 0.0 for s in mix)

    def test_bandwidth_hz_only_lowpass(self):
        mix = [0.0] * 4800
        noise = WhiteNoise(
            duration_seconds=0.1,
            bandwidth_hz=500.0,
            lowpass_hz=3000.0,
            highpass_hz=None,
        )
        _mix_white_noise(mix, noise, 48000)
        assert any(s != 0.0 for s in mix)

    def test_bandwidth_hz_only_highpass(self):
        mix = [0.0] * 4800
        noise = WhiteNoise(
            duration_seconds=0.1,
            bandwidth_hz=500.0,
            lowpass_hz=None,
            highpass_hz=1000.0,
        )
        _mix_white_noise(mix, noise, 48000)
        assert any(s != 0.0 for s in mix)

    def test_bandwidth_hz_neither_filter(self):
        """bandwidth_hz set but no lowpass/highpass → default center of 2000 Hz."""
        mix = [0.0] * 4800
        noise = WhiteNoise(
            duration_seconds=0.1,
            bandwidth_hz=500.0,
            lowpass_hz=None,
            highpass_hz=None,
        )
        _mix_white_noise(mix, noise, 48000)
        assert any(s != 0.0 for s in mix)


# ---------------------------------------------------------------------------
# _mix_modem_noise
# ---------------------------------------------------------------------------


class TestMixModemNoise:
    def test_empty_text_is_noop(self):
        mix = [0.0] * 100
        _mix_modem_noise(mix, ModemNoise(text=""), 48000)
        assert all(s == 0.0 for s in mix)

    def test_wow_warble_modifies_output(self):
        """Non-zero wow_rate_hz and wow_depth_hz apply FM warble to the tones."""
        mix_plain = [0.0] * 48000
        _mix_modem_noise(
            mix_plain, ModemNoise(text="A", wow_rate_hz=0.0, wow_depth_hz=0.0), 48000
        )
        mix_warble = [0.0] * 48000
        _mix_modem_noise(
            mix_warble, ModemNoise(text="A", wow_rate_hz=2.0, wow_depth_hz=50.0), 48000
        )
        # Both should have audio, but the samples should differ due to FM
        assert any(s != 0.0 for s in mix_plain)
        assert any(s != 0.0 for s in mix_warble)
        assert mix_plain != mix_warble


# ---------------------------------------------------------------------------
# _apply_echo
# ---------------------------------------------------------------------------


class TestApplyEcho:
    def test_zero_delay_is_noop(self):
        mix = [1.0] * 100
        original = mix[:]
        _apply_echo(mix, Echo(delay_ms=0.0, decay=0.5, wet=0.5), 48000)
        assert mix == original

    def test_zero_wet_is_noop(self):
        mix = [1.0] * 100
        original = mix[:]
        _apply_echo(mix, Echo(delay_ms=10.0, decay=0.5, wet=0.0), 48000)
        assert mix == original

    def test_zero_decay_is_noop(self):
        mix = [1.0] * 100
        original = mix[:]
        _apply_echo(mix, Echo(delay_ms=10.0, decay=0.0, wet=0.5), 48000)
        assert mix == original

    def test_delay_exceeds_mix_length_is_noop(self):
        """When delay_samples >= len(mix), echo has nowhere to write."""
        mix = [1.0] * 10
        original = mix[:]
        # 1000ms delay at 48kHz = 48000 samples, but mix is only 10 samples
        _apply_echo(mix, Echo(delay_ms=1000.0, decay=0.5, wet=0.5), 48000)
        assert mix == original


# ---------------------------------------------------------------------------
# _get_wav_duration_seconds
# ---------------------------------------------------------------------------


class TestGetWavDurationSeconds:
    def test_empty_path_returns_zero(self):
        assert _get_wav_duration_seconds("") == 0.0

    def test_nonexistent_path_returns_zero(self):
        assert _get_wav_duration_seconds("/no/such/file.wav") == 0.0

    def test_valid_wav_returns_correct_duration(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            _write_mono_wav(f.name, sr=48000, frames=48000)
            dur = _get_wav_duration_seconds(f.name)
        assert abs(dur - 1.0) < 0.001


# ---------------------------------------------------------------------------
# _compute_total_duration
# ---------------------------------------------------------------------------


class TestComputeTotalDuration:
    def test_modem_empty_text_contributes_zero(self):
        dur = _compute_total_duration([ModemNoise(text="")])
        assert dur == 0.0

    def test_looped_fragment_with_explicit_duration(self):
        dur = _compute_total_duration([LoopedAudioFragment(loop_duration_seconds=5.0)])
        assert abs(dur - 5.0) < 0.001

    def test_looped_fragment_zero_duration_contributes_zero(self):
        """loop_duration_seconds=0 means 'loop for full mix' — contributes 0 to total."""
        dur = _compute_total_duration([LoopedAudioFragment(loop_duration_seconds=0.0)])
        assert dur == 0.0


# ---------------------------------------------------------------------------
# _read_wav_mono_float
# ---------------------------------------------------------------------------


class TestReadWavMonoFloat:
    def test_mono_wav_reads_correctly(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            _write_mono_wav(f.name, sr=48000, frames=480)
            sr, samples = _read_wav_mono_float(f.name)
        assert sr == 48000
        assert len(samples) == 480

    def test_stereo_wav_downmixes(self):
        """Stereo WAV is averaged to mono. L=1000, R=-1000 → ≈ 0."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            _write_stereo_wav(f.name, sr=48000, frames=100)
            sr, samples = _read_wav_mono_float(f.name)
        assert sr == 48000
        assert len(samples) == 100
        # Each sample should be near zero (1000 + -1000) / 2 / 32768
        assert all(abs(s) < 0.01 for s in samples)

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            _read_wav_mono_float("/no/such/file.wav")


# ---------------------------------------------------------------------------
# _resample_linear
# ---------------------------------------------------------------------------


class TestResampleLinear:
    def test_same_rate_returns_input(self):
        samples = [0.1, 0.2, 0.3]
        result = _resample_linear(samples, 48000, 48000)
        assert result is samples  # identity, not a copy

    def test_empty_returns_input(self):
        result = _resample_linear([], 44100, 48000)
        assert result == []

    def test_invalid_src_rate_returns_input(self):
        samples = [0.1, 0.2]
        result = _resample_linear(samples, 0, 48000)
        assert result is samples

    def test_invalid_dst_rate_returns_input(self):
        samples = [0.1, 0.2]
        result = _resample_linear(samples, 48000, 0)
        assert result is samples

    def test_upsample_increases_length(self):
        samples = [0.0, 1.0, 0.0]
        result = _resample_linear(samples, 24000, 48000)
        assert len(result) > len(samples)

    def test_downsample_decreases_length(self):
        samples = [float(i) for i in range(100)]
        result = _resample_linear(samples, 48000, 24000)
        assert len(result) < len(samples)


# ---------------------------------------------------------------------------
# _mix_wav_file_clip
# ---------------------------------------------------------------------------


class TestMixWavFileClip:
    def test_empty_path_is_noop(self):
        mix = [0.0] * 100
        _mix_wav_file_clip(mix, WavFileClip(path=""), 48000)
        assert all(s == 0.0 for s in mix)

    def test_bad_path_raises_with_context(self):
        """Non-existent file re-raises as ValueError with path in message."""
        mix = [0.0] * 100
        with pytest.raises(ValueError, match="Failed to read WAV"):
            _mix_wav_file_clip(mix, WavFileClip(path="/no/such/file.wav"), 48000)

    def test_valid_mono_wav_mixes_into_buffer(self):
        """A WAV with non-silent content should modify the mix buffer."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Write a WAV with audible content (not silence)
            with wave.open(f.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                # Write a short tone: 480 samples of a 1kHz sine
                pcm = b""
                for i in range(480):
                    val = int(16000 * math.sin(2.0 * math.pi * 1000.0 * i / 48000.0))
                    pcm += struct.pack("<h", val)
                wf.writeframes(pcm)

            mix = [0.0] * 960
            _mix_wav_file_clip(mix, WavFileClip(path=f.name, gain=1.0), 48000)
        assert any(s != 0.0 for s in mix)


# ---------------------------------------------------------------------------
# _mix_looped_audio_fragment
# ---------------------------------------------------------------------------


class TestMixLoopedAudioFragment:
    def test_empty_path_is_noop(self):
        mix = [0.0] * 100
        _mix_looped_audio_fragment(mix, LoopedAudioFragment(path=""), 48000)
        assert all(s == 0.0 for s in mix)

    def test_bad_path_is_silent_skip(self):
        """Bad path degrades gracefully — no exception, no audio."""
        mix = [0.0] * 100
        _mix_looped_audio_fragment(
            mix, LoopedAudioFragment(path="/no/such/file.wav"), 48000
        )
        assert all(s == 0.0 for s in mix)

    def test_loops_for_full_mix_when_duration_zero(self):
        """loop_duration_seconds=0 means loop for the entire mix buffer."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # 48 samples of non-silence at 48kHz = 1ms of audio
            with wave.open(f.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                pcm = struct.pack("<" + "h" * 48, *([10000] * 48))
                wf.writeframes(pcm)

            # Mix buffer is 480 samples = 10x the loop source
            mix = [0.0] * 480
            frag = LoopedAudioFragment(path=f.name, gain=1.0, loop_duration_seconds=0.0)
            _mix_looped_audio_fragment(mix, frag, 48000)

        # The short fragment should have been looped to fill the entire buffer
        assert all(s != 0.0 for s in mix)

    def test_loops_for_explicit_duration(self):
        """loop_duration_seconds > 0 limits how far the loop extends."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            with wave.open(f.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                pcm = struct.pack("<" + "h" * 48, *([10000] * 48))
                wf.writeframes(pcm)

            # 0.005s = 240 samples at 48kHz; buffer is 480
            mix = [0.0] * 480
            frag = LoopedAudioFragment(
                path=f.name, gain=1.0, loop_duration_seconds=0.005
            )
            _mix_looped_audio_fragment(mix, frag, 48000)

        # First 240 samples should have audio, rest should be silent
        assert any(s != 0.0 for s in mix[:240])
        assert all(s == 0.0 for s in mix[240:])
