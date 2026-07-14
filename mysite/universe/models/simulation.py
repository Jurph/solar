"""
Simulation state model for tracking time progression.

The simulation uses a time-scaling system where:
- simulation_time = anchor_sim_time + (wall_clock_elapsed * time_scale)

This allows the simulation to run faster or slower than real-time.
"""

import time
from django.db import models


class SimulationState(models.Model):
    """
    Singleton model tracking simulation time state.

    The simulation time is calculated as:
        elapsed = time.time() - anchor_wall_clock
        sim_time = anchor_sim_time + (elapsed * time_scale)

    When time_scale changes, we re-anchor so the current sim time stays
    continuous but the rate changes.
    """

    anchor_sim_time = models.FloatField(
        default=0.0, help_text="Simulation time at the anchor point"
    )
    anchor_wall_clock = models.FloatField(
        help_text="Wall-clock Unix timestamp at the anchor point"
    )
    time_scale = models.FloatField(
        default=1.0,
        help_text="Time multiplier (1.0 = real-time, 60 = 1 min real = 1 hour sim)",
    )

    class Meta:
        verbose_name = "Simulation State"
        verbose_name_plural = "Simulation State"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls) -> "SimulationState":
        """Get or create the singleton simulation state."""
        now = time.time()
        instance, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                "anchor_sim_time": 0.0,
                "anchor_wall_clock": now,
                "time_scale": 1.0,
            },
        )
        return instance

    def reanchor_wall_clock(self, wall_clock: float | None = None) -> None:
        """Reset wall-clock anchor without advancing simulation time."""
        self.anchor_wall_clock = time.time() if wall_clock is None else wall_clock
        self.save(update_fields=["anchor_wall_clock"])

    def get_simulation_time(self) -> float:
        """Calculate current simulation time based on wall-clock and scale."""
        elapsed = time.time() - self.anchor_wall_clock
        return self.anchor_sim_time + (elapsed * self.time_scale)

    def set_time_scale(self, new_scale: float) -> None:
        """
        Change the time scale while keeping simulation time continuous.

        Re-anchors so the current simulation time stays the same,
        but future time advances at the new rate.
        """
        # Capture current simulation time before changing anything
        current_sim_time = self.get_simulation_time()

        # Re-anchor at current moment
        self.anchor_sim_time = current_sim_time
        self.anchor_wall_clock = time.time()
        self.time_scale = new_scale
        self.save()


def get_simulation_time() -> float:
    """Convenience function to get current simulation time."""
    return SimulationState.get_instance().get_simulation_time()
