from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace


_CONFTEST_PATH = Path(__file__).with_name("conftest.py")
_SPEC = importlib.util.spec_from_file_location("solar_tests_conftest", _CONFTEST_PATH)
assert _SPEC and _SPEC.loader
solar_conftest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(solar_conftest)


class _FakeCuda:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def mem_get_info(_device):
        free_mb = 11_240
        total_mb = 12_287
        return free_mb * 1024 * 1024, total_mb * 1024 * 1024

    @staticmethod
    def get_device_properties(_device):
        return SimpleNamespace(name="NVIDIA GeForce RTX 3060")


class _FakeTorch:
    cuda = _FakeCuda()


def test_vram_baseline_logging_is_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SOLAR_LOG_VRAM_BASELINE", raising=False)
    monkeypatch.setitem(sys.modules, "torch", _FakeTorch())

    solar_conftest._log_vram_baseline.__wrapped__()

    assert not (tmp_path / "artifacts" / "vram_baseline.json").exists()


def test_vram_baseline_logging_can_be_enabled_explicitly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SOLAR_LOG_VRAM_BASELINE", "1")
    monkeypatch.setitem(sys.modules, "torch", _FakeTorch())

    solar_conftest._log_vram_baseline.__wrapped__()

    output_path = tmp_path / "artifacts" / "vram_baseline.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["gpu_name"] == "NVIDIA GeForce RTX 3060"
    assert data["free_mb"] == 11_240
