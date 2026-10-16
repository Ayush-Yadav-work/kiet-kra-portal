"""Business rules for drafts, submission, review and reopening (plan sections 2.3, 4, 7).

Every mutating function locks the Submission row (SELECT ... FOR UPDATE) inside a transaction.
Time always comes from the server (`timezone.now()`), never from the client.
"""
import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.errors import ApiError
from apps.audit.models import record
from apps.reports.schema import validate_payload

from .models import ReopenGrant, ReopenRequest, ReviewDecision, Status, Submission, SubmissionRevision

GRANT = timedelta(hours=settings.REOPEN_GRANT_HOURS)
EDITABLE_STATUSES = (Status.DRAFT, Status.REJECTED)
NOT_SUBMITTED = "NOT_SUBMITTED"


def now():
    return timezone.now()


# ---------- read-side rules ----------

def active_grant(submission, at=None):
    at = at or now()
    return submission.grants.filter(starts_at__lte=at, expires_at__gt=at).order_by("-expires_at").first()


def window_open(submission, at=None):
    at = at or now()
    return submission.period.is_open(at) or active_grant(submission, at) is not None


def is_editable(submission, at=None):
    return submission.status in EDITABLE_STATUSES and window_open(submission, at)


def has_active_evidence(submission):
    return submission.evidence.filter(removed=False).exists()


def display_status(submission):
    """C11: an untouched Draft (edit_version 0, no active evidence) shows as Not submitted."""
    if submission is None:
        return NOT_SUBMITTED
    if submission.status == Status.DRAFT and submission.edit_version == 0 and not has_active_evidence(submission):
        return NOT_SUBMITTED
    return submission.status


def grant_option_available(submission, at=None):
    """C1: reject/return offers a 72-hour grant when the period is closed or closes within 72 hours."""
    at = at or now()
    return submission.period.closes_at - at < GRANT


def snapshot_of(submission):
    a = submission.assignment
    tv = a.template_version
    return {
        "department": {"code": a.department.code, "name": a.department.name},
        "kra": {"number": a.kra.number, "activity_text": a.kra.activity_text, "nba_ref": a.kra.nba_ref,
                "naac_ref": a.kra.naac_ref},
        "target_text": a.target_text,
        "year": a.year.label,
        "period": {"index": submission.period.index, "label": submission.period.label},
        "template": {"key": tv.key, "version": tv.version} if tv else None,
    }


def evidence_manifest(submission):
    items = []
    for e in submission.evidence.filter(removed=False).order_by("uploaded_at"):
        items.append({"id": str(e.id), "source_type": e.source_type, "category": e.category, "label": e.label,
                      "original_filename": e.original_filename, "bytes": e.bytes, "checksum": e.checksum,
                      "drive_url": e.drive_url, "uploaded_at": e.uploaded_at.isoformat()})
    return items


# ---------- helpers ----------

def _locked(submission_id):
    return (Submission.objects.select_for_update(of=("self",))
            .select_related("assignment__department", "assignment__kra", "assignment__year",
                            "assignment__template_version", "period")
            .get(pk=submission_id))


def _check_version(sub, expected):
    if expected is None or int(expected) != sub.edit_version:
        raise ApiError(409, "version_conflict",
                       "This report was changed in another tab or session. Your typed values are kept; "
                       "reload the saved copy to continue.", extra={"edit_version": sub.edit_version})


def _require_editable(sub, at):
    if sub.status not in EDITABLE_STATUSES:
        raise ApiError(409, "not_editable", f"A {sub.get_status_display().lower()} report cannot be edited.")
    if not window_open(sub, at):
        raise ApiError(409, "window_closed",
                       "The reporting period is closed. Request reopening to make changes.")


# ---------- Dean actions ----------

def get_or_create_for_dean(user, assignment, period):
    """Rows are created only by a Dean action and only while the period is open (D-017)."""
    if period.year_id != assignment.year_id:
        raise ApiError(400, "invalid", "Period does not belong to the assignment year.")
    existing = Submission.objects.filter(assignment=assignment, period=period).first()
    if existing:
        return existing, False
    if not period.is_open(now()):
        return None, False
    try:
        with transaction.atomic():
            sub = Submission.objects.create(assignment=assignment, period=period, created_by=user)
    except IntegrityError:  # concurrent first open
        return Submission.objects.get(assignment=assignment, period=period), False
    record(user, "submission_created", sub)
    return sub, True


