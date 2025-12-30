import pytest
from django.utils import timezone

from mysite.universe.views import events as events_views
from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.actor import Actor


@pytest.mark.django_db(transaction=True)
def test_select_upcoming_respects_horizon(monkeypatch):
    # Horizon set small to make test deterministic
    monkeypatch.setattr(events_views, "_AUDIO_PREFETCH_HORIZON_SECONDS", 60.0)
    monkeypatch.setattr(events_views, "_AUDIO_PREFETCH_MAX_EVENTS", 10)

    now = timezone.now().timestamp()
    actor_a = Actor.create(name="A")
    actor_b = Actor.create(name="B")
    actor_c = Actor.create(name="C")
    # inside horizon
    ev1 = DialogueEventLog.objects.create(timestamp=now + 10, actor_name=actor_a.name, text="t1", metadata={"actor_id": actor_a.id})
    ev2 = DialogueEventLog.objects.create(timestamp=now + 30, actor_name=actor_b.name, text="t2", metadata={"actor_id": actor_b.id})
    # outside horizon
    ev3 = DialogueEventLog.objects.create(timestamp=now + 120, actor_name=actor_c.name, text="t3", metadata={"actor_id": actor_c.id})

    res = list(events_views._select_upcoming_events(sim_time=now, limit=10))
    ids = [e.id for e in res]

    assert ev1.id in ids
    assert ev2.id in ids
    assert ev3.id not in ids

