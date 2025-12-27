"""
Audio plan construction (Python-side).

An "audio plan" is metadata attached to each dialogue event describing what
audio should play as that event is displayed. The browser should treat this as
an audio queue to stream alongside the text feed.

For now, plans reference named WAV presets served by `/api/audio/preset/<name>/`.
Later, this can evolve into richer per-event synthesis specs without changing
the front-end player contract.
"""

from __future__ import annotations

from typing import Any

from mysite.universe.models.event import DialogueEventLog


def build_audio_plan_for_dialogue_event(event: DialogueEventLog) -> list[dict[str, Any]]:
    """
    Build an audio plan for a single DialogueEventLog.

    Plan contract (v0):
    - List of actions, each action includes:
      - trigger: "event_start" | "event_end"
      - preset:  name of a Python-defined WAV preset (see views/audio.py)
    """
    # Default: Quindar tones bracketing the transmission.
    # This keeps the client generic and lets Python evolve the plan rules.
    return [
        {"trigger": "event_start", "preset": "quindar_start"},
        {"trigger": "event_end", "preset": "quindar_end"},
    ]


