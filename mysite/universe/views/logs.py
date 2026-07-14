import logging
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from mysite.universe.services.log_buffer import get_log_handler
from mysite.universe.views.dev_guard import state_changing_dev_only


@state_changing_dev_only
@require_GET
def logs_view(request):
    """
    Return recent logs (tail) and allow filtering by level via ?min_level=INFO|DEBUG|WARN|ERROR.
    Also allows setting root logger level via ?level=INFO|DEBUG|WARN|ERROR.

    Dev-only: gated by ALLOW_STATE_CHANGING_DEV_ENDPOINTS because ?level= can
    mutate the root logger and the buffer may contain sensitive LLM content.
    """
    # Set root logger level if requested
    level = request.GET.get("level")
    if level:
        try:
            logging.getLogger().setLevel(level.upper())
        except Exception:
            pass

    # Filter logs by minimum level if requested
    min_level = request.GET.get("min_level", "DEBUG")
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    min_level_no = level_map.get(min_level.upper(), logging.DEBUG)

    try:
        tail_n = int(request.GET.get("n", "200"))
    except (TypeError, ValueError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid n; must be a non-negative integer.",
            },
            status=400,
        )
    if tail_n < 0:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid n; must be a non-negative integer.",
            },
            status=400,
        )
    handler = get_log_handler()
    all_logs = handler.tail(tail_n)

    # Filter by minimum level
    filtered_logs = [
        log
        for log in all_logs
        if level_map.get(log["level"], logging.DEBUG) >= min_level_no
    ]

    return JsonResponse(
        {"logs": filtered_logs, "filtered": len(all_logs) - len(filtered_logs)}
    )
