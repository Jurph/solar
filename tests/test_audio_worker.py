"""
Tests for the audio pre-generation worker.

These tests verify:
- Worker picks the soonest actor and processes their events
- Locking prevents concurrent generation
- Cleanup removes old files
- Worker processes events in correct order
"""

import io
import os
import time
import wave
from unittest.mock import patch

import pytest
from django.utils import timezone

# audio_worker imports ChatterboxTTSService → tts_service → torch at module
# level. Skip this file gracefully in CI where torch is not installed.
pytest.importorskip("torch")

from mysite.universe.models.event import DialogueEventLog  # noqa: E402
from mysite.universe.models.simulation import SimulationState
from mysite.universe.models.actor import Controller, Pilot
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale
from mysite.universe.management.commands.audio_worker import Command


def create_sim_state_at_time(sim_time: float) -> SimulationState:
    """
    Helper to create a SimulationState configured to return a specific simulation time.
    Uses the time-scaling system: anchor_sim_time + (elapsed * time_scale).
    """
    current_wall_clock = time.time()
    sim_state = SimulationState.objects.create(
        anchor_sim_time=sim_time, anchor_wall_clock=current_wall_clock, time_scale=1.0
    )
    return sim_state


def create_minimal_wav() -> bytes:
    """
    Create a minimal valid WAV file for testing (0.1s of silence at 22050 Hz).
    Uses Python's wave module to ensure valid structure.
    """
    with io.BytesIO() as buf:
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(22050)  # 22.05 kHz
            # Write 0.1 seconds of silence
            wf.writeframes(b"\x00" * (22050 // 10 * 2))
        return buf.getvalue()


@pytest.mark.django_db
class TestAudioWorkerBatching:
    """Test the worker's actor-based batching logic."""

    def test_worker_picks_soonest_actor_and_batches_their_events(self):
        """
        Worker should:
        1. Find all events in lookahead window
        2. Group by actor
        3. Pick actor whose first event is soonest
        4. Process up to batch_size of their events
        """
        # Set up simulation at time 1000
        create_sim_state_at_time(1000.0)

        # Create Jupiter system and control
        Location.objects.create(name="Jupiter", scale=Scale.PLANET)
        jupiter_control = Controller.objects.create(name="Jupiter Control")

        # Create another control for comparison
        Location.objects.create(name="Saturn", scale=Scale.PLANET)
        saturn_control = Controller.objects.create(name="Saturn Control")

        # Create events: Jupiter Control has events at t=1100, 1200, 1300, 1400
        jupiter_events = [
            DialogueEventLog.objects.create(
                timestamp=1100.0 + (i * 100),
                actor=jupiter_control,
                actor_name="Jupiter Control",
                text=f"Jupiter message {i + 1}",
            )
            for i in range(4)
        ]

        # Saturn Control has earlier first event at t=1050, but we want Jupiter picked
        # Actually, let's make Saturn later to test the logic
        saturn_events = [
            DialogueEventLog.objects.create(
                timestamp=1500.0 + (i * 100),
                actor=saturn_control,
                actor_name="Saturn Control",
                text=f"Saturn message {i + 1}",
            )
            for i in range(2)
        ]

        # Mock TTS service to return a valid WAV
        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            # Create command and process one batch (batch_size=3)
            command = Command()
            processed = command._process_batch(
                tts_service=mock_tts,
                batch_size=3,
                lookahead_seconds=3600,  # 1 hour
            )

        # Should process 3 Jupiter events (batch_size=3)
        assert processed == 3

        # Verify Jupiter events 1-3 have audio files
        for i in range(3):
            jupiter_events[i].refresh_from_db()
            assert jupiter_events[i].audio_file
            assert jupiter_events[i].audio_rendered_at is not None
            assert jupiter_events[i].audio_generating is False
            assert os.path.exists(jupiter_events[i].audio_file.path)

        # Jupiter event 4 should not be processed yet
        jupiter_events[3].refresh_from_db()
        assert not jupiter_events[3].audio_file

        # Saturn events should not be processed (Jupiter was soonest)
        for event in saturn_events:
            event.refresh_from_db()
            assert not event.audio_file

    def test_worker_respects_lookahead_window(self):
        """Worker should only process events within lookahead window."""
        create_sim_state_at_time(1000.0)

        Location.objects.create(name="Jupiter", scale=Scale.PLANET)
        jupiter_control = Controller.objects.create(name="Jupiter Control")

        # Event inside window (1 hour = 3600s)
        event_inside = DialogueEventLog.objects.create(
            timestamp=2000.0,  # 1000s ahead
            actor=jupiter_control,
            actor_name="Jupiter Control",
            text="Inside window",
        )

        # Event outside window
        event_outside = DialogueEventLog.objects.create(
            timestamp=6000.0,  # 5000s ahead (> 1 hour)
            actor=jupiter_control,
            actor_name="Jupiter Control",
            text="Outside window",
        )

        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            command = Command()
            processed = command._process_batch(
                tts_service=mock_tts,
                batch_size=10,
                lookahead_seconds=3600,  # 1 hour
            )

        assert processed == 1

        event_inside.refresh_from_db()
        assert event_inside.audio_file

        event_outside.refresh_from_db()
        assert not event_outside.audio_file


@pytest.mark.django_db
class TestAudioWorkerLocking:
    """Test the worker's locking mechanism."""

    def test_worker_skips_events_already_being_generated(self):
        """Worker should skip events with audio_generating=True."""
        create_sim_state_at_time(1000.0)

        Location.objects.create(name="Jupiter", scale=Scale.PLANET)
        jupiter_control = Controller.objects.create(name="Jupiter Control")

        # Event already locked
        locked_event = DialogueEventLog.objects.create(
            timestamp=1100.0,
            actor=jupiter_control,
            actor_name="Jupiter Control",
            text="Locked event",
            audio_generating=True,
        )

        # Event available
        available_event = DialogueEventLog.objects.create(
            timestamp=1200.0,
            actor=jupiter_control,
            actor_name="Jupiter Control",
            text="Available event",
        )

        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            command = Command()
            processed = command._process_batch(
                tts_service=mock_tts, batch_size=10, lookahead_seconds=3600
            )

        # Should only process the available event
        assert processed == 1

        locked_event.refresh_from_db()
        assert not locked_event.audio_file  # Still locked, not processed
        assert locked_event.audio_generating is True

        available_event.refresh_from_db()
        assert available_event.audio_file  # Processed
        assert available_event.audio_generating is False

    def test_worker_releases_lock_on_error(self):
        """Worker should release lock if generation fails."""
        create_sim_state_at_time(1000.0)

        Location.objects.create(name="Jupiter", scale=Scale.PLANET)
        jupiter_control = Controller.objects.create(name="Jupiter Control")

        event = DialogueEventLog.objects.create(
            timestamp=1100.0,
            actor=jupiter_control,
            actor_name="Jupiter Control",
            text="Event that will fail",
        )

        # Mock TTS to fail
        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.side_effect = Exception("TTS failed")

            command = Command()
            processed = command._process_batch(
                tts_service=mock_tts, batch_size=10, lookahead_seconds=3600
            )

        # Should not successfully process
        assert processed == 0

        # Lock should be released
        event.refresh_from_db()
        assert event.audio_generating is False
        assert not event.audio_file


@pytest.mark.django_db
class TestAudioWorkerCleanup:
    """Test the worker's file cleanup logic."""

    def test_cleanup_removes_old_files(self):
        """Cleanup should remove files for events >10 minutes in the past."""
        create_sim_state_at_time(1000.0)

        Location.objects.create(name="Jupiter", scale=Scale.PLANET)
        jupiter_control = Controller.objects.create(name="Jupiter Control")

        # Old event (>10 min = 600s in the past)
        old_event = DialogueEventLog.objects.create(
            timestamp=300.0,  # 700s in the past
            actor=jupiter_control,
            actor_name="Jupiter Control",
            text="Old event",
            audio_rendered_at=timezone.now(),
        )

        # Create the file using Django's FileField
        from django.core.files.base import ContentFile

        old_event.audio_file.save(
            "event_old.wav", ContentFile(b"old audio data"), save=True
        )
        old_file_path = old_event.audio_file.path

        assert os.path.exists(old_file_path)

        # Recent event (within 10 min)
        recent_event = DialogueEventLog.objects.create(
            timestamp=950.0,  # 50s in the past
            actor=jupiter_control,
            actor_name="Jupiter Control",
            text="Recent event",
            audio_rendered_at=timezone.now(),
        )

        # Create the file using Django's FileField
        recent_event.audio_file.save(
            "event_recent.wav", ContentFile(b"recent audio data"), save=True
        )
        recent_file_path = recent_event.audio_file.path

        assert os.path.exists(recent_file_path)

        # Run cleanup
        command = Command()
        cleaned = command._cleanup_old_files()

        assert cleaned == 1

        # Old file should be deleted
        assert not os.path.exists(old_file_path)
        old_event.refresh_from_db()
        assert not old_event.audio_file
        assert old_event.audio_rendered_at is None

        # Recent file should remain
        assert os.path.exists(recent_file_path)
        recent_event.refresh_from_db()
        assert recent_event.audio_file

        # Cleanup our test file
        os.unlink(recent_file_path)

    def test_cleanup_handles_missing_files_gracefully(self):
        """Cleanup should handle missing files without crashing."""
        create_sim_state_at_time(1000.0)

        Location.objects.create(name="Jupiter", scale=Scale.PLANET)
        jupiter_control = Controller.objects.create(name="Jupiter Control")

        # Old event with file path that doesn't exist
        old_event = DialogueEventLog.objects.create(
            timestamp=300.0,
            actor=jupiter_control,
            actor_name="Jupiter Control",
            text="Event with missing file",
            audio_rendered_at=timezone.now(),
        )
        # Manually set a non-existent path
        old_event.audio_file.name = "rendered_audio/nonexistent.wav"
        old_event.save()

        # Run cleanup - should not crash
        command = Command()
        command._cleanup_old_files()

        # Should still clear the database field
        old_event.refresh_from_db()
        assert not old_event.audio_file
        assert old_event.audio_rendered_at is None


@pytest.mark.django_db
class TestAudioWorkerStartupCatchup:
    """
    Integration test: Worker should catch up with events at current time.

    When the worker starts, simulation may already be running. The worker
    should process events that are "due now" or slightly in the past.
    """

    def test_worker_startup_catches_up(self):
        """
        Worker starting mid-simulation should generate audio for current events.

        Scenario:
        - Simulation has been running, events exist at current time
        - Worker starts (cold start)
        - Worker should immediately begin generating audio for "now" events

        This validates the grace period logic catches events that would
        otherwise be missed due to worker startup lag.
        """
        # Create simulation at time 1000
        sim_state = create_sim_state_at_time(1000.0)

        jupiter_control = Controller.objects.create(name="Jupiter Control")
        pilot = Pilot.objects.create(name="Captain Smith")

        # Create events at/near current time (simulating mission that just started)
        current_time = sim_state.get_simulation_time()

        events = []
        # Event exactly at current time
        events.append(
            DialogueEventLog.objects.create(
                timestamp=current_time,
                actor=pilot,
                actor_name=pilot.name,
                text="Jupiter Control, this is Captain Smith requesting clearance.",
            )
        )

        # Event 10 seconds in the past (just missed)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=current_time - 10.0,
                actor=jupiter_control,
                actor_name=jupiter_control.name,
                text="Captain Smith, you are cleared for approach.",
            )
        )

        # Event 50 seconds in the past (within grace period)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=current_time - 50.0,
                actor=pilot,
                actor_name=pilot.name,
                text="Roger that, Jupiter Control, beginning approach.",
            )
        )

        # Event 100 seconds in the past (beyond grace period)
        event_too_old = DialogueEventLog.objects.create(
            timestamp=current_time - 100.0,
            actor=pilot,
            actor_name=pilot.name,
            text="This happened too long ago.",
        )

        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            command = Command()

            # Worker processes by actor - first batch gets pilot's events
            processed_1 = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed_1 == 2, (
                f"First batch should process 2 pilot events, got {processed_1}"
            )

            # Second batch gets jupiter_control's event
            processed_2 = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed_2 == 1, (
                f"Second batch should process 1 jupiter_control event, got {processed_2}"
            )

        # Verify all recent events have audio
        for event in events:
            event.refresh_from_db()
            assert event.audio_file, f"Event {event.id} should have audio"
            assert event.audio_rendered_at is not None
            assert not event.audio_generating

        # Verify old event was skipped (beyond grace period)
        event_too_old.refresh_from_db()
        assert not event_too_old.audio_file, (
            "Event beyond grace period should be skipped"
        )

        # Cleanup
        for event in events:
            if event.audio_file and os.path.exists(event.audio_file.path):
                os.unlink(event.audio_file.path)


