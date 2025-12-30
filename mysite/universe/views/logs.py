import logging
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from mysite.universe.services.log_buffer import get_log_handler


@require_GET
def logs_view(request):
    """
    Return recent logs (tail) and allow setting log level via ?level=INFO|DEBUG|WARN|ERROR.
    """
    level = request.GET.get("level")
    if level:
        try:
            logging.getLogger().setLevel(level.upper())
        except Exception:
            pass

    tail_n = int(request.GET.get("n", "200"))
    handler = get_log_handler()
    return JsonResponse({"logs": handler.tail(tail_n)})