DRAFT_FIELDS = ("payload", "achievement_text", "remarks", "is_nil", "nil_reason")


def save_draft(user, submission_id, expected_version, changes, request=None):
    changes = {k: v for k, v in changes.items() if k in DRAFT_FIELDS}
    with transaction.atomic():
        sub = _locked(submission_id)
        at = now()
        _check_version(sub, expected_version)
        _require_editable(sub, at)
        if "payload" in changes:
            schema = sub.assignment.template_version.schema
            errors = validate_payload(schema, changes["payload"], strict=False)
            if errors:
                raise ApiError(400, "invalid", "Some values are not valid.", errors)
        for k in ("achievement_text", "remarks", "nil_reason"):
            if k in changes and not isinstance(changes[k], str):
                raise ApiError(400, "invalid", "Invalid value.", {k: ["Must be text."]})
        if len(changes.get("achievement_text", "")) > 500:
            raise ApiError(400, "invalid", "Achievement is too long.", {"achievement_text": ["Max 500 characters."]})
        if "is_nil" in changes and not isinstance(changes["is_nil"], bool):
            raise ApiError(400, "invalid", "Invalid value.", {"is_nil": ["Must be true or false."]})
        for k, v in changes.items():
            setattr(sub, k, v)
        sub.edit_version += 1
        sub.save()
        record(user, "draft_saved", sub, {"fields": sorted(changes), "edit_version": sub.edit_version}, request)
        return sub


def validation_errors(sub):
    """Strict submission validation: report fields + achievement + evidence minimum."""
    errors = {}
    if sub.is_nil:
        if not sub.nil_reason.strip():
            errors["nil_reason"] = ["A reason is required for a Nil submission."]
    else:
        errors.update(validate_payload(sub.assignment.template_version.schema, sub.payload, strict=True))
        if not sub.achievement_text.strip():
            errors["achievement_text"] = ["Enter the achievement for this period."]
        required = sub.assignment.template_version.schema.get("evidence", {}).get("required", [])
        present = set(sub.evidence.filter(removed=False).values_list("category", flat=True))
        missing = [c for c in required if c not in present]
        if missing:
            errors["evidence"] = [f"Add evidence for: {', '.join(missing)}."]
    return errors


def submit(user, submission_id, expected_version, request=None):
    with transaction.atomic():
        sub = _locked(submission_id)
        at = now()
        _check_version(sub, expected_version)
        _require_editable(sub, at)
        errors = validation_errors(sub)
        if errors:
            raise ApiError(400, "validation_failed", "Complete the highlighted items before submitting.", errors)
        manifest = evidence_manifest(sub)
        rev = SubmissionRevision.objects.create(
            submission=sub,
            sequence=sub.revisions.count() + 1,
            payload={} if sub.is_nil else sub.payload,
            is_nil=sub.is_nil,
            nil_reason=sub.nil_reason if sub.is_nil else "",
            achievement_text=sub.achievement_text,
            remarks=sub.remarks,
            snapshot=snapshot_of(sub),
            evidence_manifest=manifest,
            manifest_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            submitted_by=user,
            submitted_at=at,
        )
        sub.status = Status.SUBMITTED
        sub.current_revision = rev
        sub.save(update_fields=["status", "current_revision", "updated_at"])
        record(user, "submitted", sub, {"revision": rev.sequence}, request)
        return sub


