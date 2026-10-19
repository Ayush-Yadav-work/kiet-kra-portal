"""Bulk approval (VC plan v2.3 §9–9.0, D-075).

1. `prepare` freezes a manifest of exact (submission, current submitted revision) pairs — from the VC's selected rows or
   from every eligible row matching the progress filters — and returns it for review. Nothing is approved yet.
2. `confirm` (once, before `expires_at`) commits the VC to that manifest. Later submissions are never added.
3. `process_next` approves at most BULK_BATCH_SIZE unprocessed items per request, one transaction per item, through the
   existing `services.review` (same locks, exact-revision check, audit and approved-PDF job). Items are claimed with
   SELECT … FOR UPDATE SKIP LOCKED in position order, so two tabs or a repeated request never review an item twice; an
   outcome, once stored, is final. Stale revisions and no-longer-submitted reports are recorded as conflicts/skips.
"""
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import Count
from django.utils import timezone

from apps.audit.errors import ApiError
from apps.audit.models import record

from . import progress
from . import services as svc
from .models import BulkApproval, BulkApprovalItem, Status, Submission

Outcome = BulkApprovalItem.Outcome


def _key(value):
    key = str(value or "").strip()
    if not key or len(key) > 64:
        raise ApiError(400, "invalid", "A request key is required.", {"idempotency_key": ["1–64 characters."]})
    return key


def _selected(items):
    if not isinstance(items, list) or not items:
        raise ApiError(400, "invalid", "Select at least one report.", {"items": ["Required."]})
    if len(items) > settings.BULK_MANIFEST_CAP:
        raise ApiError(400, "too_many", f"At most {settings.BULK_MANIFEST_CAP} reports per approval; narrow the selection.")
    pairs, excluded = [], []
    try:
        wanted = {str(i["submission"]): str(i["revision"]) for i in items}
    except (TypeError, KeyError):
        raise ApiError(400, "invalid", "Each item needs submission and revision.", {"items": ["Invalid."]})
    subs = {str(s.pk): s for s in Submission.objects.filter(pk__in=list(wanted)).select_related(
        "assignment__department", "assignment__kra", "period")}
    for sid, rid in wanted.items():
        s = subs.get(sid)
        if s is None:
            excluded.append({"submission": sid, "reason": "not found"})
        elif s.status != Status.SUBMITTED:
            excluded.append({"submission": sid, "reason": f"not awaiting review ({s.get_status_display().lower()})"})
        elif str(s.current_revision_id) != rid:
            excluded.append({"submission": sid, "reason": "a newer revision was submitted; review it again"})
        else:
            pairs.append((s.pk, s.current_revision_id, s.assignment.kra.number, s.assignment.department.code))
    return pairs, excluded


def _filtered(query):
    f = progress.parse_filters(query)
    f["status"] = Status.SUBMITTED  # only reports awaiting review are eligible, whatever status filter was shown
    rows, _ = progress.build(f)
    pairs = [(r["submission_id"], r["revision_id"], r["kra_number"], r["department"]) for r in rows if r["revision_id"]]
    if len(pairs) > settings.BULK_MANIFEST_CAP:
        raise ApiError(400, "too_many", f"{len(pairs)} reports match; at most {settings.BULK_MANIFEST_CAP} per approval. "
                       "Narrow the filters (nothing was selected).")
    return pairs, progress.filters_json(f)


def prepare(user, data, request=None, retry_of=None):
    key = _key(data.get("idempotency_key"))
    existing = BulkApproval.objects.filter(actor=user, idempotency_key=key).first()
    if existing:  # repeated click/lost response: same manifest
        return existing, []
    scope = data.get("scope")
    if scope == "selection":
        pairs, excluded = _selected(data.get("items"))
        filters = {"description": "Selected reports"}
        if isinstance(data.get("filters"), dict):
            filters.update({k: str(v)[:100] for k, v in data["filters"].items() if k in ("year", "period", "department", "kra", "search")})
    elif scope == "filtered":
        pairs, filters = _filtered(data.get("filters") if isinstance(data.get("filters"), dict) else {})
        excluded = []
    else:
        raise ApiError(400, "invalid", "Choose selected reports or all matching filters.", {"scope": ["selection or filtered"]})
    if not pairs:
        raise ApiError(409, "nothing_eligible", "No selected report is awaiting review; nothing to approve.", extra={"excluded": excluded})
    pairs.sort(key=lambda p: (p[2], p[3]))  # KRA, department: a stable, reviewable order
    at = timezone.now()
    with transaction.atomic():
        bulk, created = BulkApproval.objects.get_or_create(actor=user, idempotency_key=key, defaults=dict(
            scope=BulkApproval.Scope.SELECTION if scope == "selection" else BulkApproval.Scope.FILTERED, filters=filters,
            total=len(pairs), created_at=at, expires_at=at + timedelta(minutes=settings.BULK_CONFIRM_MINUTES),
            retry_of=retry_of))
        if created:
            BulkApprovalItem.objects.bulk_create([BulkApprovalItem(bulk=bulk, position=i, submission_id=s, revision_id=r)
                                                  for i, (s, r, _, _) in enumerate(pairs)])
            record(user, "bulk_approval.prepare", bulk, {"scope": bulk.scope, "total": bulk.total, "filters": filters}, request)
    return bulk, excluded


def owned(user, pk):
    bulk = BulkApproval.objects.filter(pk=pk, actor=user).first()
    if bulk is None:  # another VC's manifest (or none) is indistinguishable from a missing one
        raise ApiError(404, "not_found", "Not found.")
    return bulk