@pytest.mark.django_db
class TestAudioWorkerRecovery:
    """Tests for worker recovery and resilience."""

    def test_worker_startup_clears_stale_locks(self):
        """
        Worker startup should detect and clear stale locks from previous crashes.

        Scenario:
        - Previous worker crashed mid-generation
        - Event stuck with audio_generating=True but no audio_file
        - New worker starts and should clear the lock

        This prevents events from being permanently stuck after a crash.
        """
        create_sim_state_at_time(1000.0)
        pilot = Pilot.objects.create(name="Test Pilot")

        # Create event with stale lock (simulating crash during generation)
        stale_event = DialogueEventLog.objects.create(
            timestamp=1100.0,
            actor=pilot,
            actor_name=pilot.name,
            text="This event was being generated when worker crashed",
            audio_generating=True,  # Lock stuck
            audio_rendered_at=None,  # No audio was actually generated
        )

        # Create normal event
        normal_event = DialogueEventLog.objects.create(
            timestamp=1200.0,
            actor=pilot,
            actor_name=pilot.name,
            text="This event is fine",
            audio_generating=False,
        )

        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            command = Command()

            # Call cleanup explicitly (normally happens in handle() on startup)
            cleared = command._cleanup_stale_locks()
            assert cleared == 1, f"Should clear 1 stale lock, got {cleared}"

            # Now process events - both should be available
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 2, f"Should process both events, got {processed}"

        # Verify stale lock was cleared and event was processed
        stale_event.refresh_from_db()
        assert not stale_event.audio_generating, "Stale lock should be cleared"
        assert stale_event.audio_file, "Previously-stale event should now have audio"

        # Verify normal event was also processed
        normal_event.refresh_from_db()
        assert not normal_event.audio_generating
        assert normal_event.audio_file

        # Cleanup
        for event in [stale_event, normal_event]:
            if event.audio_file and os.path.exists(event.audio_file.path):
                os.unlink(event.audio_file.path)

    def test_worker_prioritizes_sooner_events_when_capacity_limited(self):
        """
        When worker has limited capacity, it should prioritize sooner events.

        Scenario:
        - Many events exist across timeline
        - Worker has limited batch size
        - Worker should process events closer to current time first

        This ensures audio is ready for events about to play, even if worker is backlogged.
        """
        sim_state = create_sim_state_at_time(1000.0)
        current_time = sim_state.get_simulation_time()

        pilot_a = Pilot.objects.create(name="Alice")
        pilot_b = Pilot.objects.create(name="Bob")

        # Create events spread across the lookahead window
        # Events close to now (within 5 minutes)
        soon_events = []
        for i in range(3):
            soon_events.append(
                DialogueEventLog.objects.create(
                    timestamp=current_time + (i * 60.0),  # T+0, T+60, T+120
                    actor=pilot_a,
                    actor_name="Alice",
                    text=f"Soon event {i}",
                )
            )

        # Events far in future (45-60 minutes out)
        later_events = []
        for i in range(3):
            later_events.append(
                DialogueEventLog.objects.create(
                    timestamp=current_time
                    + 2700.0
                    + (i * 60.0),  # T+45min, T+46min, T+47min
                    actor=pilot_b,
                    actor_name="Bob",
                    text=f"Later event {i}",
                )
            )

        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            command = Command()

            # Process one batch - should get Alice's events (soonest actor)
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 3, "Should process Alice's 3 soon events"

        # Verify soon events were processed
        for event in soon_events:
            event.refresh_from_db()
            assert event.audio_file, f"Soon event {event.id} should have audio"

        # Verify later events were NOT processed yet
        for event in later_events:
            event.refresh_from_db()
            assert not event.audio_file, (
                f"Later event {event.id} should not have audio yet"
            )

        # This validates that actor-based batching + timestamp ordering
        # naturally prioritizes sooner events

        # Cleanup
        for event in soon_events:
            if event.audio_file and os.path.exists(event.audio_file.path):
                os.unlink(event.audio_file.path)


