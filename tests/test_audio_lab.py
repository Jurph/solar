from __future__ import annotations

import json
import io
import os
import tempfile
import wave
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse


class TestAudioLab(TestCase):
    def setUp(self):
        self.client = Client()

    def test_audio_lab_page_loads(self):
        resp = self.client.get(reverse("audio_lab"))
        assert resp.status_code == 200
        assert b"Audio Lab" in resp.content
        assert b"Show settings" in resp.content

    def test_audio_lab_render_modem_returns_wav(self):
        payload = {
            "mode": "modem",
            "text": "Sphinx of black quartz, judge my vow.",
            "include_quindar": True,
            "include_static": True,
            "mark_frequency_hz": 1300.0,
            "space_frequency_hz": 2100.0,
            "wow_rate_hz": 1.5,
            "wow_depth_hz": 30.0,
            "include_rumble": True,
            "include_echo": True,
            "echo_delay_ms": 110.0,
            "echo_decay": 0.35,
            "echo_wet": 0.2,
        }
        resp = self.client.post(
            reverse("audio_lab_render"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp["Content-Type"] == "audio/wav"
        assert resp.content.startswith(b"RIFF")
        assert b"WAVE" in resp.content[:64]

    def test_audio_lab_render_tts_preset_returns_wav(self):
        # Create a tiny deterministic WAV for the view to load.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            path = tf.name

        try:
            sr = 48_000
            frames = sr // 4  # 250ms
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(b"\x00\x00" * frames)  # silence

            payload = {
                "mode": "tts",
                "text": "Hello",  # ignored for now
                "tts_gain": 1.0,
                "include_quindar": True,
                "include_static": True,
                "include_rumble": True,
                "include_echo": True,
            }

            with patch("mysite.universe.views.audio.finders.find", return_value=path):
                resp = self.client.post(
                    reverse("audio_lab_render"),
                    data=json.dumps(payload),
                    content_type="application/json",
                )
            assert resp.status_code == 200
            assert resp["Content-Type"] == "audio/wav"
            assert resp.content.startswith(b"RIFF")
            assert b"WAVE" in resp.content[:64]
            # Ensure we're not truncating the clip: response duration should be >= input duration.
            with wave.open(path, "rb") as wf_in:
                in_frames = wf_in.getnframes()
                in_sr = wf_in.getframerate()
            with wave.open(io.BytesIO(resp.content), "rb") as wf_out:
                out_frames = wf_out.getnframes()
                out_sr = wf_out.getframerate()
            assert out_sr == in_sr
            assert out_frames >= in_frames
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def test_audio_lab_render_invalid_json_returns_400(self):
        resp = self.client.post(
            reverse("audio_lab_render"),
            data="{not json",
            content_type="application/json",
        )
        assert resp.status_code == 400