def confirm(user, pk, request=None):
    with transaction.atomic():
        bulk = BulkApproval.objects.select_for_update().get(pk=owned(user, pk).pk)
        if bulk.confirmed_at:
            return bulk  # double confirmation: no-op
        if timezone.now() >= bulk.expires_at:
            raise ApiError(409, "expired", "This selection expired before it was confirmed. Select the reports again.")
        bulk.confirmed_at = timezone.now()
        bulk.save(update_fields=["confirmed_at"])
        record(user, "bulk_approval.confirm", bulk, {"total": bulk.total}, request)
    return bulk


def _approve(user, item, request):
    """One item, one transaction. Returns (outcome, reason, decision)."""
    try:
        sub, rd = svc.review(user, item.submission_id, item.revision_id, "APPROVE", "", False, request)
        return Outcome.APPROVED, "", rd
    except ApiError as e:
        if e.code == "stale_revision":
            return Outcome.CONFLICT, "A newer revision was submitted after selection; review it separately.", None
        if e.code == "invalid_state":
            cur = Submission.objects.filter(pk=item.submission_id).values_list("status", flat=True).first()
            label = dict(Status.choices).get(cur, cur or "unknown").lower()
            return Outcome.SKIPPED, f"No longer awaiting review (now {label}).", None
        return Outcome.FAILED, e.message[:300], None
    except DatabaseError:
        return Outcome.FAILED, "Database error; nothing was approved for this report. Retry later.", None


def process_next(user, pk, request=None):
    bulk = owned(user, pk)
    if not bulk.confirmed_at:
        raise ApiError(409, "not_confirmed", "Confirm the selection first.")
    if timezone.now() >= bulk.confirmed_at + timedelta(days=settings.BULK_RETENTION_DAYS) and not bulk.completed_at:
        raise ApiError(409, "expired", "This approval run is older than the resume window; select the reports again.")
    done = []
    for _ in range(settings.BULK_BATCH_SIZE):
        with transaction.atomic():
            item = (BulkApprovalItem.objects.select_for_update(skip_locked=True)
                    .filter(bulk=bulk, outcome=Outcome.PENDING).order_by("position").first())
            if item is None:
                break
            outcome, reason, rd = _approve(user, item, request)
            item.outcome, item.reason, item.decision, item.processed_at = outcome, reason, rd, timezone.now()
            item.save(update_fields=["outcome", "reason", "decision", "processed_at"])
            done.append(item)
    state = summary(bulk)
    if state["remaining"] == 0 and not bulk.completed_at:
        with transaction.atomic():
            b = BulkApproval.objects.select_for_update().get(pk=bulk.pk)
            if not b.completed_at:
                b.completed_at = timezone.now()
                b.save(update_fields=["completed_at"])
                record(user, "bulk_approval.complete", b, state["counts"], request)
        state = summary(bulk)
    batch = _with_context(BulkApprovalItem.objects.filter(pk__in=[i.pk for i in done])).order_by("position")
    return {**state, "batch": [item_json(i) for i in batch]}


def summary(bulk):
    bulk.refresh_from_db()
    counts = {o: 0 for o in ("APPROVED", "SKIPPED", "CONFLICT", "FAILED")}
    pending = 0
    for row in BulkApprovalItem.objects.filter(bulk=bulk).values("outcome").annotate(n=Count("id")):
        if row["outcome"]:
            counts[row["outcome"]] = row["n"]
        else:
            pending = row["n"]
    at = timezone.now()
    return {"id": str(bulk.pk), "scope": bulk.scope, "scope_label": bulk.get_scope_display(), "filters": bulk.filters,
            "total": bulk.total, "processed": bulk.total - pending, "remaining": pending, "counts": counts,
            "created_at": bulk.created_at, "expires_at": bulk.expires_at, "confirmed_at": bulk.confirmed_at,
            "completed_at": bulk.completed_at, "expired": (not bulk.confirmed_at and at >= bulk.expires_at),
            "resumable": bool(bulk.confirmed_at and pending and at < bulk.confirmed_at + timedelta(days=settings.BULK_RETENTION_DAYS)),
            "batch_size": settings.BULK_BATCH_SIZE}


def item_json(i):
    sub = i.submission
    a = sub.assignment
    return {"position": i.position, "submission": str(i.submission_id), "revision": str(i.revision_id),
            "revision_sequence": i.revision.sequence, "department": a.department.code, "kra": a.kra.number,
            "period": sub.period.label, "outcome": i.outcome or "PENDING", "reason": i.reason}


def _with_context(qs):
    return qs.select_related("revision", "submission__period", "submission__assignment__department", "submission__assignment__kra")


def items_page(bulk, outcome=None, page=1, size=50):
    qs = _with_context(BulkApprovalItem.objects.filter(bulk=bulk))
    if outcome:
        qs = qs.filter(outcome="" if outcome == "PENDING" else outcome)
    total = qs.count()
    start = (page - 1) * size
    return {"total": total, "page": page, "page_size": size, "results": [item_json(i) for i in qs[start:start + size]]}


def retry(user, pk, key, request=None):
    """A new manifest (needs its own confirmation) from this run's FAILED items whose exact revision is still awaiting
    review. Conflicts and skips are never retried automatically: they need a fresh look."""
    bulk = owned(user, pk)
    failed = list(BulkApprovalItem.objects.filter(bulk=bulk, outcome=Outcome.FAILED).values("submission_id", "revision_id"))
    if not failed:
        raise ApiError(409, "nothing_eligible", "No failed reports to retry.")
    items = [{"submission": str(f["submission_id"]), "revision": str(f["revision_id"])} for f in failed]
    return prepare(user, {"idempotency_key": key, "scope": "selection", "items": items, "filters": bulk.filters},
                   request, retry_of=bulk)
