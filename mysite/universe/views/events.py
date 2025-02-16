from django.http import JsonResponse
from django.shortcuts import render
from mysite.universe.models.event import Event

def event_feed(request):
    """
    API endpoint that returns simulation events as JSON.
    """
    events = list(Event.objects.order_by("timestamp").values("id", "message", "timestamp"))
    return JsonResponse({"events": events})

def event_scroller(request):
    """
    Renders the simulation event log page.
    """
    return render(request, "event_scroller.html") 