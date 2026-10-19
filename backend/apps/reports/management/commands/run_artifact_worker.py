"""Approved-PDF artifact worker (D-076). Run one per host (several are safe: jobs are leased with SKIP LOCKED).

    python backend/manage.py run_artifact_worker            # until SIGTERM/SIGINT
    python backend/manage.py run_artifact_worker --once     # drain due jobs, then exit (tests, cron fallback)

Stops after the current job on SIGTERM/SIGINT; a second signal (or Ctrl+C) gives the lease back immediately.
Database or renderer outages are retried; the process only exits on a signal.
"""
import logging
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection
from django.db.utils import DatabaseError
from django.utils import timezone

from apps.reports import artifacts

log = logging.getLogger("kra.artifacts")


class Command(BaseCommand):
    help = "Render approved-report PDFs from the durable artifact queue."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process every due job, then exit.")

    def handle(self, *args, once=False, **opts):
        name = artifacts.worker_name()
        started, processed, stopping = timezone.now(), 0, []

        def stop(signum, frame):
            if stopping:
                raise KeyboardInterrupt
            stopping.append(signum)
            log.info("worker %s: stopping after the current job", name)

        previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
        log.info("worker %s started (renderer %s, lease %ss, max attempts %s)", name, settings.RENDERER_URL,
                 settings.ARTIFACT_LEASE_SECONDS, settings.ARTIFACT_MAX_ATTEMPTS)
        try:
            while not stopping:
                try:
                    artifacts.beat(name, started, processed=processed)
                    job = artifacts.claim(name)
                    if job is None:
                        if once:
                            break
                        time.sleep(settings.ARTIFACT_POLL_SECONDS)
                        continue
                    artifacts.beat(name, started, current=job.pk, processed=processed)
                    try:
                        done = artifacts.process(job, name)
                    except BaseException:
                        artifacts.release(job, name)
                        raise
                    processed += 1
                    log.info("artifact %s -> %s (attempt %s)", done.pk, done.state, done.attempts)
                except DatabaseError:  # database restart/outage: reconnect and keep going
                    if once or connection.in_atomic_block:
                        raise
                    log.exception("worker %s: database error; retrying", name)
                    connection.close()
                    time.sleep(min(settings.ARTIFACT_POLL_SECONDS * 5, 30))
                finally:
                    if not connection.in_atomic_block:  # (tests run the command inside a transaction)
                        close_old_connections()
        except KeyboardInterrupt:
            log.info("worker %s interrupted", name)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            try:
                artifacts.beat(name, started, processed=processed, stopped=True)
            except DatabaseError:
                pass
            log.info("worker %s stopped after %s job(s)", name, processed)