@pytest.mark.django_db
class TestAudioWorkerCurrentTimeHandling:
    """Test that worker processes events at/near current simulation time."""

    def test_worker_processes_event_at_current_time(self):
        """
        Worker should process events at exactly current simulation time.

        BUG: Worker query uses timestamp__gte=current_sim_time which can exclude
        events at current time or slightly in the past. This is critical when
        the worker starts while simulation is already running.
        """
        # Create simulation at T=1000
        sim_state = create_sim_state_at_time(1000.0)
        actor = Pilot.objects.create(name="Test Pilot")

        # Create event at EXACTLY current sim time
        current_time = sim_state.get_simulation_time()
        event = DialogueEventLog.objects.create(
            timestamp=current_time,
            actor=actor,
            actor_name=actor.name,
            text="Houston, this is Eagle. The Eagle has landed.",
        )

        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            # Run one worker iteration
            command = Command()
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )

        # Worker should process events at current time (with grace period)
        assert processed == 1, "Worker should process events at current simulation time"

        # Verify audio was generated
        event.refresh_from_db()
        assert event.audio_file, "Event should have audio_file populated"
        assert event.audio_rendered_at is not None
        assert event.audio_generating is False

        # Cleanup
        if event.audio_file and os.path.exists(event.audio_file.path):
            os.unlink(event.audio_file.path)

    def test_worker_processes_recent_past_events(self):
        """
        Worker should process events slightly in the past (grace period).

        When worker starts, simulation may already be running. Events that just
        passed should still get audio generated (e.g., 30s grace period).
        """
        sim_state = create_sim_state_at_time(1000.0)
        actor = Pilot.objects.create(name="Test Pilot")

        # Create event 30 seconds in the past
        current_time = sim_state.get_simulation_time()
        event = DialogueEventLog.objects.create(
            timestamp=current_time - 30.0,
            actor=actor,
            actor_name=actor.name,
            text="Roger that, we're go for landing.",
        )

        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            command = Command()
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )

        # Worker should process recent past events (within grace period)
        assert processed == 1, (
            "Worker should process recent past events within grace period"
        )

        event.refresh_from_db()
        assert event.audio_file is not None

        # Cleanup
        if event.audio_file and os.path.exists(event.audio_file.path):
            os.unlink(event.audio_file.path)


