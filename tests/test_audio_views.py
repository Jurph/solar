from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.core.files.base import ContentFile
from django.utils import timezone

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.actor import Pilot


def _minimal_wav() -> bytes:
    """Return a tiny valid WAV file (0.01s silence) for use in tests."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(b"\x00\x00" * 480)
    return buf.getvalue()


class TestAudioPresetEndpoint(TestCase):
    def setUp(self):
        self.client = Client()

    def test_audio_preset_quindar_start_returns_wav(self):
        url = reverse("audio_preset", kwargs={"preset": "quindar_start"})
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


class TestEventAudioEndpoint(TestCase):
    """Tests for the /api/event_audio/<id>/ endpoint."""

    def setUp(self):
        self.client = Client()
        self.actor = Pilot.objects.create(name="Test Pilot")

    def _create_minimal_wav(self) -> bytes:
        """Create a minimal valid WAV file for testing."""
        with io.BytesIO() as buf:
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00" * (22050 // 10 * 2))  # 0.1s silence
            return buf.getvalue()

    def test_head_returns_200_for_prerendered_audio(self):
        """
        HEAD request should return 200 when audio_file exists.

        BUG: HEAD handler only checks cache, not audio_file field, causing
        frontend to think audio isn't ready even when worker has generated it.
        """
        # Create event with pre-rendered audio
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.actor,
            actor_name=self.actor.name,
            text="Mars base, requesting docking clearance.",
        )

        # Simulate worker having generated audio
        wav_bytes = self._create_minimal_wav()
        event.audio_file.save(f"event_{event.id}.wav", ContentFile(wav_bytes))
        event.audio_rendered_at = timezone.now()
        event.save()

        # Make HEAD request
        response = self.client.head(f"/api/event_audio/{event.id}/")

        # Should return 200 (audio available)
        self.assertEqual(
            response.status_code,
            200,
            "HEAD request should return 200 when audio_file exists",
        )
        self.assertEqual(response["Content-Type"], "audio/wav")

    def test_head_returns_202_when_audio_not_ready(self):
        """HEAD request should return 202 when audio hasn't been generated yet."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.actor,
            actor_name=self.actor.name,
            text="Saturn base, this is Apollo.",
        )

        # No audio generated yet
        response = self.client.head(f"/api/event_audio/{event.id}/")

        # Should return 202 (audio pending generation by worker)
        self.assertEqual(
            response.status_code,
            202,
            "HEAD request should return 202 when audio not ready",
        )

    def test_get_returns_202_when_audio_pending(self):
        """GET request should return 202 when audio is being generated."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.actor,
            actor_name=self.actor.name,
            text="Jupiter Control, requesting approach vector.",
        )

        # No audio generated yet
        response = self.client.get(f"/api/event_audio/{event.id}/")

        # Should return 202 (pending)
        self.assertEqual(
            response.status_code,
            202,
            "GET request should return 202 when audio pending generation",
        )
        self.assertEqual(response.json()["status"], "pending")

    def test_web_server_serves_worker_generated_audio(self):
        """
        Integration test: Web server should serve audio files generated by worker.

        This validates the core worker → web server handoff:
        - Worker writes audio to disk via Django's FileField
        - Web server reads audio from disk and serves it
        - Both use Django's storage API (single source of truth)
        """
        # Create event
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.actor,
            actor_name=self.actor.name,
            text="Mars Control, we have landed safely.",
        )

        # Simulate worker generating audio file
        wav_bytes = self._create_minimal_wav()
        event.audio_file.save(f"event_{event.id}.wav", ContentFile(wav_bytes))
        event.audio_rendered_at = timezone.now()
        event.save()

        # Web server should serve the file
        response = self.client.get(f"/api/event_audio/{event.id}/")

        self.assertEqual(
            response.status_code, 200, "Web server should serve worker-generated audio"
        )
        self.assertEqual(response["Content-Type"], "audio/wav")
        self.assertTrue(
            response.content.startswith(b"RIFF"), "Response should be valid WAV file"
        )
        # Should be the same bytes the worker wrote
        self.assertEqual(
            response.content,
            wav_bytes,
            "Served audio should match worker-generated file",
        )

    def test_http_202_then_success_flow(self):
        """
        Integration test: Full lifecycle of audio generation.

        This validates the frontend's expected flow:
        1. Request audio before worker generates → 202 Pending
        2. Worker generates audio
        3. Request again → 200 OK with audio
        """
        # Create event without audio
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.actor,
            actor_name=self.actor.name,
            text="Jupiter Control, beginning final approach.",
        )

        # Phase 1: Request audio before worker generates
        response = self.client.get(f"/api/event_audio/{event.id}/")
        self.assertEqual(
            response.status_code, 202, "First request should return 202 (audio pending)"
        )
        self.assertEqual(response.json()["status"], "pending")

        # Phase 2: Simulate worker generating audio
        wav_bytes = self._create_minimal_wav()
        event.audio_file.save(f"event_{event.id}.wav", ContentFile(wav_bytes))
        event.audio_rendered_at = timezone.now()
        event.save()

        # Phase 3: Request again after worker generates
        response = self.client.get(f"/api/event_audio/{event.id}/")
        self.assertEqual(
            response.status_code, 200, "Second request should return 200 (audio ready)"
        )
        self.assertEqual(response["Content-Type"], "audio/wav")
        self.assertTrue(response.content.startswith(b"RIFF"))
        self.assertEqual(response.content, wav_bytes)


class TestEventAudioDegradedStates(TestCase):
    """
    Tests for event_audio endpoint under degraded / seam conditions.

    Policy encoded here:
    - 404 means event does not exist
    - 202 means event exists but audio is not currently available
    - Cache wins over stale/missing audio_file references
    """

    def setUp(self):
        self.client = Client()
        cache.clear()  # Prevent ID-reuse cache pollution between tests
        self.actor = Pilot.objects.create(name="Degraded State Pilot")

    def _create_minimal_wav(self) -> bytes:
        with io.BytesIO() as buf:
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00" * (22050 // 10 * 2))
            return buf.getvalue()

    def _make_event(self) -> DialogueEventLog:
        return DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=self.actor,
            actor_name=self.actor.name,
            text="Test message.",
        )

    # --- 404 policy: event does not exist ---

    def test_get_missing_event_returns_404(self):
        """GET for a nonexistent event_id returns 404, not 202."""
        response = self.client.get("/api/event_audio/999999/")
        self.assertEqual(response.status_code, 404)

    def test_head_missing_event_returns_404(self):
        """HEAD for a nonexistent event_id returns 404."""
        response = self.client.head("/api/event_audio/999999/")
        self.assertEqual(response.status_code, 404)

    # --- Stale audio_file, no cache: event exists but audio is unavailable ---

    def test_stale_audio_file_cache_miss_returns_202(self):
        """
        Event row has audio_file name set but file was deleted from disk.
        No cache entry exists.  Endpoint must return 202 (not 500 or 404).
        """
        event = self._make_event()
        wav_bytes = self._create_minimal_wav()
        event.audio_file.save(f"event_{event.id}.wav", ContentFile(wav_bytes))
        os.remove(event.audio_file.path)  # Simulate stale reference

        response = self.client.get(f"/api/event_audio/{event.id}/")
        self.assertEqual(response.status_code, 202)

    def test_head_stale_audio_file_cache_miss_returns_202(self):
        """HEAD: stale audio_file with no cache → 202."""
        event = self._make_event()
        wav_bytes = self._create_minimal_wav()
        event.audio_file.save(f"event_{event.id}.wav", ContentFile(wav_bytes))
        os.remove(event.audio_file.path)

        response = self.client.head(f"/api/event_audio/{event.id}/")
        self.assertEqual(response.status_code, 202)

    # --- Cache wins over stale/missing audio_file ---

    def test_stale_audio_file_cache_hit_returns_200(self):
        """
        Event row has audio_file name set but file was deleted from disk.
        Cache has mixed audio.  Cache wins: endpoint returns 200.
        """
        event = self._make_event()
        wav_bytes = self._create_minimal_wav()
        event.audio_file.save(f"event_{event.id}.wav", ContentFile(wav_bytes))
        os.remove(event.audio_file.path)  # Stale reference
        cache.set(f"mixed_audio:{event.id}", wav_bytes)

        response = self.client.get(f"/api/event_audio/{event.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")

    def test_head_stale_audio_file_cache_hit_returns_200(self):
        """HEAD: stale audio_file + cache hit → 200."""
        event = self._make_event()
        wav_bytes = self._create_minimal_wav()
        event.audio_file.save(f"event_{event.id}.wav", ContentFile(wav_bytes))
        os.remove(event.audio_file.path)
        cache.set(f"mixed_audio:{event.id}", wav_bytes)

        response = self.client.head(f"/api/event_audio/{event.id}/")
        self.assertEqual(response.status_code, 200)

    def test_no_audio_file_cache_hit_returns_200(self):
        """
        Event has no audio_file at all, but cache has mixed audio.
        Endpoint must return 200 (cached audio is still audio).
        """
        event = self._make_event()
        wav_bytes = self._create_minimal_wav()
        cache.set(f"mixed_audio:{event.id}", wav_bytes)

        response = self.client.get(f"/api/event_audio/{event.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")

    def test_head_no_audio_file_cache_hit_returns_200(self):
        """HEAD: no audio_file, but cache has data → 200."""
        event = self._make_event()
        wav_bytes = self._create_minimal_wav()
        cache.set(f"mixed_audio:{event.id}", wav_bytes)

        response = self.client.head(f"/api/event_audio/{event.id}/")
        self.assertEqual(response.status_code, 200)


class TestClearEventsFullReset(TestCase):
    """
    Tests for clear_events covering all three affected layers:
    database rows, audio files on disk, and Django cache.
    """

    def setUp(self):
        self.client = Client()
        DialogueEventLog.objects.all().delete()
        cache.clear()

    def _create_minimal_wav(self) -> bytes:
        with io.BytesIO() as buf:
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00" * (22050 // 10 * 2))
            return buf.getvalue()

    def test_clear_events_removes_cache_keys(self):
        """clear_events calls cache.clear() so mixed_audio cache entries are gone."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor_name="Test Pilot",
            text="Test.",
        )
        wav_bytes = self._create_minimal_wav()
        cache.set(f"mixed_audio:{event.id}", wav_bytes)
        self.assertIsNotNone(cache.get(f"mixed_audio:{event.id}"))

        self.client.post("/api/clear-events/")

        self.assertIsNone(
            cache.get(f"mixed_audio:{event.id}"),
            "Cache entry should be gone after clear_events",
        )

    def test_event_audio_after_clear_returns_404(self):
        """After clear_events, requesting audio for a deleted event returns 404."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor_name="Test Pilot",
            text="Test.",
        )
        event_id = event.id

        self.client.post("/api/clear-events/")

        response = self.client.get(f"/api/event_audio/{event_id}/")
        self.assertEqual(response.status_code, 404)

    def test_clear_events_with_audio_file_deletes_file(self):
        """clear_events deletes audio files on disk, not just DB rows."""
        actor = Pilot.objects.create(name="File Deletion Pilot")
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=actor,
            actor_name=actor.name,
            text="Test.",
        )
        wav_bytes = self._create_minimal_wav()
        event.audio_file.save(f"event_{event.id}.wav", ContentFile(wav_bytes))
        file_path = event.audio_file.path
        self.assertTrue(os.path.exists(file_path))

        self.client.post("/api/clear-events/")

        self.assertFalse(
            os.path.exists(file_path), "Audio file should be deleted by clear_events"
        )


class TestEventAudioActorlessInvariant(TestCase):
    """
    event_audio must return 400 for actor-less events.

    Policy: an actor-less DialogueEvent is a critical invariant violation.
    The web server must surface this as an explicit error, not a silent 202.
    """

    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_get_returns_400_for_actorless_event(self):
        """GET /api/event_audio/<id>/ returns 400 when event has no actor."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=None,
            actor_name="Ghost Speaker",
            text="Test transmission.",
        )
        response = self.client.get(f"/api/event_audio/{event.id}/")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "error")

    def test_head_returns_400_for_actorless_event(self):
        """HEAD /api/event_audio/<id>/ returns 400 when event has no actor."""
        event = DialogueEventLog.objects.create(
            timestamp=100.0,
            actor=None,
            actor_name="Ghost Speaker",
            text="Test transmission.",
        )
        response = self.client.head(f"/api/event_audio/{event.id}/")
        self.assertEqual(response.status_code, 400)