def request_reopen(user, assignment, period, reason, request=None):
    """C2: creates the Draft row (edit_version 0) when none exists, then the request — atomically."""
    reason = (reason or "").strip()
    if not reason:
        raise ApiError(400, "invalid", "A reason is required.", {"reason": ["Required."]})
    if period.year_id != assignment.year_id:
        raise ApiError(400, "invalid", "Period does not belong to the assignment year.")
    with transaction.atomic():
        sub, created = Submission.objects.get_or_create(assignment=assignment, period=period,
                                                        defaults={"created_by": user})
        sub = _locked(sub.pk)
        at = now()
        if sub.period.is_open(at):
            raise ApiError(409, "period_open", "The period is still open; no reopening is needed.")
        if sub.status not in EDITABLE_STATUSES:
            raise ApiError(409, "not_editable", "Submitted or approved reports cannot be reopened by request.")
        if active_grant(sub, at):
            raise ApiError(409, "grant_active", "This report is already reopened.")
        if sub.reopen_requests.filter(state=ReopenRequest.State.PENDING).exists():
            raise ApiError(409, "request_pending", "A reopening request is already pending.")
        req = ReopenRequest.objects.create(submission=sub, reason=reason[:2000], requested_by=user, requested_at=at)
        record(user, "reopen_requested", sub, {"created_row": created}, request)
        return req


# ---------- VC actions ----------

def review(user, submission_id, revision_id, decision, reason, grant_reopen, request=None):
    reason = (reason or "").strip()
    with transaction.atomic():
        sub = _locked(submission_id)
        at = now()
        if not sub.current_revision_id or str(sub.current_revision_id) != str(revision_id):
            raise ApiError(409, "stale_revision", "This report has a newer revision. Reload before reviewing.")
        allowed = {"APPROVE": Status.SUBMITTED, "REJECT": Status.SUBMITTED, "RETURN": Status.APPROVED}
        if decision not in allowed:
            raise ApiError(400, "invalid", "Unknown decision.", {"decision": ["Invalid."]})
        if sub.status != allowed[decision]:
            raise ApiError(409, "invalid_state", f"Cannot {decision.lower()} a {sub.get_status_display().lower()} report.")
        if decision != "APPROVE" and not reason:
            raise ApiError(400, "invalid", "A reason is required.", {"reason": ["Required."]})
        do_grant = decision != "APPROVE" and bool(grant_reopen) and grant_option_available(sub, at)
        rd = ReviewDecision.objects.create(revision=sub.current_revision, reviewer=user,
                                           reviewer_name=user.display_name, decision=decision,
                                           reason=reason[:4000], granted_reopen=do_grant, created_at=at)
        sub.status = Status.APPROVED if decision == "APPROVE" else Status.REJECTED
        sub.save(update_fields=["status", "updated_at"])
        if do_grant:
            ReopenGrant.objects.create(submission=sub, starts_at=at, expires_at=at + GRANT, approved_by=user,
                                       source=ReopenGrant.Source.REVIEW, review_decision=rd)
        record(user, f"review_{decision.lower()}", sub, {"granted_reopen": do_grant}, request)
        return sub, rd


def decide_reopen(user, request_id, approve, reason, request=None):
    reason = (reason or "").strip()
    with transaction.atomic():
        req = ReopenRequest.objects.select_for_update().get(pk=request_id)
        sub = _locked(req.submission_id)
        at = now()
        if req.state != ReopenRequest.State.PENDING:
            raise ApiError(409, "already_decided", "This request was already decided.")
        if not approve and not reason:
            raise ApiError(400, "invalid", "A reason is required to deny.", {"reason": ["Required."]})
        req.state = ReopenRequest.State.APPROVED if approve else ReopenRequest.State.DENIED
        req.decided_by, req.decided_at, req.decision_reason = user, at, reason[:2000]
        req.save()
        grant = None
        if approve:
            grant = ReopenGrant.objects.create(submission=sub, starts_at=at, expires_at=at + GRANT, approved_by=user,
                                               source=ReopenGrant.Source.REQUEST, request=req)
        record(user, "reopen_approved" if approve else "reopen_denied", sub, request=request)
        return req, grant


def evidence_totals(submission):
    from apps.evidence.models import Evidence

    files = Evidence.objects.filter(submission=submission, source_type=Evidence.Source.FILE)
    return (files.filter(removed=False).aggregate(s=Sum("bytes"))["s"] or 0,
            files.aggregate(s=Sum("bytes"))["s"] or 0)
