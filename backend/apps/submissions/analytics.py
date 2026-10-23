"""VC report-approval analytics and department comparison (VC features plan v2.3 §6–8, Phase 1; D-074).

completion = approved applicable report slots / expected applicable report slots. A slot is one finalised assignment ×
one reporting period at or after its effective start period. Drafts/removed allocations never create slots; text
targets are never parsed. Every number, chart, table and export of one request comes from ONE materialised dataset read
inside an owned REPEATABLE READ, READ ONLY transaction (§8.1), then aggregated in Python.
"""
from django.db import connections, transaction
from django.db.models import Exists, OuterRef, Q, Subquery

from apps.audit.errors import ApiError
from apps.catalogue.models import KRA, AcademicYear, AnnualAssignment, Department, DraftAssignment, ReportingPeriod
from apps.evidence.models import Evidence

from .models import ReopenGrant, ReviewDecision, Submission
from .services import classify


def vc_bucket(*args):
    b = classify(*args)
    return "NOT_SUBMITTED" if b == "DRAFT" else b

# Draft privacy (D-078): analytics are VC-facing, so a saved but never-submitted draft counts as Not submitted.
BUCKETS = ("NOT_SUBMITTED", "AWAITING_REVIEW", "RETURNED", "REJECTED", "APPROVED", "NOT_DUE")
LABELS = {"NOT_SUBMITTED": "Not submitted", "AWAITING_REVIEW": "Awaiting review", "RETURNED": "Returned for correction",
          "REJECTED": "Rejected", "APPROVED": "Approved", "NOT_DUE": "Not due"}
SCOPES = {"period": "Bimonthly period", "ytd": "Year to date", "year": "Full academic year"}
MAX_EXPORT_ROWS = 5000  # exports refuse (never truncate) beyond this; the 13 × 45 × 6 full year is 3,510
MAX_FILTER_ITEMS = 200


class SnapshotError(RuntimeError):
    """Raised instead of silently reading at a weaker isolation level."""


def read_snapshot(fn, using="default"):
    """Run `fn` in a new REPEATABLE READ, READ ONLY transaction owned here. SET TRANSACTION must be the first statement of
    the transaction, so a caller's open transaction (or a request-wide one) is refused rather than downgraded. The
    settings are transaction-scoped: nothing leaks to later writes on the same connection."""
    conn = connections[using]
    if conn.in_atomic_block:
        raise SnapshotError("The analytics reader must own its transaction; call it outside transaction.atomic() "
                            "(views are wrapped with transaction.non_atomic_requests).")
    with transaction.atomic(using=using):
        with conn.cursor() as c:
            c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return fn()


def bad(message, field):
    return ApiError(400, "invalid_filter", message, field_errors={field: [message]})


def parse(q):
    """Validated filters (outside the snapshot): year, scope, period (bimonthly scope; must belong to the year),
    departments, KRAs, detail status, page."""
    year = AcademicYear.objects.filter(label=q.get("year", "")).first()
    if not year:
        raise bad("Choose a valid academic year.", "year")
    scope = q.get("scope") or "ytd"
    if scope not in SCOPES:
        raise bad("Choose bimonthly, year to date or full year.", "scope")
    period = None
    if scope == "period":
        try:
            period = ReportingPeriod.objects.get(pk=int(q.get("period", "")), year=year)
        except (ValueError, ReportingPeriod.DoesNotExist):
            raise bad(f"Choose a reporting period of {year.label}.", "period")
    depts = [d for d in q.getlist("department") if d]
    kras = [k for k in q.getlist("kra") if k]
    if len(depts) > MAX_FILTER_ITEMS or len(kras) > MAX_FILTER_ITEMS:
        raise bad("Too many filter values.", "department")
    if depts and Department.objects.filter(code__in=depts).count() != len(set(depts)):
        raise bad("Unknown department.", "department")
    try:
        kras = sorted({int(k) for k in kras})
    except ValueError:
        raise bad("KRA must be a number.", "kra")
    if kras and KRA.objects.filter(number__in=kras).count() != len(kras):
        raise bad("Unknown KRA.", "kra")
    status = q.get("status") or ""
    if status == "DRAFT":  # old bookmarks: drafts are part of Not submitted now (D-078)
        status = "NOT_SUBMITTED"
    if status and status not in BUCKETS:
        raise bad("Unknown status.", "status")
    try:
        page = max(int(q.get("page", 1) or 1), 1)
        size = min(max(int(q.get("page_size", 50) or 50), 10), 200)
    except ValueError:
        raise bad("Page must be a number.", "page")
    return {"year": year, "scope": scope, "period": period, "departments": sorted(set(depts)), "kras": kras, "status": status,
            "page": page, "page_size": size}


