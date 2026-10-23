from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.errors import ApiError
from apps.audit.models import record

from . import throttle

FAIL_WINDOW = 15 * 60
MAX_USER_FAILS, MAX_IP_FAILS = 5, 20
GENERIC = "Invalid username or password for this portal."


def user_payload(user):
    return {
        "id": str(user.uuid),
        "username": user.username,
        "name": user.display_name,
        "role": user.role,
        "department": {"code": user.department.code, "name": user.department.name} if user.department else None,
        "must_change_password": user.must_change_password,
    }


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"ok": True})


# DRF only enforces CSRF for authenticated sessions; login/logout must be protected explicitly (login CSRF).
@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """Portal-specific login (plan 2.1.1): the role is fixed by the URL, never by the client."""

    permission_classes = [AllowAny]
    role = None

    def post(self, request):
        username = str(request.data.get("username", "")).strip()[:150]
        password = str(request.data.get("password", ""))
        ip = request.META.get("REMOTE_ADDR", "")
        ukey, ikey = f"loginfail:{self.role}:{username.lower()}", f"loginfail-ip:{ip}"

        current = request.user
        if current and current.is_authenticated:
            if current.role == self.role:
                return Response(user_payload(current))
            raise ApiError(409, "other_portal_session",
                           "You are signed in to the other portal. Return to it or sign out first.",
                           extra={"role": current.role})

        try:  # shared, atomic slot reservation before any password check (apps/accounts/throttle.py)
            user_n, ip_n = throttle.reserve(ukey, FAIL_WINDOW), throttle.reserve(ikey, FAIL_WINDOW)  # both always counted
        except DatabaseError:  # fail closed: never check passwords without the shared counter
            raise ApiError(503, "login_unavailable", "Sign-in is temporarily unavailable. Try again shortly.")
        if user_n > MAX_USER_FAILS or ip_n > MAX_IP_FAILS:
            raise ApiError(429, "rate_limited", "Too many failed attempts. Try again in 15 minutes.")
        user = authenticate(request, username=username, password=password) if username and password else None
        if user is None or not user.is_active or user.role != self.role:
            raise ApiError(400, "invalid_credentials", GENERIC)  # the reserved slots stay counted as failures
        throttle.clear(ukey)
        throttle.release(ikey)
        throttle.prune()  # housekeeping: expired windows already count as zero
        login(request, user)
        record(user, "login", user, {"portal": self.role}, request)
        return Response(user_payload(user))


class DeanLoginView(LoginView):
    role = "DEAN"


class VCLoginView(LoginView):
    role = "VC"


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({"ok": True})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_payload(request.user))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current, new = str(request.data.get("current_password", "")), str(request.data.get("new_password", ""))
        if not user.check_password(current):
            raise ApiError(400, "invalid", "Current password is incorrect.",
                           {"current_password": ["Current password is incorrect."]})
        if current == new:
            raise ApiError(400, "invalid", "Choose a different password.", {"new_password": ["Must differ."]})
        try:
            validate_password(new, user)
        except ValidationError as e:
            raise ApiError(400, "invalid", "Password is too weak.", {"new_password": list(e.messages)})
        user.set_password(new)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, user)
        record(user, "password_changed", user, request=request)
        return Response(user_payload(user))
