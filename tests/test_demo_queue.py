import time
from types import SimpleNamespace
from unittest.mock import patch

from mysite.universe.management.commands.character_dialogue_demo import DemoQueue
from mysite.universe.models.event import DialogueEvent, NavigationEvent
from mysite.universe.models.navigation import ManeuverType


class TestDemoQueue:
    def _make_dialogue(self, timestamp: float, text: str) -> DialogueEvent:
        actor = SimpleNamespace(name="Dummy Actor", id=1)
        return DialogueEvent(timestamp=timestamp, actor=actor, text=text)

    def _make_navigation(self, timestamp: float) -> NavigationEvent:
        target = SimpleNamespace(name="Dummy Target")
        return NavigationEvent(
            timestamp=timestamp,
            maneuver=ManeuverType.LAUNCH,
            target=target,
        )

    def test_events_processed_in_timestamp_order(self):
        q = DemoQueue(delay_seconds=0)
        q.add_event(self._make_dialogue(10.0, "third"))
        q.add_event(self._make_dialogue(1.0, "first"))
        q.add_event(self._make_dialogue(5.0, "second"))

        seen = []
        count = q.process_all_events(callback=lambda e: seen.append(e.text))

        assert count == 3
        assert seen == ["first", "second", "third"]
        assert q.peek_next_event() is None

    def test_callback_receives_navigation_and_dialogue_events(self):
        q = DemoQueue(delay_seconds=0)
        q.add_event(self._make_dialogue(1.0, "hello"))
        q.add_event(self._make_navigation(2.0))

        seen = []
        q.process_all_events(callback=lambda e: seen.append(type(e).__name__))

        assert seen == ["DialogueEvent", "NavigationEvent"]

    def test_sleep_between_events_when_delay_positive(self):
        q = DemoQueue(delay_seconds=2.5)
        q.add_event(self._make_dialogue(1.0, "one"))
        q.add_event(self._make_dialogue(2.0, "two"))
        q.add_event(self._make_dialogue(3.0, "three"))

        with patch.object(time, "sleep") as sleep_mock:
            q.process_all_events()

        assert sleep_mock.call_count == 2
        sleep_mock.assert_called_with(2.5)

    def test_process_all_events_instant_restores_delay(self):
        q = DemoQueue(delay_seconds=9.0)
        q.add_event(self._make_dialogue(1.0, "one"))
        q.add_event(self._make_dialogue(2.0, "two"))

        with patch.object(time, "sleep") as sleep_mock:
            count = q.process_all_events_instant()

        assert count == 2
        assert q.delay_seconds == 9.0
        sleep_mock.assert_not_called()

    def test_callback_exception_does_not_stop_replay(self):
        q = DemoQueue(delay_seconds=0)
        q.add_event(self._make_dialogue(1.0, "one"))
        q.add_event(self._make_dialogue(2.0, "two"))

        def flaky(event):
            raise RuntimeError("boom")

        count = q.process_all_events(callback=flaky)

        assert count == 0
        assert q.peek_next_event() is None