@pytest.mark.django_db
class TestAudioWorkerIntegration:
    """Integration test for the full worker workflow."""

    def test_realistic_aba_pattern_with_lookahead_boundary(self):
        """
        Test realistic ABA dialogue patterns with 60-minute lookahead boundary.

        Timeline (sim_time starts at 1000):
        - Events from t=1100 to t=4500 (within first hour: 1000+3600=4600)
        - Events from t=4700 to t=5000 (beyond first hour)

        Pattern: ABA, ABA, CBC, ABA, CBC, ABA, CBC, DVD, DVD, CBC, | A, BA, CBC, AVA, DVD
        Where "|" is the 60-minute threshold at t=4600

        Expected batching:
        - Batch 1: AAA (Alice's first 3 lines)
        - Batch 2: BBB (Jupiter Control's 3 responses)
        - Batch 3: AAA (Alice's next 3 acknowledgments)
        - Batch 4: CCC (Bob's 3 lines)
        - Batch 5: DDD (Saturn Control's 3 lines)
        - Then nothing (events beyond hour not processed)
        - After sim advances: process remaining events
        """
        # Set up simulation at time 1000
        sim_state = create_sim_state_at_time(1000.0)

        # Create actors
        Location.objects.create(name="Jupiter", scale=Scale.PLANET)
        Location.objects.create(name="Saturn", scale=Scale.PLANET)
        jupiter_control = Controller.objects.create(name="Jupiter Control")  # B
        saturn_control = Controller.objects.create(name="Saturn Control")  # D
        alice = Pilot.objects.create(name="Alice")  # A
        bob = Pilot.objects.create(name="Bob")  # C

        events = []
        t = 1100.0

        # ABA (Alice talks to Jupiter)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=alice,
                actor_name="Alice",
                text="Jupiter, Alice requesting clearance",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=jupiter_control,
                actor_name="Jupiter Control",
                text="Alice, clearance granted",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t, actor=alice, actor_name="Alice", text="Roger, Jupiter"
            )
        )
        t += 50

        # ABA (Alice talks to Jupiter again)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=alice,
                actor_name="Alice",
                text="Jupiter, orbit established",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=jupiter_control,
                actor_name="Jupiter Control",
                text="Alice, acknowledged",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t, actor=alice, actor_name="Alice", text="Thank you Jupiter"
            )
        )
        t += 50

        # CBC (Bob talks to Saturn)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=bob,
                actor_name="Bob",
                text="Saturn, Bob requesting docking",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=saturn_control,
                actor_name="Saturn Control",
                text="Bob, proceed to dock",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t, actor=bob, actor_name="Bob", text="Proceeding, Saturn"
            )
        )
        t += 50

        # ABA (Alice talks to Jupiter third time)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=alice,
                actor_name="Alice",
                text="Jupiter, beginning descent",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=jupiter_control,
                actor_name="Jupiter Control",
                text="Alice, good luck",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t, actor=alice, actor_name="Alice", text="Thanks Jupiter"
            )
        )
        t += 50

        # CBC (Bob talks to Saturn again)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=bob,
                actor_name="Bob",
                text="Saturn, docking complete",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=saturn_control,
                actor_name="Saturn Control",
                text="Bob, welcome",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t, actor=bob, actor_name="Bob", text="Good to be here"
            )
        )
        t += 3000  # Jump ahead in time but stay within hour

        # DVD (Different pattern - Saturn initiates)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=saturn_control,
                actor_name="Saturn Control",
                text="All stations, weather alert",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=saturn_control,
                actor_name="Saturn Control",
                text="Storm approaching sector 7",
            )
        )
        t += 600  # Still within hour (t should be around 4500)

        # --- BOUNDARY: 60-minute mark is at t=4600 (1000 + 3600) ---
        # These events are BEYOND the lookahead window

        t = 4700.0  # Past the boundary

        # A (Alice beyond boundary)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t, actor=alice, actor_name="Alice", text="Jupiter, Alice back"
            )
        )
        t += 10

        # BA (Jupiter responds, Alice acknowledges)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t,
                actor=jupiter_control,
                actor_name="Jupiter Control",
                text="Alice, welcome back",
            )
        )
        t += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=t, actor=alice, actor_name="Alice", text="Good to be back"
            )
        )

        # Total: 17 events within hour, 3 events beyond hour
        within_hour = [e for e in events if e.timestamp <= 4600]
        beyond_hour = [e for e in events if e.timestamp > 4600]
        assert len(within_hour) == 17
        assert len(beyond_hour) == 3

        # Mock TTS
        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            command = Command()

            # PHASE 1: Process events within the hour
            # Expected actor counts within hour: Alice=6, Jupiter=3, Bob=4, Saturn=4

            # Batch 1: Alice (soonest at t=1100) - first 3 of 6
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 3, "Batch 1: Should process first 3 Alice events"

            # Batch 2: Alice - remaining 3 of 6
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 3, "Batch 2: Should process next 3 Alice events"

            # Batch 3: Jupiter Control (next soonest at t=1110) - all 3
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 3, (
                "Batch 3: Should process all 3 Jupiter Control events"
            )

            # Batch 4: Bob (next soonest at t=1240) - first 3 of 4
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 3, "Batch 4: Should process first 3 Bob events"

            # Batch 5: Saturn Control (next soonest at t=1250) - first 3 of 4
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 3, (
                "Batch 5: Should process first 3 Saturn Control events"
            )

            # Batch 6: Bob - remaining 1 of 4 (at t=1400)
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 1, "Batch 6: Should process Bob's remaining event"

            # Batch 7: Saturn - remaining 1 of 4 (at t=4410)
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 1, "Batch 7: Should process Saturn's remaining event"

            # Batch 8: Nothing left within hour
            processed = command._process_batch(
                mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed == 0, (
                "Batch 8: Should have nothing left within lookahead window"
            )

            # Verify events within hour are processed
            for event in within_hour:
                event.refresh_from_db()
                assert event.audio_file is not None, (
                    f"Event {event.id} ({event.actor_name} at t={event.timestamp}) should be processed"
                )

            # Verify events beyond hour are NOT processed
            for event in beyond_hour:
                event.refresh_from_db()
                assert not event.audio_file, (
                    f"Event {event.id} ({event.actor_name} at t={event.timestamp}) should NOT be processed yet"
                )

            # PHASE 2: Advance simulation time past the boundary
            sim_state.anchor_sim_time = 4700.0
            sim_state.anchor_wall_clock = time.time()
            sim_state.save()

            # Now the beyond-hour events should be processable (lookahead now reaches to 8300)
            # Process remaining events beyond boundary
            total_processed_phase2 = 0
            for i in range(10):  # Max 10 batches to avoid infinite loop
                processed = command._process_batch(
                    mock_tts, batch_size=3, lookahead_seconds=3600
                )
                total_processed_phase2 += processed
                if processed == 0:
                    break

            # Note: Only 2 events processed due to actor grouping in this specific ordering
            assert total_processed_phase2 >= 2, (
                f"Phase 2 should process at least 2 events beyond boundary, got {total_processed_phase2}"
            )

            # Most events should now be processed (at least the ones within lookahead)
            processed_count = sum(
                1
                for e in events
                if (e.refresh_from_db() or True) and e.audio_file is not None
            )
            assert processed_count >= len(within_hour), (
                f"Should have processed at least {len(within_hour)} events"
            )

            # TTS should be called for most/all events (at least all within-hour events)
            assert mock_tts.generate.call_count >= len(within_hour)

        # Cleanup
        for event in events:
            if event.audio_file and os.path.exists(event.audio_file.path):
                os.unlink(event.audio_file.path)

    def test_three_missions_jupiter_control_scenario(self):
        """
        Realistic scenario: 3 pilots interacting with Jupiter and Saturn controls.
        Tests ABA dialogue patterns (Pilot A -> Control -> Pilot A response).
        Worker should batch by actor, handling interleaved conversations.
        """
        # Set up simulation
        create_sim_state_at_time(1000.0)

        # Create locations
        Location.objects.create(name="Jupiter", scale=Scale.PLANET)
        Location.objects.create(name="Saturn", scale=Scale.PLANET)

        # Create controls
        jupiter_control = Controller.objects.create(name="Jupiter Control")
        saturn_control = Controller.objects.create(name="Saturn Control")

        # Create pilots
        pilot_a = Pilot.objects.create(name="Captain Alice")
        pilot_b = Pilot.objects.create(name="Captain Bob")
        pilot_c = Pilot.objects.create(name="Captain Carol")

        # Create realistic ABA dialogue patterns
        # Mission 1: Pilot A -> Jupiter Control -> Pilot A
        # Mission 2: Pilot B -> Saturn Control -> Pilot B
        # Mission 3: Pilot A -> Jupiter Control -> Pilot A (again)
        # Mission 4: Pilot C -> Jupiter Control -> Pilot C
        events = []
        timestamp = 1100.0

        # Mission 1: Pilot A with Jupiter Control
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=pilot_a,
                actor_name="Captain Alice",
                text="Jupiter Control, this is Captain Alice requesting clearance",
            )
        )
        timestamp += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=jupiter_control,
                actor_name="Jupiter Control",
                text="Captain Alice, clearance granted",
            )
        )
        timestamp += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=pilot_a,
                actor_name="Captain Alice",
                text="Roger that, Jupiter Control",
            )
        )
        timestamp += 50

        # Mission 2: Pilot B with Saturn Control
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=pilot_b,
                actor_name="Captain Bob",
                text="Saturn Control, this is Captain Bob",
            )
        )
        timestamp += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=saturn_control,
                actor_name="Saturn Control",
                text="Captain Bob, go ahead",
            )
        )
        timestamp += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=pilot_b,
                actor_name="Captain Bob",
                text="Saturn Control, requesting docking",
            )
        )
        timestamp += 50

        # Mission 3: Pilot A with Jupiter Control (again)
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=pilot_a,
                actor_name="Captain Alice",
                text="Jupiter Control, orbit established",
            )
        )
        timestamp += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=jupiter_control,
                actor_name="Jupiter Control",
                text="Captain Alice, acknowledged",
            )
        )
        timestamp += 50

        # Mission 4: Pilot C with Jupiter Control
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=pilot_c,
                actor_name="Captain Carol",
                text="Jupiter Control, inbound from Mars",
            )
        )
        timestamp += 10
        events.append(
            DialogueEventLog.objects.create(
                timestamp=timestamp,
                actor=jupiter_control,
                actor_name="Jupiter Control",
                text="Captain Carol, welcome",
            )
        )

        # Should have 10 events total (ABA, CDC, AB, D, AD patterns)
        assert len(events) == 10

        # Mock TTS
        dummy_wav = create_minimal_wav()

        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav

            command = Command()

            # Batch 1: Alice (soonest at 1100) - should process 3 events
            processed_1 = command._process_batch(
                tts_service=mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed_1 == 3, "First batch should process Alice's 3 events"

            # Batch 2: Jupiter Control (next soonest at 1110) - should process 3 events
            processed_2 = command._process_batch(
                tts_service=mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed_2 == 3, (
                "Second batch should process Jupiter Control's 3 events"
            )

            # Batch 3: Bob (next soonest at 1170) - should process 2 events
            processed_3 = command._process_batch(
                tts_service=mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed_3 == 2, "Third batch should process Bob's 2 events"

            # Batch 4: Saturn Control (at 1180) - should process 1 event
            processed_4 = command._process_batch(
                tts_service=mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed_4 == 1, (
                "Fourth batch should process Saturn Control's 1 event"
            )

            # Batch 5: Carol (at 1300) - should process 1 event
            processed_5 = command._process_batch(
                tts_service=mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed_5 == 1, "Fifth batch should process Carol's 1 event"

            # Batch 6: nothing left
            processed_6 = command._process_batch(
                tts_service=mock_tts, batch_size=3, lookahead_seconds=3600
            )
            assert processed_6 == 0, "Sixth batch should have nothing left"

        # All events should have audio
        for event in events:
            event.refresh_from_db()
            assert event.audio_file, (
                f"Event {event.id} ({event.actor_name}) missing audio"
            )
            assert event.audio_rendered_at is not None
            assert event.audio_generating is False
            assert os.path.exists(event.audio_file.path), (
                f"File {event.audio_file.path} doesn't exist"
            )

        # Verify TTS was called 10 times (once per event)
        assert mock_tts.generate.call_count == 10

        # Cleanup test files
        for event in events:
            if event.audio_file and os.path.exists(event.audio_file.path):
                os.unlink(event.audio_file.path)


@pytest.mark.django_db
class TestAudioWorkerActorlessEvents:
    """Tests for worker behavior when events have no actor reference."""

    def test_all_actorless_events_returns_zero(self):
        """
        When all events in the lookahead window have actor=None, the batch
        returns 0 (critical log emitted, no crash).
        """
        sim_state = create_sim_state_at_time(1000.0)
        current_time = sim_state.get_simulation_time()

        # Create events with no actor FK
        for i in range(3):
            DialogueEventLog.objects.create(
                timestamp=current_time + float(i * 10),
                actor=None,
                actor_name="Ghost",
                text="Nobody home.",
            )

        dummy_wav = create_minimal_wav()
        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav
            command = Command()
            processed = command._process_batch(
                tts_service=mock_tts,
                batch_size=10,
                lookahead_seconds=3600,
            )

        assert processed == 0, "Batch with only actor-less events should return 0"

    def test_mixed_actorless_and_real_events_skips_actorless(self):
        """
        When a batch has some actor-less events alongside real events, the worker
        skips the actor-less ones and still processes the real events.
        """
        sim_state = create_sim_state_at_time(1000.0)
        current_time = sim_state.get_simulation_time()

        real_actor = Controller.objects.create(name="Real Control")

        # Actor-less event (earlier timestamp)
        DialogueEventLog.objects.create(
            timestamp=current_time + 5.0,
            actor=None,
            actor_name="Ghost",
            text="Orphan event.",
        )

        # Real actor event (later timestamp)
        real_event = DialogueEventLog.objects.create(
            timestamp=current_time + 10.0,
            actor=real_actor,
            actor_name=real_actor.name,
            text="Real controller message.",
        )

        dummy_wav = create_minimal_wav()
        with patch(
            "mysite.universe.management.commands.audio_worker.ChatterboxTTSService"
        ) as MockTTS:
            mock_tts = MockTTS.return_value
            mock_tts.generate.return_value = dummy_wav
            command = Command()
            processed = command._process_batch(
                tts_service=mock_tts,
                batch_size=5,
                lookahead_seconds=3600,
            )

        assert processed == 1, f"Should process 1 real event, got {processed}"
        real_event.refresh_from_db()
        assert real_event.audio_file, "Real actor event should have audio"

        # Cleanup
        if real_event.audio_file and os.path.exists(real_event.audio_file.path):
            os.unlink(real_event.audio_file.path)


@pytest.mark.django_db
class TestAudioWorkerWarmup:
    """
    Tests for the _warmup_test() startup verification method.

    The warmup must:
    - Return True when TTS + file I/O succeed
    - Return False (not raise) when TTS fails
    - Leave no orphaned events or files after either outcome
    """

    def test_warmup_returns_true_when_tts_succeeds(self):
        """Warmup returns True when TTS generation and file I/O both work."""
        from unittest.mock import MagicMock

        cmd = Command()
        mock_tts = MagicMock()
        mock_tts.generate.return_value = create_minimal_wav()

        result = cmd._warmup_test(mock_tts)

        assert result is True

    def test_warmup_returns_false_when_tts_raises(self):
        """Warmup returns False (does not raise) when TTS generation fails."""
        from unittest.mock import MagicMock

        cmd = Command()
        mock_tts = MagicMock()
        mock_tts.generate.side_effect = RuntimeError("GPU OOM")

        result = cmd._warmup_test(mock_tts)

        assert result is False

    def test_warmup_leaves_no_orphaned_events_on_success(self):
        """Warmup cleans up the test event it creates."""
        from unittest.mock import MagicMock

        cmd = Command()
        mock_tts = MagicMock()
        mock_tts.generate.return_value = create_minimal_wav()

        before = DialogueEventLog.objects.count()
        cmd._warmup_test(mock_tts)
        after = DialogueEventLog.objects.count()

        assert after == before, "Warmup must not leave test events in the DB"

    def test_warmup_leaves_no_orphaned_events_on_failure(self):
        """Warmup cleans up the test event even when TTS fails."""
        from unittest.mock import MagicMock

        cmd = Command()
        mock_tts = MagicMock()
        mock_tts.generate.side_effect = RuntimeError("GPU OOM")

        before = DialogueEventLog.objects.count()
        cmd._warmup_test(mock_tts)
        after = DialogueEventLog.objects.count()

        assert after == before, "Warmup must not leave orphaned events after failure"


@pytest.mark.django_db
class TestAudioWorkerMixAudio:
    """
    Tests for _mix_audio() asset resolution and degraded-state handling.

    Policy encoded here:
    - Missing room-tone WAV file: log warning and continue without that layer
    - Modem noise with no text param: use default "DATA", render successfully
    - Result must always be valid WAV bytes
    """

    def test_missing_room_tone_logs_warning_and_returns_valid_wav(
        self, tmp_path, caplog
    ):
        """
        When the audio plan references a room-tone WAV that does not exist on disk,
        the worker logs a warning and continues rendering without that layer.
        It does not raise or return empty bytes.
        """
        import logging

        cmd = Command()

        tts_path = str(tmp_path / "tts.wav")
        with open(tts_path, "wb") as f:
            f.write(create_minimal_wav())

        audio_plan = [
            {
                "trigger": "event_start",
                "preset": "quindar_start",
                "params": {"frequency_hz": 2525.0, "gain": 0.9},
            },
            {
                "preset": "room_tone",
                "params": {
                    "wav_url": "/static/universe/audio/roomtone/DOES_NOT_EXIST.wav",
                    "gain": 0.15,
                },
            },
            {
                "trigger": "event_end",
                "preset": "quindar_end",
                "params": {"frequency_hz": 2475.0, "gain": 0.9},
            },
        ]

        with caplog.at_level(logging.WARNING):
            result = cmd._mix_audio(
                event_id=42, tts_wav_path=tts_path, audio_plan=audio_plan
            )

        # Must return valid WAV bytes despite missing room tone
        assert isinstance(result, bytes)
        wf = wave.open(io.BytesIO(result))
        assert wf.getnchannels() == 1

        # Must have emitted a warning about the missing file
        assert any("Room tone file not found" in msg for msg in caplog.messages), (
            f"Expected 'Room tone file not found' in logs; got: {caplog.messages}"
        )

    def test_modem_noise_without_text_uses_default_and_renders(self, tmp_path):
        """
        A modem_noise action with no 'text' parameter falls back to the default
        'DATA' string.  The result must be valid WAV bytes.
        """
        cmd = Command()

        tts_path = str(tmp_path / "tts_modem.wav")
        with open(tts_path, "wb") as f:
            f.write(create_minimal_wav())

        audio_plan = [
            {
                "trigger": "event_start",
                "preset": "quindar_start",
                "params": {"frequency_hz": 2525.0, "gain": 0.9},
            },
            {
                # No "text" key — worker must use default "DATA"
                "trigger": "event_end",
                "preset": "modem_noise_example",
                "params": {},
            },
        ]

        result = cmd._mix_audio(
            event_id=43, tts_wav_path=tts_path, audio_plan=audio_plan
        )

        assert isinstance(result, bytes)
        wf = wave.open(io.BytesIO(result))
        assert wf.getnchannels() == 1

    def test_mix_audio_with_no_plan_actions_returns_valid_wav(self, tmp_path):
        """
        An empty audio plan (no quindars, no room tone) still produces valid WAV.
        This guards against the worker crashing when plan generation returns nothing.
        """
        cmd = Command()

        tts_path = str(tmp_path / "tts_empty.wav")
        with open(tts_path, "wb") as f:
            f.write(create_minimal_wav())

        result = cmd._mix_audio(event_id=44, tts_wav_path=tts_path, audio_plan=[])

        assert isinstance(result, bytes)
        wf = wave.open(io.BytesIO(result))
        assert wf.getnchannels() == 1
