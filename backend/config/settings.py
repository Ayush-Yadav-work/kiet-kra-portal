"""KIET KRA Portal settings. All secrets/environment specifics come from the environment or backend/.env."""
import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"Environment variable {name} is required")
    return value


DEBUG = env("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:5173").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "apps.accounts",
    "apps.catalogue",
    "apps.submissions",
    "apps.evidence",
    "apps.reports",
    "apps.audit",
]

MIDDLEWARE = [
    "apps.audit.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": False,
    "OPTIONS": {"context_processors": []},
}]
WSGI_APPLICATION = "config.wsgi.application"

_db = urlparse(env("DATABASE_URL", required=True))
if _db.scheme not in ("postgres", "postgresql"):
    raise ImproperlyConfigured("DATABASE_URL must point to PostgreSQL")
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": _db.path.lstrip("/"),
    "USER": _db.username,
    "PASSWORD": _db.password,
    "HOST": _db.hostname,
    "PORT": _db.port or 5432,
    "ATOMIC_REQUESTS": False,
}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"  # institutional timezone; DB timestamps stay UTC
USE_I18N = False
USE_TZ = True

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
# shortcut: locmem throttling is per-process, upgrade to a shared cache (DB/Redis) when running >1 Gunicorn worker.

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 3600
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"  # report preview HTML is shown in a same-origin sandboxed iframe
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_SSL_REDIRECT = env("DJANGO_SSL_REDIRECT", "1") == "1"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.SessionAuthentication401"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser", "rest_framework.parsers.MultiPartParser"],
    "EXCEPTION_HANDLER": "apps.audit.errors.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "UNAUTHENTICATED_USER": None,
}

# Private storage (D-015): never under a static/media URL.
PRIVATE_STORAGE_ROOT = Path(env("PRIVATE_STORAGE_ROOT", str(PROJECT_ROOT / ".work" / "private")))
EVIDENCE_MAX_FILE_BYTES = int(env("EVIDENCE_MAX_FILE_MB", "20")) * 1024 * 1024
EVIDENCE_MAX_ACTIVE_BYTES = int(env("EVIDENCE_MAX_ACTIVE_MB", "100")) * 1024 * 1024
EVIDENCE_MAX_HISTORY_BYTES = int(env("EVIDENCE_MAX_HISTORY_MB", "500")) * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

RENDERER_URL = env("RENDERER_URL", "http://127.0.0.1:8790")
RENDERER_TIMEOUT_SECONDS = float(env("RENDERER_TIMEOUT_SECONDS", "45"))
RENDERER_VERSION = "kiet-renderer-1"

REOPEN_GRANT_HOURS = 72
MAX_ACTIVITIES = int(env("KRA_MAX_ACTIVITIES", "20"))
MAX_TABLE_ROWS = int(env("KRA_MAX_TABLE_ROWS", "100"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
