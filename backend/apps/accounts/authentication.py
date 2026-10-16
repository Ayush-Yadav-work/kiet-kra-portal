from rest_framework.authentication import SessionAuthentication


class SessionAuthentication401(SessionAuthentication):
    """Session auth that yields 401 (not 403) for anonymous requests. Kept import-light: DRF loads it early."""

    def authenticate_header(self, request):
        return "Session"
