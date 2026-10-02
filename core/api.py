"""Shared API helpers: consistent, friendly error responses."""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from services.ai_service import AIServiceError

logger = logging.getLogger("prepai.api")

AI_UNAVAILABLE_MESSAGE = "AI service is temporarily unavailable. Please try again."


def exception_handler(exc, context):
    """
    Wrap DRF's handler so every error has the shape
    {"error": {"message": str, "code": str, "details": ...}}.
    AI failures become 503s with a friendly message instead of a 500.
    """
    if isinstance(exc, AIServiceError):
        logger.warning("AI service error: %s", exc)
        return Response(
            {"error": {"message": exc.user_message or AI_UNAVAILABLE_MESSAGE,
                       "code": "ai_unavailable", "retryable": exc.retryable}},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {"error": {"message": "Something went wrong on our side. Please try again.",
                       "code": "server_error"}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    data = response.data
    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        message = str(data["detail"])
        details = None
    else:
        message = "Please correct the highlighted fields."
        details = data
    code = getattr(exc, "default_code", "error")
    if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        message = "You're doing that too often. Please wait a little and try again."
    response.data = {"error": {"message": message, "code": code, "details": details}}
    return response
