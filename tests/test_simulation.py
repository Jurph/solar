"""
Tests for the simulation time system.

These tests verify the core time interpolation and re-anchoring logic
that drives the entire simulation timing system.
"""

import time
import unittest
from django.test import TestCase

from mysite.universe.models.simulation import SimulationState


class ReanchoringTests(TestCase):
    """
    Tests for the re-anchoring logic when time scale changes.

    When scale changes, we must:
    1. Calculate current sim time
    2. Set that as the new anchor_sim_time
    3. Set current wall time as new anchor_wall_clock
    4. Update the scale

    This ensures sim time doesn't "jump" when scale changes.
    """

    def setUp(self):
        """Clear simulation state before each test."""
        SimulationState.objects.all().delete()

    def test_scale_change_preserves_simulation_time(self):
        """
        Changing scale should not cause simulation time to jump.

        This is the CRITICAL test - if this fails, changing the time
        scale slider will cause events to suddenly appear or disappear.
        """
        state = SimulationState.objects.create(
            pk=1, anchor_sim_time=1000.0, anchor_wall_clock=time.time(), time_scale=1.0
        )

        sim_time_before = state.get_simulation_time()

        # Change scale from 1x to 60x
        state.set_time_scale(60.0)

        sim_time_after = state.get_simulation_time()

        # Time should be nearly the same (just re-anchored, not jumped)
        # At 1x before the change, overhead drift is negligible.
        self.assertAlmostEqual(sim_time_before, sim_time_after, delta=0.5)
        self.assertEqual(state.time_scale, 60.0)

    def test_scale_change_updates_anchors_correctly(self):
        """
        After scale change, anchors should reflect accumulated time.

        If anchor_sim_time isn't updated to current sim time,
        subsequent calculations will be wrong.
        """
        state = SimulationState.objects.create(
            pk=1,
            anchor_sim_time=1000.0,
            anchor_wall_clock=time.time() - 100.0,  # 100 seconds ago
            time_scale=1.0,
        )

        # Change scale - this should re-anchor
        state.set_time_scale(10.0)

        # New anchor_sim_time should be ~1100 (1000 + 100 seconds at 1x)
        self.assertAlmostEqual(state.anchor_sim_time, 1100.0, delta=2.0)

        # New anchor_wall_clock should be approximately now
        self.assertAlmostEqual(state.anchor_wall_clock, time.time(), delta=1.0)


class TimeMonotonicityTests(TestCase):
    """Tests that simulation time never goes backwards."""

    def setUp(self):
        """Clear simulation state before each test."""
        SimulationState.objects.all().delete()

    def test_time_always_increases(self):
        """
        Multiple calls to get_simulation_time should return increasing values.

        If time ever goes backwards, events could be processed twice
        or the UI would show confusing timestamps.
        """
        current_wall = time.time()

        state = SimulationState.objects.create(
            pk=1, anchor_sim_time=1000.0, anchor_wall_clock=current_wall, time_scale=1.0
        )

        times = []
        for _ in range(5):
            times.append(state.get_simulation_time())
            time.sleep(0.02)  # 20ms between samples

        # Each time should be >= previous
        for i in range(1, len(times)):
            self.assertGreaterEqual(
                times[i],
                times[i - 1],
                f"Time went backwards: {times[i]} < {times[i - 1]}",
            )


if __name__ == "__main__":
    unittest.main()
