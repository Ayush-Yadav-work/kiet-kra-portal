"""Durable approved-PDF artifacts (VC plan v2.3 §9.1, D-076).

Approval only writes an ApprovalArtifact row (PENDING) in its own transaction; no request waits for Chromium. The worker
(`manage.py run_artifact_worker`) claims one job at a time with a lease, renders it through the existing bounded renderer
from the frozen revision + decision snapshot, writes the file under a fresh key and publishes it by setting `storage_key`
in a transaction that re-checks its lease. A lost lease, crash or renderer outage leaves the job claimable again;
attempts are bounded with exponential backoff, after which the job is FAILED until an operator retries it.
"""
import hashlib
import logging
import os
import socket
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.errors import ApiError
from apps.evidence.storage import read_path, write_bytes

from .models import ApprovalArtifact, GeneratedDocument, WorkerHeartbeat

log = logging.getLogger("kra.artifacts")
State = ApprovalArtifact.State


def label_for(reviewer_name):
    return f"Verified by VC - {reviewer_name}"


def enqueue(decision):
    """Called inside the approval transaction: the job commits (or rolls back) with the decision."""
    rev = decision.revision
    tpl = rev.snapshot.get("template") or {}
    defaults = dict(submission_id=rev.submission_id, revision=rev, reviewer_name=decision.reviewer_name,
                    verified_at=decision.created_at, template_key=tpl.get("key", ""), template_version=tpl.get("version") or 0,
                    renderer_version=settings.RENDERER_VERSION, next_attempt_at=decision.created_at)
    old = legacy_document(decision)
    if old is not None:  # approved before D-076 and already rendered: keep that retained file, render nothing
        defaults.update(state=State.READY, storage_key=old.storage_key, bytes=old.bytes, content_hash=old.content_hash,
                        renderer_version=old.renderer_version, legacy_document=old, ready_at=old.created_at)
    art, _ = ApprovalArtifact.objects.get_or_create(decision=decision, defaults=defaults)
    return art


# ---------- worker side ----------

def worker_name():
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def beat(name, started_at, current=None, processed=0, stopped=False):
    now = timezone.now()
    WorkerHeartbeat.objects.update_or_create(name=name, defaults=dict(
        host=socket.gethostname(), pid=os.getpid(), started_at=started_at, beat_at=now,
        stopped_at=now if stopped else None, current_job=current, processed=processed))


def claim(owner, at=None):
    """Lease the next due job (PENDING, or RUNNING with an expired lease). SKIP LOCKED lets several workers share the
    queue without ever claiming the same row."""
    at = at or timezone.now()
    with transaction.atomic():
        job = (ApprovalArtifact.objects.select_for_update(skip_locked=True)
               .filter(Q(state=State.PENDING, next_attempt_at__lte=at) | Q(state=State.RUNNING, lease_expires_at__lt=at))
               .order_by("next_attempt_at", "created_at").first())
        if job is None:
            return None
        if job.attempts >= settings.ARTIFACT_MAX_ATTEMPTS:  # abandoned on its last attempt
            job.state, job.lease_owner, job.lease_expires_at = State.FAILED, "", None
            job.last_error = (job.last_error or "Worker stopped during the last attempt.")[:300]
            job.save()
            log.error("artifact %s failed permanently: %s", job.pk, job.last_error)
            return claim(owner, at)
        job.state, job.lease_owner = State.RUNNING, owner
        job.lease_expires_at = at + timedelta(seconds=settings.ARTIFACT_LEASE_SECONDS)
        job.attempts += 1
        job.save()
        return job


def render(job):
    """Build the PDF from immutable data only: the revision's payload/snapshot and the decision's frozen reviewer name."""
    from .pdf import call_renderer
    from .rendering import build_context, pdf_parts

    rev = job.revision
    sub = rev.submission
    tv = sub.assignment.template_version
    if (tv.key, tv.version) != (job.template_key, job.template_version):
        raise RuntimeError("Template version differs from the approved revision snapshot.")
    fmt = timezone.localtime(job.verified_at).strftime("%d %b %Y %H:%M IST")
    ctx = build_context(sub, rev, verified_as=(label_for(job.reviewer_name), True, fmt))
    return call_renderer(pdf_parts(ctx))


