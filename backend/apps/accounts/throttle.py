"""Login throttling in PostgreSQL (audit H1): one counter row per key, shared by all web workers, surviving restarts.

Each attempt *reserves* its slot before the password is checked: one atomic INSERT … ON CONFLICT … RETURNING increments
the counter (restarting it once its fixed window has ended), so concurrent requests can never check more passwords than
the limit. A successful login gives the slots back (the user key is cleared, the IP key decremented), so only failures
accumulate, as before. If the database cannot be reached, sign-in fails closed (the caller answers 503).
"""
from datetime import timedelta

from django.db import connection
from django.db.models import F
from django.utils import timezone

from .models import LoginThrottle

TABLE = LoginThrottle._meta.db_table
RESERVE = f"""
INSERT INTO {TABLE} (key, count, window_ends) VALUES (%s, 1, %s)
ON CONFLICT (key) DO UPDATE SET
  count = CASE WHEN {TABLE}.window_ends <= %s THEN 1 ELSE {TABLE}.count + 1 END,
  window_ends = CASE WHEN {TABLE}.window_ends <= %s THEN EXCLUDED.window_ends ELSE {TABLE}.window_ends END
RETURNING count"""


def reserve(key, window_seconds):
    """Count one attempt for `key`; returns the number of attempts in the current window, including this one."""
    at = timezone.now()
    with connection.cursor() as c:
        c.execute(RESERVE, [key, at + timedelta(seconds=window_seconds), at, at])
        return c.fetchone()[0]


def release(key):
    """Give back one slot (a successful attempt is not a failure)."""
    LoginThrottle.objects.filter(key=key, count__gt=0).update(count=F("count") - 1)


def clear(key):
    LoginThrottle.objects.filter(key=key).delete()


def prune():
    """Delete rows whose window has ended (run on each successful sign-in; expired rows are already ignored)."""
    return LoginThrottle.objects.filter(window_ends__lte=timezone.now()).delete()[0]