def filters_json(f):
    return {"year": f["year"].label, "scope": f["scope"], "scope_label": SCOPES[f["scope"]],
            "period": {"id": f["period"].id, "label": f["period"].label} if f["period"] else None,
            "departments": f["departments"], "kras": f["kras"], "status": f["status"]}


def load(f, as_of, between=None):
    """The materialised dataset: five bounded reads, no lazy access afterwards. `between` is a test seam to run a
    concurrent writer after the first read (proves the reads share one snapshot)."""
    year = f["year"]
    periods = list(ReportingPeriod.objects.filter(year=year).order_by("index").values("id", "index", "label", "opens_at", "closes_at"))
    assigned = AnnualAssignment.objects.filter(year=year)
    if f["departments"]:
        assigned = assigned.filter(department__code__in=f["departments"])
    if f["kras"]:
        assigned = assigned.filter(kra__number__in=f["kras"])
    assignments = list(assigned.order_by("kra__number", "department__code").values(
        "id", "department__code", "kra__number", "kra__activity_text", "target_text", "effective_start_period__index"))
    if between:
        between()
    subs = list(Submission.objects.filter(assignment__in=assigned.values("id"), period__year=year).annotate(
        has_ev=Exists(Evidence.objects.filter(submission=OuterRef("pk"), removed=False)),
        last_decision=Subquery(ReviewDecision.objects.filter(revision=OuterRef("current_revision"))
                               .order_by("-created_at").values("decision")[:1]),
        reopened=Exists(ReopenGrant.objects.filter(submission=OuterRef("pk"), starts_at__lte=as_of, expires_at__gt=as_of)),
    ).values("id", "assignment_id", "period_id", "status", "edit_version", "is_nil", "achievement_text", "has_ev", "last_decision",
             "reopened", "current_revision__achievement_text", "current_revision__is_nil", "current_revision__sequence"))
    drafts = DraftAssignment.objects.filter(year=year, finalized_assignment__isnull=True, removed_at__isnull=True)
    if f["departments"]:
        drafts = drafts.filter(department__code__in=f["departments"])
    if f["kras"]:
        drafts = drafts.filter(kra__number__in=f["kras"])
    depts = Department.objects.filter(code__in=f["departments"]) if f["departments"] else Department.objects.filter(
        Q(active=True) | Q(assignments__year=year)).distinct()
    return {"periods": periods, "assignments": assignments, "subs": subs, "drafts_pending": drafts.count(),
            "departments": list(depts.order_by("code").values("code", "name"))}


def rate(approved, expected, assignments, not_due=False):
    """Display rule (§6.1): one decimal; zero denominator is never shown as 0 % or 100 %."""
    if expected == 0:
        return {"rate": None, "rate_label": "No assignments" if assignments == 0 else "No applicable reporting periods"}
    if not_due:
        return {"rate": None, "rate_label": "Not due"}
    r = approved * 100 / expected
    return {"rate": r, "rate_label": f"{r:.1f}%"}


