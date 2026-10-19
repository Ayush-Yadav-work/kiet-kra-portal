"""Operator view of the approved-PDF queue (D-076).

    python backend/manage.py artifact_jobs                  # summary + failed jobs
    python backend/manage.py artifact_jobs --check          # exit 1 when no live worker, backlog or failed jobs
    python backend/manage.py artifact_jobs --retry-failed [ID ...]
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.reports import artifacts
from apps.reports.models import ApprovalArtifact


class Command(BaseCommand):
    help = "Show, check or retry approved-PDF artifact jobs."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true")
        parser.add_argument("--retry-failed", nargs="*", metavar="ID")

    def handle(self, *args, check=False, retry_failed=None, **opts):
        if retry_failed is not None:
            n = artifacts.retry_failed(retry_failed or None)
            self.stdout.write(f"requeued {n} failed job(s)")
        h = artifacts.health()
        self.stdout.write(json.dumps(h))
        for a in ApprovalArtifact.objects.filter(state=ApprovalArtifact.State.FAILED).order_by("updated_at")[:50]:
            self.stdout.write(f"FAILED {a.pk} revision={a.revision_id} attempts={a.attempts} error={a.last_error}")
        if check and not h["ok"]:
            raise CommandError("artifact worker unhealthy: " + ", ".join(h["problems"]))
