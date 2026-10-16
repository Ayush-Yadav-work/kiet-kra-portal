from rest_framework import permissions

from apps.audit.errors import ApiError


class _Role(permissions.BasePermission):
    role = None

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated and u.is_active and u.role == self.role):
            return False
        return _password_ok(u)


class IsDean(_Role):
    role = "DEAN"


class IsVC(_Role):
    role = "VC"


class IsDeanOrVC(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated and u.is_active and u.role in ("DEAN", "VC")):
            return False
        return _password_ok(u)


def _password_ok(user):
    if user.must_change_password:
        raise ApiError(403, "password_change_required", "Change your password before continuing.")
    return True