# ---------------------------------------------------------------------------
# _find_audio_lab_tts_sample_path()
# ---------------------------------------------------------------------------


class TestFindAudioLabTTSSamplePath(TestCase):
    """_find_audio_lab_tts_sample_path() fallback chain."""

    def test_returns_finder_result_when_found(self):
        """When staticfiles finders resolves the path, it is returned directly."""
        from mysite.universe.views.audio import _find_audio_lab_tts_sample_path

        with patch(
            "mysite.universe.views.audio.finders.find", return_value="/found/path.wav"
        ):
            result = _find_audio_lab_tts_sample_path()
        self.assertEqual(result, "/found/path.wav")

    def test_returns_legacy_path_when_finder_fails_but_legacy_exists(self):
        """When finders returns None but the legacy staticfiles/ path exists, it is used."""
        from mysite.universe.views.audio import _find_audio_lab_tts_sample_path

        with patch("mysite.universe.views.audio.finders.find", return_value=None):
            with patch("os.path.exists", return_value=True):
                result = _find_audio_lab_tts_sample_path()
        self.assertIsNotNone(result)
        self.assertIn("staticfiles", result)

    def test_returns_none_when_neither_source_found(self):
        """When both finders and legacy path fail, None is returned."""
        from mysite.universe.views.audio import _find_audio_lab_tts_sample_path

        with patch("mysite.universe.views.audio.finders.find", return_value=None):
            with patch("os.path.exists", return_value=False):
                result = _find_audio_lab_tts_sample_path()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _save_last_playback()
