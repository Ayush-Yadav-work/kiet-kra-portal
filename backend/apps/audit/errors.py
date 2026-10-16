"""Consistent error envelope: {code, message, field_errors, request_id} (plan section 9)."""
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler


class ApiError(exceptions.APIException):
    """Business-rule error with an explicit code, e.g. ApiError(409, 'version_conflict', '...')."""

    def __init__(self, status_code, code, message, field_errors=None, extra=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field_errors = field_errors or {}
        self.extra = extra or {}
        super().__init__(message)


_CODES = {400: "invalid", 401: "not_authenticated", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
          409: "conflict", 413: "too_large", 429: "rate_limited"}


def exception_handler(exc, context):
    request = context.get("request")
    request_id = getattr(request, "request_id", None) if request else None
    if isinstance(exc, ApiError):
        body = {"code": exc.code, "message": exc.message, "field_errors": exc.field_errors, "request_id": request_id}
        body.update(exc.extra)
        return Response(body, status=exc.status_code)
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    response = drf_handler(exc, context)
    if response is None:
        return None
    field_errors, message = {}, ""
    if isinstance(response.data, dict) and "detail" in response.data:
        message = str(response.data["detail"])
    elif isinstance(response.data, (dict, list)):
        field_errors = response.data if isinstance(response.data, dict) else {"non_field_errors": response.data}
        message = "Invalid input."
    response.data = {"code": _CODES.get(response.status_code, "error"), "message": message,
                     "field_errors": field_errors, "request_id": request_id}
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        response.data["message"] = response.data["message"] or "Sign in required."
    return response
