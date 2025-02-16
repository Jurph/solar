from django.http import JsonResponse
from mysite.universe.models.event import Event

def event_feed(request):
    # Return events ordered by timestamp
    events = list(Event.objects.order_by("timestamp").values("id", "message", "timestamp"))
    return JsonResponse({"events": events})