# ---------------------------------------------------------------------------


class TestSaveLastPlayback(TestCase):
    """_save_last_playback() swallows write errors."""

    def test_write_exception_is_swallowed(self):
        """An OSError during write is caught; no exception propagates."""
        from mysite.universe.views.audio import _save_last_playback

        with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
            _save_last_playback(b"fake_wav")  # must not raise


# ---------------------------------------------------------------------------
# audio_lab GET
# ---------------------------------------------------------------------------


class TestAudioLabView(TestCase):
    """audio_lab renders the dev-tool template."""

    def setUp(self):
        self.client = Client()

    def test_get_returns_200(self):
        url = reverse("audio_lab")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# audio_lab_render POST — modem mode
# ---------------------------------------------------------------------------


class TestAudioLabRenderModemMode(TestCase):
    """audio_lab_render default (modem) mode produces WAV without any TTS."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("audio_lab_render")

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.url, data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_body_uses_defaults_returns_wav(self):
        response = self.client.post(
            self.url, data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")

    def test_modem_mode_with_quindar_returns_wav(self):
        payload = {"mode": "modem", "text": "NAVSAT TEST", "include_quindar": True}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")

    def test_modem_mode_without_quindar_returns_wav(self):
        payload = {"mode": "modem", "text": "NAVSAT TEST", "include_quindar": False}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# audio_lab_render POST — TTS mode  (sys.modules mock avoids importing torch)
# ---------------------------------------------------------------------------


def _mock_tts_module(wav_bytes: bytes | None = None) -> MagicMock:
    """Return a mock tts_service module whose get_tts_service() yields a mock service."""
    mock_svc = MagicMock()
    mock_svc.generate.return_value = wav_bytes or _minimal_wav()
    mock_module = MagicMock()
    mock_module.get_tts_service.return_value = mock_svc
    return mock_module


class TestAudioLabRenderTTSMode(TestCase):
    """audio_lab_render TTS mode branches; tts_service is mocked to avoid torch."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("audio_lab_render")

    def test_tts_mode_with_voice_id_returns_wav(self):
        """Happy path: voice_id provided, TTS generates valid WAV."""
        mock_mod = _mock_tts_module()
        payload = {"mode": "tts", "voice_id": "pilot_default", "text": "Check."}
        with patch.dict(
            sys.modules, {"mysite.universe.services.tts_service": mock_mod}
        ):
            response = self.client.post(
                self.url, data=json.dumps(payload), content_type="application/json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")

    def test_tts_mode_tts_failure_falls_back_to_sample(self):
        """TTS generation raises; view falls back to sample clip."""
        mock_mod = _mock_tts_module()
        mock_mod.get_tts_service.return_value.generate.side_effect = RuntimeError(
            "GPU OOM"
        )

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(_minimal_wav())
            sample_path = tmp.name
        try:
            payload = {"mode": "tts", "voice_id": "pilot_default", "text": "Check."}
            with patch.dict(
                sys.modules, {"mysite.universe.services.tts_service": mock_mod}
            ):
                with patch(
                    "mysite.universe.views.audio._find_audio_lab_tts_sample_path",
                    return_value=sample_path,
                ):
                    response = self.client.post(
                        self.url,
                        data=json.dumps(payload),
                        content_type="application/json",
                    )
        finally:
            os.unlink(sample_path)
        self.assertEqual(response.status_code, 200)

    def test_tts_mode_no_clip_returns_501(self):
        """TTS fails and no sample exists → 501."""
        mock_mod = _mock_tts_module()
        mock_mod.get_tts_service.return_value.generate.side_effect = RuntimeError(
            "no model"
        )
        payload = {"mode": "tts", "voice_id": "ghost", "text": "Check."}
        with patch.dict(
            sys.modules, {"mysite.universe.services.tts_service": mock_mod}
        ):
            with patch(
                "mysite.universe.views.audio._find_audio_lab_tts_sample_path",
                return_value=None,
            ):
                response = self.client.post(
                    self.url, data=json.dumps(payload), content_type="application/json"
                )
        self.assertEqual(response.status_code, 501)

    def test_tts_mode_fragment_loop_skips_missing_files(self):
        """component_N_gain > 0 exercises the audio fragment loop; missing files are skipped."""
        mock_mod = _mock_tts_module()
        payload = {
            "mode": "tts",
            "voice_id": "pilot_default",
            "text": "Check.",
            "component_1_gain": 1.0,
            "component_2_gain": 0.5,
            "include_quindar": False,
            "include_static": False,
        }
        with patch.dict(
            sys.modules, {"mysite.universe.services.tts_service": mock_mod}
        ):
            with patch("mysite.universe.views.audio.finders.find", return_value=None):
                response = self.client.post(
                    self.url, data=json.dumps(payload), content_type="application/json"
                )
        self.assertEqual(response.status_code, 200)

    def test_tts_mode_fragment_loop_adds_found_fragment(self):
        """When finders resolves a fragment file, LoopedAudioFragment is added."""
        mock_mod = _mock_tts_module()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(_minimal_wav())
            fragment_path = tmp.name
        try:
            payload = {
                "mode": "tts",
                "voice_id": "pilot_default",
                "text": "Check.",
                "component_1_gain": 1.0,
                "include_quindar": False,
                "include_static": False,
            }
            with patch.dict(
                sys.modules, {"mysite.universe.services.tts_service": mock_mod}
            ):
                with patch(
                    "mysite.universe.views.audio.finders.find",
                    return_value=fragment_path,
                ):
                    response = self.client.post(
                        self.url,
                        data=json.dumps(payload),
                        content_type="application/json",
                    )
        finally:
            os.unlink(fragment_path)
        self.assertEqual(response.status_code, 200)

    def test_tts_mode_with_echo_and_rumble(self):
        """include_echo and include_rumble exercise additional component branches."""
        mock_mod = _mock_tts_module()
        payload = {
            "mode": "tts",
            "voice_id": "pilot_default",
            "text": "Check.",
            "include_echo": True,
            "include_rumble": True,
            "include_static": True,
            "include_quindar": True,
        }
        with patch.dict(
            sys.modules, {"mysite.universe.services.tts_service": mock_mod}
        ):
            response = self.client.post(
                self.url, data=json.dumps(payload), content_type="application/json"
            )
        self.assertEqual(response.status_code, 200)

    def test_tts_mode_without_voice_id_uses_sample_path(self):
        """TTS mode with no voice_id skips TTS generation and uses sample path."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(_minimal_wav())
            sample_path = tmp.name
        try:
            payload = {
                "mode": "tts",
                "text": "Check.",
                "include_quindar": False,
                "include_static": False,
            }
            with patch(
                "mysite.universe.views.audio._find_audio_lab_tts_sample_path",
                return_value=sample_path,
            ):
                response = self.client.post(
                    self.url, data=json.dumps(payload), content_type="application/json"
                )
        finally:
            os.unlink(sample_path)
        self.assertEqual(response.status_code, 200)