def finish(job, owner, data=None, error=None):
    """Publish or record a failure, but only while this worker still holds the lease."""
    key = None
    if data is not None:
        key = f"approved/{uuid.uuid4().hex}.pdf"  # fresh name per attempt: a published file is never overwritten
        write_bytes(key, data)
    with transaction.atomic():
        cur = ApprovalArtifact.objects.select_for_update().get(pk=job.pk)
        if cur.state != State.RUNNING or cur.lease_owner != owner:
            log.warning("artifact %s: lease lost, discarding this attempt", job.pk)
            if key:
                read_path(key).unlink(missing_ok=True)
            return cur
        cur.lease_owner, cur.lease_expires_at = "", None
        if key:
            cur.state, cur.storage_key, cur.bytes = State.READY, key, len(data)
            cur.content_hash, cur.ready_at, cur.last_error = hashlib.sha256(data).hexdigest(), timezone.now(), ""
        else:
            cur.last_error = str(error)[:300]
            if cur.attempts >= settings.ARTIFACT_MAX_ATTEMPTS:
                cur.state = State.FAILED
                log.error("artifact %s failed permanently after %s attempts: %s", cur.pk, cur.attempts, cur.last_error)
            else:
                delay = min(settings.ARTIFACT_BACKOFF_SECONDS * 2 ** (cur.attempts - 1), 900)
                cur.state, cur.next_attempt_at = State.PENDING, timezone.now() + timedelta(seconds=delay)
                log.warning("artifact %s attempt %s failed (%s); retry in %ss", cur.pk, cur.attempts, cur.last_error, delay)
        cur.save()
        return cur


def release(job, owner):
    """Graceful shutdown mid-job: give the lease back without spending the attempt."""
    with transaction.atomic():
        cur = ApprovalArtifact.objects.select_for_update().get(pk=job.pk)
        if cur.state == State.RUNNING and cur.lease_owner == owner:
            cur.state, cur.lease_owner, cur.lease_expires_at = State.PENDING, "", None
            cur.attempts = max(cur.attempts - 1, 0)
            cur.next_attempt_at = timezone.now()
            cur.save()


def run_one(owner):
    """Claim and process one job; returns the job's final row or None when nothing is due."""
    job = claim(owner)
    return None if job is None else process(job, owner)


def process(job, owner):
    try:
        data = render(job)
    except ApiError as e:
        return finish(job, owner, error=f"{e.code}: {e.message}")
    except Exception as e:  # noqa: BLE001 - any render failure is recorded and retried, never crashes the worker
        log.exception("artifact %s render error", job.pk)
        return finish(job, owner, error=f"{type(e).__name__}: {e}")
    return finish(job, owner, data=data)


def retry_failed(ids=None):
    """Operator action: put FAILED jobs back in the queue with a fresh attempt budget."""
    qs = ApprovalArtifact.objects.filter(state=State.FAILED)
    if ids:
        qs = qs.filter(pk__in=ids)
    return qs.update(state=State.PENDING, attempts=0, next_attempt_at=timezone.now(), last_error="")


def health(at=None):
    at = at or timezone.now()
    stale = timedelta(seconds=settings.ARTIFACT_HEARTBEAT_STALE_SECONDS)
    beats = list(WorkerHeartbeat.objects.filter(stopped_at__isnull=True, beat_at__gte=at - stale))
    pending = ApprovalArtifact.objects.filter(state__in=[State.PENDING, State.RUNNING]).count()
    failed = ApprovalArtifact.objects.filter(state=State.FAILED).count()
    oldest = (ApprovalArtifact.objects.filter(state__in=[State.PENDING, State.RUNNING]).order_by("created_at")
              .values_list("created_at", flat=True).first())
    problems = []
    if not beats:
        problems.append("no_live_worker")
    if pending > settings.ARTIFACT_BACKLOG_WARN:
        problems.append("backlog")
    if failed:
        problems.append("failed_jobs")
    return {"ok": not problems, "problems": problems, "live_workers": len(beats), "pending": pending, "failed": failed,
            "oldest_pending_seconds": int((at - oldest).total_seconds()) if oldest else 0}


# ---------- download side ----------

def approval_for(submission, revision):
    """The approval decision whose artifact answers an export, or None when the export is not an approved document.
    Current export: only while the submission is Approved on its current revision. Explicit revision: any revision that
    received an approval (its original artifact, unchanged by a later return)."""
    from apps.submissions.models import ReviewDecision, Status

    rev = revision or submission.current_revision
    if rev is None:
        return None
    if revision is None and not (submission.status == Status.APPROVED and rev.id == submission.current_revision_id):
        return None
    return rev.decisions.filter(decision=ReviewDecision.Decision.APPROVE).order_by("-created_at").first()


def artifact_for(decision):
    """Ensure the job exists (approvals recorded before D-076 get one on first request) and return it."""
    try:
        return decision.artifact
    except ApprovalArtifact.DoesNotExist:
        with transaction.atomic():
            return enqueue(decision)


def legacy_document(decision):
    """An identical approved PDF rendered before D-076, reused instead of rendering again."""
    return (GeneratedDocument.objects.filter(revision=decision.revision, status_snapshot="APPROVED",
                                             verification_label=label_for(decision.reviewer_name))
            .order_by("created_at").first())