def compute(data, f, as_of):
    """Pure aggregation over the materialised dataset (unit-testable without a database)."""
    periods = data["periods"]
    sel = f["period"].id if f["period"] else None
    subs = {(s["assignment_id"], s["period_id"]): s for s in data["subs"]}
    slots = []  # every applicable slot of the year: (assignment, period, bucket, sub)
    for a in data["assignments"]:
        start = a["effective_start_period__index"] or 1
        for p in periods:
            if p["index"] < start:
                continue  # not assigned for this period: not an obligation, never "Not submitted"
            s = subs.get((a["id"], p["id"]))
            bucket = "NOT_DUE" if as_of < p["opens_at"] else vc_bucket(
                s and s["status"], s and s["edit_version"], s and s["has_ev"], s and s["last_decision"])
            slots.append((a, p, bucket, s))

    def in_scope(p):
        return p["id"] == sel if f["scope"] == "period" else (p["opens_at"] <= as_of if f["scope"] == "ytd" else True)

    scoped = [x for x in slots if in_scope(x[1])]
    future_period = f["scope"] == "period" and as_of < f["period"].opens_at

    def tally(rows):
        b = {k: 0 for k in BUCKETS}
        for x in rows:
            b[x[2]] += 1
        return b

    def summary(rows, n_assign, not_due=False):
        approved, expected = sum(1 for x in rows if x[2] == "APPROVED"), len(rows)
        return {"approved": approved, "expected": expected, "remaining": expected - approved, "assignments": n_assign,
                **rate(approved, expected, n_assign, not_due)}

    out = {"as_of": as_of, "filters": filters_json(f), "drafts_pending": data["drafts_pending"],
           "summary": summary(scoped, len(data["assignments"]), future_period), "breakdown": tally(scoped),
           "labels": LABELS}
    by_dept = {}
    for x in scoped:
        by_dept.setdefault(x[0]["department__code"], []).append(x)
    n_by_dept = {}
    for a in data["assignments"]:
        n_by_dept[a["department__code"]] = n_by_dept.get(a["department__code"], 0) + 1
    out["departments"] = [{"code": d["code"], "name": d["name"], **summary(by_dept.get(d["code"], []), n_by_dept.get(d["code"], 0), future_period),
                           "breakdown": tally(by_dept.get(d["code"], []))} for d in data["departments"]]

    def trend(rows):
        res = []
        for p in periods:
            prow = [x for x in rows if x[1]["id"] == p["id"]]
            opened = p["opens_at"] <= as_of
            approved = sum(1 for x in prow if x[2] == "APPROVED")
            res.append({"period_id": p["id"], "index": p["index"], "label": p["label"], "opened": opened, "approved": approved,
                        "expected": len(prow), **rate(approved, len(prow), 1 if prow else 0, not opened)})
        return res

    out["trend"] = trend(slots)
    all_by_dept = {}
    for x in slots:
        all_by_dept.setdefault(x[0]["department__code"], []).append(x)
    out["department_trends"] = {d["code"]: trend(all_by_dept.get(d["code"], [])) for d in data["departments"]}

    # Department × KRA matrix: the slot status (bimonthly) or approved/expected (YTD, full year); no assignment = None (N/A).
    kras = sorted({a["kra__number"] for a in data["assignments"]})
    cells = {}
    for a in data["assignments"]:
        cells[(a["department__code"], a["kra__number"])] = {"approved": 0, "expected": 0, "bucket": "NOT_ASSIGNED" if f["scope"] == "period" else None}
    for a, p, bucket, _ in scoped:
        c = cells[(a["department__code"], a["kra__number"])]
        c["expected"] += 1
        c["approved"] += bucket == "APPROVED"
        if f["scope"] == "period":
            c["bucket"] = bucket
    out["matrix"] = {"kras": kras, "rows": [{"department": d["code"], "cells": [cells.get((d["code"], k)) for k in kras]}
                                            for d in data["departments"]]}

    details = []
    for a, p, bucket, s in scoped:
        if f["status"] and bucket != f["status"]:
            continue
        reviewed = s and s["status"] in ("SUBMITTED", "REJECTED", "APPROVED") and s["current_revision__sequence"]
        details.append({"department": a["department__code"], "kra_number": a["kra__number"], "kra_text": a["kra__activity_text"],
                        "period": p["label"], "period_index": p["index"], "target_text": a["target_text"], "status": bucket,
                        "status_label": LABELS[bucket],
                        "achievement_text": s["current_revision__achievement_text"] if reviewed else "",
                        "achievement_source": "submitted" if reviewed else "none",
                        "is_nil": bool(reviewed and s["current_revision__is_nil"]),
                        "reopened": bool(s and s["reopened"]), "submission_id": str(s["id"]) if reviewed else None})
    details.sort(key=lambda r: (r["kra_number"], r["department"], r["period_index"]))
    out["details"] = details
    return out


def dataset(f, as_of, between=None):
    return compute(read_snapshot(lambda: load(f, as_of, between)), f, as_of)
