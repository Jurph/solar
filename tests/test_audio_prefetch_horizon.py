import pytest
from django.utils import timezone

from mysite.universe.views import events as events_views
from mysite.universe.models.event import DialogueEventLog


@pytest.mark.django_db(transaction=True)
def test_select_upcoming_respects_horizon(monkeypatch):
    # Horizon set small to make test deterministic
    monkeypatch.setattr(events_views, "_AUDIO_PREFETCH_HORIZON_SECONDS", 60.0)
    monkeypatch.setattr(events_views, "_AUDIO_PREFETCH_MAX_EVENTS", 10)

    now = timezone.now().timestamp()
    # inside horizon
    ev1 = DialogueEventLog.objects.create(timestamp=now + 10, actor_name="A", text="t1", metadata={})
    ev2 = DialogueEventLog.objects.create(timestamp=now + 30, actor_name="B", text="t2", metadata={})
    # outside horizon
    ev3 = DialogueEventLog.objects.create(timestamp=now + 120, actor_name="C", text="t3", metadata={})

    res = list(events_views._select_upcoming_events(sim_time=now, limit=10))
    ids = [e.id for e in res]

    assert ev1.id in ids
    assert ev2.id in ids
    assert ev3.id not in ids

