"""Phase 5B — the one progress dataset behind the VC table, its status counts and the progress PDF (D-068).

Two set-based queries (finalized assignments of the year + that period's submissions); no per-row queries. VC
assignment drafts are a separate model and never appear. Status follows the C11 rule (an untouched Draft shows as Not
submitted); achievements of Submitted/Rejected/Approved rows come from the submitted revision, Draft rows are marked as
unsubmitted. Targets and achievements are returned exactly as stored; nothing is totalled or ranked.
"""
from django.db.models import BooleanField, Case, Exists, F, FilteredRelation, OuterRef, Q, Value, When

from apps.audit.errors import ApiError
from apps.catalogue.models import AcademicYear, AnnualAssignment, Department, ReportingPeriod
from apps.evidence.models import Evidence

from .models import Status
from .services import NOT_SUBMITTED

STATUSES = (NOT_SUBMITTED, Status.DRAFT, Status.SUBMITTED, Status.REJECTED, Status.APPROVED)
STATUS_LABELS = {NOT_SUBMITTED: "Not submitted", Status.DRAFT: "Draft", Status.SUBMITTED: "Submitted",
                 Status.REJECTED: "Rejected", Status.APPROVED: "Approved"}
REVIEWED = (Status.SUBMITTED, Status.REJECTED, Status.APPROVED)
MAX_ROWS = 5000  # bounded processing: refuse (never truncate) beyond this


def bad(message, field):
    return ApiError(400, "invalid_filter", message, field_errors={field: [message]})


def parse_filters(q):
    """Validated filters; the period must belong to the year."""
    year = AcademicYear.objects.filter(label=q.get("year", "")).first()
    if not year:
        raise bad("Choose a valid academic year.", "year")
    try:
        period = ReportingPeriod.objects.select_related("year").get(pk=int(q.get("period", "")))
    except (ValueError, ReportingPeriod.DoesNotExist):
        raise bad("Choose a valid reporting period.", "period")
    if period.year_id != year.id:
        raise bad(f"Period {period.label} does not belong to {year.label}.", "period")
    f = {"year": year, "period": period, "department": "", "kra": None, "status": "", "search": ""}
    if q.get("department"):
        if not Department.objects.filter(code=q["department"]).exists():
            raise bad("Unknown department.", "department")
        f["department"] = q["department"]
    if q.get("kra"):
        try:
            f["kra"] = int(q["kra"])
        except ValueError:
            raise bad("KRA must be a number.", "kra")
    if q.get("status"):
        if q["status"] not in STATUSES:
            raise bad("Unknown status.", "status")
        f["status"] = q["status"]
    f["search"] = (q.get("search") or "")[:100]
    return f


def filters_json(f):
    return {"year": f["year"].label, "period": f["period"].label, "department": f["department"] or "All",
            "kra": f["kra"] or "All", "status": f["status"] or "All", "search": f["search"]}


def build(f):
    """(rows matching every filter, counts per status over the year/period/department/KRA/search dataset).

    One SQL statement (assignments LEFT JOIN this period's submission and its current revision), so rows and counts
    always come from a single database snapshot, for the page and the PDF alike."""
    qs = AnnualAssignment.objects.filter(year=f["year"]).annotate(
        sub=FilteredRelation("submissions", condition=Q(submissions__period=f["period"])))
    if f["department"]:
        qs = qs.filter(department__code=f["department"])
    if f["kra"] is not None:
        qs = qs.filter(kra__number=f["kra"])
    if f["search"]:
        qs = qs.filter(kra__activity_text__icontains=f["search"])
    same = (Q(sub__achievement_text=F("sub__current_revision__achievement_text")) & Q(sub__is_nil=F("sub__current_revision__is_nil"))
            & Q(sub__payload=F("sub__current_revision__payload")))
    data = list(qs.annotate(
        has_ev=Exists(Evidence.objects.filter(submission=OuterRef("sub__id"), removed=False)),
        same_as_revision=Case(When(same, then=Value(True)), default=Value(False), output_field=BooleanField()),
    ).order_by("kra__number", "department__code", "id").values(
        "id", "department__code", "department__name", "kra__number", "kra__activity_text", "target_text", "template_version_id",
        "sub__id", "sub__status", "sub__edit_version", "sub__is_nil", "sub__achievement_text", "sub__current_revision__sequence",
        "sub__current_revision__submitted_at", "sub__current_revision__achievement_text", "sub__current_revision__is_nil",
        "has_ev", "same_as_revision")[:MAX_ROWS + 1])
    if len(data) > MAX_ROWS:
        raise ApiError(400, "too_many_rows", f"More than {MAX_ROWS} rows match; narrow the filters.")
    rows, counts = [], {s: 0 for s in STATUSES}
    for a in data:
        st = a["sub__status"]
        status = NOT_SUBMITTED if st is None or (st == Status.DRAFT and a["sub__edit_version"] == 0 and not a["has_ev"]) else st
        counts[status] += 1
        if f["status"] and f["status"] != status:
            continue
        seq = a["sub__current_revision__sequence"]
        if status in REVIEWED and seq:
            achievement, nil, source = a["sub__current_revision__achievement_text"], a["sub__current_revision__is_nil"], "submitted"
        elif status == Status.DRAFT:
            achievement, nil, source = a["sub__achievement_text"], a["sub__is_nil"], "draft"
        else:
            achievement, nil, source = "", False, "none"
        rows.append({"assignment_id": str(a["id"]), "department": a["department__code"], "department_name": a["department__name"],
                     "kra_number": a["kra__number"], "kra_text": a["kra__activity_text"], "target_text": a["target_text"],
                     "has_template": a["template_version_id"] is not None,
                     "submission_id": str(a["sub__id"]) if a["sub__id"] else None, "display_status": status,
                     "status_label": STATUS_LABELS[status], "achievement_text": achievement, "is_nil": bool(nil),
                     "achievement_source": source, "revision_sequence": seq, "submitted_at": a["sub__current_revision__submitted_at"],
                     "changed_since_submission": bool(seq and status in REVIEWED and not a["same_as_revision"])})
    return rows, counts
