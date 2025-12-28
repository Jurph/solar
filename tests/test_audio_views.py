from __future__ import annotations

from django.test import Client, TestCase
from django.urls import reverse


class TestAudioPresetEndpoint(TestCase):
    def setUp(self):
        self.client = Client()

    def test_audio_preset_room_tone_placeholder_returns_wav(self):
        url = reverse("audio_preset", kwargs={"preset": "room_tone_placeholder"})
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert resp["Content-Type"] == "audio/wav"
        assert resp.content.startswith(b"RIFF")
        assert b"WAVE" in resp.content[:64]

    def test_audio_preset_modem_noise_with_text_param_returns_wav(self):
        url = reverse("audio_preset", kwargs={"preset": "modem_noise_example"})
        resp = self.client.get(url, {"text": "HELLO MODEM", "gain": "0.2"})
        assert resp.status_code == 200
        assert resp["Content-Type"] == "audio/wav"
        assert resp.content.startswith(b"RIFF")
        assert b"WAVE" in resp.content[:64]

    def test_audio_preset_unknown_returns_404(self):
        url = reverse("audio_preset", kwargs={"preset": "does_not_exist"})
        resp = self.client.get(url)
        assert resp.status_code == 404

