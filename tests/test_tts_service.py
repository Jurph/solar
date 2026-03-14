"""
Mock-based tests for ChatterboxTTSService in tts_service.py.

Covers without GPU/model files:
- _generate_silence(): valid WAV output
- _get_cache_key(): determinism and uniqueness
- _wav_to_bytes(): mono conversion, resampling
- _get_voice_path(): fallback chain (pilot prefix, controller prefix, generic)
- generate(): cache hit, model load failure, voice not found, exception→raises RuntimeError
- get_tts_service(): singleton pattern
- warm_tts_service(): swallows errors
"""

import io
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip this entire file gracefully when torch is not installed (e.g. in CI,
# which installs the base + dev dependency sets but not the optional ML extras).
# Tests here
# are mock-based and need no GPU, but tts_service.py imports torch at module
# level so torch must at least be importable.
torch = pytest.importorskip("torch")

from mysite.universe.services.tts_service import (  # noqa: E402  # torch guard above
    ChatterboxTTSService,
    get_tts_service,
    warm_tts_service,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _parse_wav(wav_bytes: bytes) -> wave.Wave_read:
    return wave.open(io.BytesIO(wav_bytes))


# ---------------------------------------------------------------------------
# _generate_silence()
# ---------------------------------------------------------------------------


class TestGenerateSilence:
    """_generate_silence() returns valid WAV bytes without touching the model."""

    def setup_method(self):
        self.svc = ChatterboxTTSService(device="cpu")

    def test_returns_bytes(self):
        assert isinstance(self.svc._generate_silence(0.1), bytes)

    def test_valid_wav_header_mono_16bit_48k(self):
        wf = _parse_wav(self.svc._generate_silence(0.1))
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48000

    def test_one_second_has_48000_frames(self):
        wf = _parse_wav(self.svc._generate_silence(1.0))
        assert wf.getnframes() == 48000

    def test_half_second_has_24000_frames(self):
        wf = _parse_wav(self.svc._generate_silence(0.5))
        assert wf.getnframes() == 24000


# ---------------------------------------------------------------------------
# _get_cache_key()
# ---------------------------------------------------------------------------


class TestGetCacheKey:
    """_get_cache_key() is deterministic and input-sensitive."""

    def setup_method(self):
        self.svc = ChatterboxTTSService(device="cpu")

    def test_returns_string_with_tts_prefix(self):
        key = self.svc._get_cache_key("hello", "pilot_default", 0.5, 0.5)
        assert isinstance(key, str)
        assert key.startswith("tts:")

    def test_same_inputs_same_key(self):
        k1 = self.svc._get_cache_key("hello", "pilot_default", 0.5, 0.5)
        k2 = self.svc._get_cache_key("hello", "pilot_default", 0.5, 0.5)
        assert k1 == k2

    def test_different_text_different_key(self):
        k1 = self.svc._get_cache_key("hello", "pilot_default", 0.5, 0.5)
        k2 = self.svc._get_cache_key("goodbye", "pilot_default", 0.5, 0.5)
        assert k1 != k2

    def test_different_voice_different_key(self):
        k1 = self.svc._get_cache_key("hello", "pilot_default", 0.5, 0.5)
        k2 = self.svc._get_cache_key("hello", "controller_default", 0.5, 0.5)
        assert k1 != k2

    def test_different_cfg_weight_different_key(self):
        k1 = self.svc._get_cache_key("hello", "pilot_default", 0.3, 0.5)
        k2 = self.svc._get_cache_key("hello", "pilot_default", 0.7, 0.5)
        assert k1 != k2


# ---------------------------------------------------------------------------
# _wav_to_bytes()
# ---------------------------------------------------------------------------


class TestWavToBytes:
    """_wav_to_bytes() converts PyTorch tensors to valid WAV bytes."""

    def setup_method(self):
        self.svc = ChatterboxTTSService(device="cpu")

    def test_1d_tensor_produces_valid_wav(self):
        tensor = torch.zeros(4800)  # 0.1 sec at 48 kHz
        wav_bytes = self.svc._wav_to_bytes(tensor, 48000)
        wf = _parse_wav(wav_bytes)
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48000

    def test_2d_stereo_tensor_averaged_to_mono(self):
        tensor = torch.zeros(2, 4800)  # Stereo
        wav_bytes = self.svc._wav_to_bytes(tensor, 48000)
        wf = _parse_wav(wav_bytes)
        assert wf.getnchannels() == 1

    def test_resampling_changes_sample_rate_to_48k(self):
        tensor = torch.zeros(2400)  # 0.1 sec at 24 kHz
        wav_bytes = self.svc._wav_to_bytes(tensor, 24000)
        wf = _parse_wav(wav_bytes)
        assert wf.getframerate() == 48000

    def test_clipping_does_not_crash(self):
        """Values outside [-1, 1] are clamped, not erroring."""
        tensor = torch.tensor([2.0, -2.0, 0.5])
        wav_bytes = self.svc._wav_to_bytes(tensor, 48000)
        assert isinstance(wav_bytes, bytes)


# ---------------------------------------------------------------------------
# _get_voice_path()
# ---------------------------------------------------------------------------


class TestGetVoicePath:
    """_get_voice_path() fallback chain without touching the filesystem."""

    def setup_method(self):
        self.svc = ChatterboxTTSService(device="cpu")

    def test_custom_voice_returned_directly(self):
        custom = Path("/fake/my_voice.wav")
        with patch.object(
            self.svc,
            "_find_voice_file",
            side_effect=lambda v: custom if v == "my_voice" else None,
        ):
            assert self.svc._get_voice_path("my_voice") == custom

    def test_pilot_prefix_falls_back_to_pilot_default(self):
        pilot_default = Path("/fake/pilot_default.wav")

        def find_voice(v):
            return pilot_default if v == "pilot_default" else None

        with patch.object(self.svc, "_find_voice_file", side_effect=find_voice):
            result = self.svc._get_voice_path("pilot-M-999_unknown")
        assert result == pilot_default

    def test_controller_prefix_falls_back_to_controller_default(self):
        ctrl_default = Path("/fake/controller_default.wav")

        def find_voice(v):
            return ctrl_default if v == "controller_default" else None

        with patch.object(self.svc, "_find_voice_file", side_effect=find_voice):
            result = self.svc._get_voice_path("controller-F-001_unknown")
        assert result == ctrl_default

    def test_unknown_voice_falls_back_to_generic_pilot_default(self):
        """Completely unknown voice uses first available generic default."""
        pilot_default = Path("/fake/pilot_default.wav")

        def find_voice(v):
            return pilot_default if v == "pilot_default" else None

        with patch.object(self.svc, "_find_voice_file", side_effect=find_voice):
            result = self.svc._get_voice_path("completely_unknown_voice")
        assert result == pilot_default

    def test_returns_none_when_no_defaults_exist(self):
        with patch.object(self.svc, "_find_voice_file", return_value=None):
            assert self.svc._get_voice_path("nonexistent_voice") is None


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


class TestGenerate:
    """generate() branches: cache hit, model failure, no voice, exception→silence."""

    def setup_method(self):
        self.svc = ChatterboxTTSService(device="cpu")

    def test_cache_hit_returns_cached_bytes_without_model(self):
        cached = b"fake_wav"
        with patch("mysite.universe.services.tts_service.cache") as mock_cache:
            mock_cache.get.return_value = cached
            result = self.svc.generate("hello", "pilot_default")
        assert result == cached

    def test_model_load_failure_raises_runtime_error(self):
        with patch("mysite.universe.services.tts_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch.object(
                self.svc, "_load_model", side_effect=Exception("GPU OOM")
            ):
                with pytest.raises(RuntimeError, match="Failed to load TTS model"):
                    self.svc.generate("hello", "pilot_default")

    def test_voice_not_found_raises_value_error(self):
        # Pre-set model so _load_model short-circuits
        self.svc.model = MagicMock()
        with patch("mysite.universe.services.tts_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch.object(self.svc, "_get_voice_path", return_value=None):
                with pytest.raises(ValueError, match="Voice clip not found"):
                    self.svc.generate("hello", "ghost_voice")

    def test_model_generation_exception_raises(self):
        """Model failure must raise RuntimeError so callers know to retry (no silent silence)."""
        fake_path = Path("/fake/pilot_default.wav")
        mock_model = MagicMock()
        mock_model.generate.side_effect = RuntimeError("CUDA error")
        # Pre-set model so _load_model short-circuits
        self.svc.model = mock_model

        with patch("mysite.universe.services.tts_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch.object(self.svc, "_get_voice_path", return_value=fake_path):
                with pytest.raises(RuntimeError, match="TTS generation failed"):
                    self.svc.generate("hello", "pilot_default")

    def test_successful_generation_sets_cache(self):
        fake_path = Path("/fake/pilot_default.wav")
        mock_model = MagicMock()
        # Return a 1D tensor of zeros as "generated" audio
        mock_model.generate.return_value = torch.zeros(4800)
        mock_model.sr = 48000
        self.svc.model = mock_model

        with patch("mysite.universe.services.tts_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch.object(self.svc, "_get_voice_path", return_value=fake_path):
                result = self.svc.generate("hello", "pilot_default")

        assert isinstance(result, bytes)
        mock_cache.set.assert_called_once()


# ---------------------------------------------------------------------------
# get_tts_service() singleton
# ---------------------------------------------------------------------------


class TestGetTTSServiceSingleton:
    """get_tts_service() returns the same instance on repeated calls."""

    def test_same_instance_returned_twice(self):
        import mysite.universe.services.tts_service as tts_module

        original = tts_module._tts_service
        try:
            tts_module._tts_service = None
            svc1 = get_tts_service()
            svc2 = get_tts_service()
            assert svc1 is svc2
        finally:
            tts_module._tts_service = original

    def test_returns_chatterbox_instance(self):
        import mysite.universe.services.tts_service as tts_module

        original = tts_module._tts_service
        try:
            tts_module._tts_service = None
            svc = get_tts_service()
            assert isinstance(svc, ChatterboxTTSService)
        finally:
            tts_module._tts_service = original


# ---------------------------------------------------------------------------
# warm_tts_service()
# ---------------------------------------------------------------------------


class TestWarmTTSService:
    """warm_tts_service() is best-effort and never raises."""

    def test_failure_is_swallowed(self):
        import mysite.universe.services.tts_service as tts_module

        original = tts_module._tts_service
        try:
            mock_svc = MagicMock()
            mock_svc.generate.side_effect = RuntimeError("no GPU")
            tts_module._tts_service = mock_svc
            warm_tts_service()  # Must not raise
        finally:
            tts_module._tts_service = original

    def test_calls_generate_with_defaults(self):
        import mysite.universe.services.tts_service as tts_module

        original = tts_module._tts_service
        try:
            mock_svc = MagicMock()
            mock_svc.generate.return_value = b"ok"
            tts_module._tts_service = mock_svc
            warm_tts_service()
            mock_svc.generate.assert_called_once_with(
                text="check", voice_id="pilot_default"
            )
        finally:
            tts_module._tts_service = original
