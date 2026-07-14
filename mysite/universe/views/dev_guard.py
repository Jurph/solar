"""Helpers for state-changing views that are intentionally dev-only.

These endpoints are convenient for local debugging, but they are not meant to be
exposed in a production deployment. The guard keeps the deployment boundary
explicit by requiring the project-level dev-endpoint flag.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from django.conf import settings
from django.http import HttpRequest, JsonResponse, HttpResponseBase

P = ParamSpec("P")
R = TypeVar("R", bound=HttpResponseBase)


def state_changing_dev_only(view_func: Callable[P, R]) -> Callable[P, R | JsonResponse]:
    """Allow the wrapped view only when destructive dev endpoints are enabled.

    The setting defaults to ``DEBUG`` in ``mysite.settings`` so local development
    remains convenient, while production deployments can disable the endpoints
    explicitly.
    """

    @wraps(view_func)
    def _wrapped(
        request: HttpRequest, *args: P.args, **kwargs: P.kwargs
    ) -> R | JsonResponse:
        if not getattr(settings, "ALLOW_STATE_CHANGING_DEV_ENDPOINTS", settings.DEBUG):
            return JsonResponse(
                {
                    "status": "error",
                    "message": (
                        "This endpoint is disabled outside local development. "
                        "Set ALLOW_STATE_CHANGING_DEV_ENDPOINTS=True only for trusted dev environments."
                    ),
                },
                status=403,
            )

        return view_func(request, *args, **kwargs)

    return _wrapped
