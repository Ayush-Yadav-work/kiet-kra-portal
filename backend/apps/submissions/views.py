from django.db.models import Exists, OuterRef
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django.utils.html import escape
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsDean, IsDeanOrVC, IsVC
from apps.audit.errors import ApiError
from apps.catalogue.allocations import NOT_ASSIGNED, applicability
from apps.catalogue.models import ReportingPeriod
from apps.catalogue.views import assignment_json, period_json
from apps.evidence.models import Evidence
from apps.reports import artifacts
from apps.reports.pdf import call_renderer, export_pdf
from apps.reports.rendering import build_context, progress_pdf_parts, render_html
from apps.reports import capabilities
from apps.reports.schema import validate_payload

from . import progress
from . import services as svc
from .models import ReopenGrant, ReviewDecision, Status, Submission
from .progress import STATUS_LABELS
from .scope import assignments_for, get_or_404, reopen_requests_for, submissions_for


def decision_json(d):
    return {"id": str(d.id), "decision": d.decision, "reason": d.reason, "reviewer_name": d.reviewer_name,
            "granted_reopen": d.granted_reopen, "created_at": d.created_at, "revision_sequence": d.revision.sequence}


def grant_json(g, at):
    return {"id": str(g.id), "starts_at": g.starts_at, "expires_at": g.expires_at, "source": g.source,
            "active": g.starts_at <= at < g.expires_at}


def request_json(r):
    a = r.submission.assignment
    return {"id": str(r.id), "submission_id": str(r.submission_id), "reason": r.reason, "state": r.state,
            "requested_at": r.requested_at, "requested_by": r.requested_by.display_name,
            "decided_at": r.decided_at, "decided_by": r.decided_by.display_name if r.decided_by else None,
            "decision_reason": r.decision_reason, "department": a.department.code, "kra_number": a.kra.number,
            "submitted": r.submission.current_revision_id is not None,  # whether a submitted version exists to open
            "period": r.submission.period.label, "year": a.year.label}


def latest_decision(sub):
    d = (ReviewDecision.objects.filter(revision__submission=sub).select_related("revision")
         .order_by("-created_at").first())
    return decision_json(d) if d else None


def summary_json(sub, decisions, vc=False):
    """Compact per-period state used by dashboards (C11 display status). `decisions`: latest decision per submission id.
    For the VC (D-078) a never-submitted report is plain Not submitted and values come from the submitted revision."""
    if sub is None or (vc and sub.current_revision_id is None):
        return {"id": None, "display_status": svc.NOT_SUBMITTED}
    if vc:
        rev = sub.current_revision
        out = {"id": str(sub.id), "display_status": sub.status, "status": sub.status, "achievement_text": rev.achievement_text, "is_nil": rev.is_nil}
        if sub.status == Status.REJECTED:
            d = decisions.get(sub.id)
            out["latest_decision"] = decision_json(d) if d else None
        return out
    out = {"id": str(sub.id), "display_status": svc.display_status(sub), "status": sub.status,
           "achievement_text": sub.achievement_text, "is_nil": sub.is_nil}
    if sub.status == Status.REJECTED:
        d = decisions.get(sub.id)
        out["latest_decision"] = decision_json(d) if d else None
    return out


def vc_detail_json(sub, user):
    """Draft privacy (D-078): the VC sees the submitted revision only — never the Dean's working copy, edit version or
    in-progress values, and other periods only as submitted."""
    out = detail_json(sub, user)
    rev = sub.current_revision
    out.update({"display_status": sub.status, "is_nil": rev.is_nil, "nil_reason": rev.nil_reason, "achievement_text": rev.achievement_text,
                "remarks": rev.remarks, "payload": rev.payload, "edit_version": None, "editable": False, "can_request_reopen": False})
    others = {s.period_id: s for s in Submission.objects.filter(assignment=sub.assignment, current_revision__isnull=False)
              .select_related("current_revision")}
    for e in out["period_entries"]:
        o = others.get(e["period"]["id"])
        r = o.current_revision if o else None
        e.update({"submission_id": str(o.id) if o else None, "display_status": o.status if o else svc.NOT_SUBMITTED,
                  "achievement_text": r.achievement_text if r else "", "remarks": r.remarks if r else "", "is_nil": r.is_nil if r else False})
    return out


def detail_json(sub, user):
    at = timezone.now()
    a = sub.assignment
    grants = list(sub.grants.all())
    active = next((g for g in grants if g.starts_at <= at < g.expires_at), None)
    requests = list(sub.reopen_requests.select_related("requested_by", "decided_by", "submission__period",
                                                       "submission__assignment__department",
                                                       "submission__assignment__kra",
                                                       "submission__assignment__year"))
    pending = any(r.state == "PENDING" for r in requests)
    others = {s.period_id: s for s in Submission.objects.filter(assignment=a).select_related("period")}
    periods = ReportingPeriod.objects.filter(year=a.year).select_related("year")
    return {
        "id": str(sub.id),
        "server_time": at,
        "assignment": assignment_json(a),
        "period": period_json(sub.period, at),
        "status": sub.status,
        "display_status": svc.display_status(sub),
        "is_nil": sub.is_nil,
        "nil_reason": sub.nil_reason,
        "achievement_text": sub.achievement_text,
        "remarks": sub.remarks,
        "payload": capabilities.editable_payload(capabilities.schema_for(sub), sub.payload),
        "dean_name": svc.dean_name(user) if user.role == "DEAN" else "",  # read-only Head/Dean value (D-079)
        "edit_version": sub.edit_version,
        "editable": svc.is_editable(sub, at),
        "active_grant": grant_json(active, at) if active else None,
        "grants": [grant_json(g, at) for g in grants],
        "reopen_requests": [request_json(r) for r in requests],
        "applicability": applicability(a, sub.period, at),
        "can_request_reopen": (user.role == "DEAN" and at >= sub.period.closes_at and active is None
                               and applicability(a, sub.period, at) != NOT_ASSIGNED
                               and not pending and sub.status in svc.EDITABLE_STATUSES),
        "current_revision": (lambda r: r and {  # what was submitted: review reads only these values (D-068)
            "id": str(r.id), "sequence": r.sequence, "submitted_at": r.submitted_at, "achievement_text": r.achievement_text,
            "remarks": r.remarks, "is_nil": r.is_nil, "nil_reason": r.nil_reason, "evidence": r.evidence_manifest})(sub.current_revision),
        "latest_decision": latest_decision(sub),
        "grant_option_available": svc.grant_option_available(sub, at),
        "period_entries": [
            {"period": period_json(p, at), "submission_id": str(others[p.id].id) if p.id in others else None,
             "display_status": svc.display_status(others.get(p.id)), "applicability": applicability(a, p, at),
             "achievement_text": others[p.id].achievement_text if p.id in others else "",
             "remarks": others[p.id].remarks if p.id in others else "",
             "is_nil": others[p.id].is_nil if p.id in others else False}
            for p in periods
        ],
    }


# ---------- Dean: assignments + workspace ----------

class AssignmentsView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request):
        year = request.query_params.get("year", "2026-27")
        qs = assignments_for(request.user).filter(year__label=year)
        period_id = request.query_params.get("period")
        period = get_or_404(ReportingPeriod.objects.filter(year__label=year), pk=period_id) if period_id else None
        subs, decisions, requests = {}, {}, {}
        if period:  # fixed number of queries however many rows (Phase 6B: was one query per Rejected/untouched row)
            subs = {s.assignment_id: s for s in Submission.objects.filter(period=period, assignment__in=qs).select_related("current_revision").annotate(
                has_ev=Exists(Evidence.objects.filter(submission=OuterRef("pk"), removed=False)))}
            rejected = [s.id for s in subs.values() if s.status == Status.REJECTED]
            for d in (ReviewDecision.objects.filter(revision__submission_id__in=rejected).select_related("revision")
                      .order_by("-created_at")):
                decisions.setdefault(d.revision.submission_id, d)
            # latest reopening request per report (one query): a denial stays visible until a newer request supersedes it
            for r in reopen_requests_for(request.user).filter(submission__in=list(subs.values())).order_by("-requested_at"):
                requests.setdefault(r.submission.assignment_id, r)
        at = timezone.now()
        return Response({
            "server_time": at,
            "period": period_json(period, at) if period else None,
            "results": [{**assignment_json(a), "submission": summary_json(subs.get(a.id), decisions, request.user.role == "VC") if period else None,
                         "applicability": applicability(a, period, at) if period else None,
                         "latest_reopen_request": request_json(requests[a.id]) if a.id in requests else None}
                        for a in qs],
        })


class AssignmentPeriodView(APIView):
    """Workspace entry for (assignment, period): opens or creates the Dean's draft row (D-017)."""

    permission_classes = [IsDeanOrVC]

    def get(self, request, assignment_id, period_id):
        a = get_or_404(assignments_for(request.user), pk=assignment_id)
        p = get_or_404(ReportingPeriod.objects.filter(year=a.year), pk=period_id)
        sub = Submission.objects.filter(assignment=a, period=p).first()
        at = timezone.now()
        if request.user.role == "VC" and sub is not None and sub.current_revision_id is None:
            sub = None  # draft privacy (D-078)
        body = {"assignment": assignment_json(a), "period": period_json(p, at), "server_time": at, "applicability": applicability(a, p, at),
                "submission_id": str(sub.id) if sub else None}
        if sub is None:
            body["can_request_reopen"] = request.user.role == "DEAN" and at >= p.closes_at and applicability(a, p, at) != NOT_ASSIGNED
        return Response(body)

    def post(self, request, assignment_id, period_id):
        if request.user.role != "DEAN":
            raise ApiError(403, "forbidden", "Only the Dean can open a draft.")
        a = get_or_404(assignments_for(request.user), pk=assignment_id)
        p = get_or_404(ReportingPeriod.objects.filter(year=a.year), pk=period_id)
        if a.template_version is None:
            raise ApiError(409, "template_pending", "This KRA's report format is not available yet (Phase 4).")
        sub, created = svc.get_or_create_for_dean(request.user, a, p)
        if sub is None:
            raise ApiError(409, "window_closed", "The reporting period is closed. Request reopening to start a report.")
        return Response({"submission_id": str(sub.id), "created": created}, status=201 if created else 200)


class SubmissionDetailView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        return Response((vc_detail_json if request.user.role == 'VC' else detail_json)(sub, request.user))


class DraftView(APIView):
    permission_classes = [IsDean]

    def patch(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        sub = svc.save_draft(request.user, sub.pk, request.data.get("edit_version"),
                             {k: v for k, v in request.data.items() if k != "edit_version"}, request)
        return Response({"edit_version": sub.edit_version, "display_status": svc.display_status(sub),
                         "saved_at": sub.updated_at})


class ValidateView(APIView):
    permission_classes = [IsDean]

    def post(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        errors = svc.validation_errors(sub, request.user)
        return Response({"valid": not errors, "field_errors": errors})


class SubmitView(APIView):
    permission_classes = [IsDean]

    def post(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        sub = svc.submit(request.user, sub.pk, request.data.get("edit_version"), request)
        return Response((vc_detail_json if request.user.role == 'VC' else detail_json)(sub, request.user))


class PreviewView(APIView):
    """Unsaved draft -> HTML. Status/verification never come from the client."""

    permission_classes = [IsDeanOrVC]

    def post(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        draft = {}
        if request.user.role == "DEAN":
            draft = {k: request.data[k] for k in ("payload", "is_nil", "nil_reason", "achievement_text")
                     if k in request.data}
            if "payload" in draft:
                errors = validate_payload(capabilities.schema_for(sub), draft["payload"], strict=False)
                if errors:
                    raise ApiError(400, "invalid", "Some values are not valid.", errors)
            if "is_nil" in draft and not isinstance(draft["is_nil"], bool):
                draft.pop("is_nil")
            for k in ("nil_reason", "achievement_text"):
                if k in draft and not isinstance(draft[k], str):
                    draft.pop(k)
        revision = None
        if request.data.get("revision"):
            revision = get_or_404(sub.revisions.all(), pk=request.data["revision"])
            draft = {}
        elif request.user.role == "VC":
            revision = sub.current_revision  # draft privacy (D-078)
        ctx = build_context(sub, revision, draft)
        return Response({"html": render_html(ctx, "preview")})


PDF_WAIT_POLLS = 24  # bounded automatic refreshes (~2 minutes) before asking the user to try later


def artifact_pending(request, art):
    """Processing / failed answer for an approved PDF that is not ready. Never falls back to another document."""
    failed = art.state == art.State.FAILED
    retry = 5
    body = {"code": "pdf_failed" if failed else "pdf_processing", "state": art.state, "retry_after": retry,
            "message": ("The approved PDF could not be generated yet. The approval is recorded; the administrator can retry "
                        "the PDF job. Try again later." if failed else
                        "The approved PDF is being prepared. The approval is recorded; try again in a few seconds.")}
    if "application/json" in request.headers.get("Accept", ""):
        resp = Response(body, status=503 if failed else 202)
    else:  # opened in a browser tab: a small self-refreshing page with a bounded number of refreshes
        try:
            n = min(max(int(request.query_params.get("wait", 0)), 0), PDF_WAIT_POLLS)
        except ValueError:
            n = 0
        q = request.query_params.copy()
        q["wait"] = n + 1
        again = escape(f"?{q.urlencode()}")
        refresh = f'<meta http-equiv="refresh" content="{retry};url={again}">' if not failed and n < PDF_WAIT_POLLS else ""
        note = ("Still preparing after several attempts." if n >= PDF_WAIT_POLLS and not failed else "")
        html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Approved PDF</title>{refresh}'
                '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
                '<body style="font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem;color:#1f2937">'
                f'<h1 style="font-size:1.25rem">{"Approved PDF not available yet" if failed else "Preparing the approved PDF"}</h1>'
                f'<p role="status">{escape(body["message"])} {note}</p><p><a href="{again}">Try again</a></p></body></html>')
        resp = HttpResponse(html, status=503 if failed else 202, content_type="text/html; charset=utf-8")
    resp["Retry-After"] = str(retry)
    resp["Cache-Control"] = "private, no-store"
    return resp


class ExportView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        revision = None
        if request.query_params.get("revision"):
            revision = get_or_404(sub.revisions.all(), pk=request.query_params["revision"])
        approval = artifacts.approval_for(sub, revision)
        if approval is None and revision is None and request.user.role == "VC":
            revision = sub.current_revision  # draft privacy (D-078): the submitted version, never the working copy
        if approval is not None:  # approved documents come only from the retained artifact (D-076)
            art = artifacts.artifact_for(approval)
            if art.state != art.State.READY:
                return artifact_pending(request, art)
            path, snap = artifacts.read_path(art.storage_key), art.revision.snapshot
        else:
            doc, path, ctx = export_pdf(sub, revision)
            snap = ctx["snap"]
        name = f'KRA{snap["kra"]["number"]}_{snap["department"]["code"]}_{snap["year"]}_P{snap["period"]["index"]}'
        name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        if request.query_params.get("revision"):
            name += f"_rev{revision.sequence}"
        resp = FileResponse(path.open("rb"), content_type="application/pdf",
                            as_attachment=request.query_params.get("inline") != "1", filename=f"{name}.pdf")
        resp["X-Content-Type-Options"] = "nosniff"
        resp["Cache-Control"] = "private, no-store"  # unpublished institutional report (Phase 6A)
        return resp


class HistoryView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        at = timezone.now()
        revisions = []
        for rev in sub.revisions.select_related("submitted_by").prefetch_related("decisions"):
            revisions.append({"id": str(rev.id), "sequence": rev.sequence, "submitted_at": rev.submitted_at,
                              "submitted_by": (rev.snapshot.get("dean") or {}).get("name") or rev.submitted_by.display_name, "is_nil": rev.is_nil,
                              "achievement_text": rev.achievement_text, "evidence_count": len(rev.evidence_manifest),
                              "decisions": [decision_json(d) for d in rev.decisions.all()]})
        return Response({"revisions": revisions, "grants": [grant_json(g, at) for g in sub.grants.all()],
                         "reopen_requests": [request_json(r) for r in reopen_requests_for(request.user)
                                             .filter(submission=sub)]})


# ---------- reopening ----------

class SubmissionReopenRequestView(APIView):
    permission_classes = [IsDean]

    def post(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        req = svc.request_reopen(request.user, sub.assignment, sub.period, request.data.get("reason"), request)
        return Response(request_json(req), status=201)


class AssignmentReopenRequestView(APIView):
    """C2: Dean request when no submission row exists yet."""

    permission_classes = [IsDean]

    def post(self, request, assignment_id, period_id):
        a = get_or_404(assignments_for(request.user), pk=assignment_id)
        p = get_or_404(ReportingPeriod.objects.filter(year=a.year), pk=period_id)
        if a.template_version is None:
            raise ApiError(409, "template_pending", "This KRA's report format is not available yet (Phase 4).")
        req = svc.request_reopen(request.user, a, p, request.data.get("reason"), request)
        return Response(request_json(req), status=201)


class ReopenRequestsView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request):
        qs = reopen_requests_for(request.user)
        if request.query_params.get("state"):
            qs = qs.filter(state=request.query_params["state"])
        return Response([request_json(r) for r in qs[:200]])


class ReopenDecisionView(APIView):
    permission_classes = [IsVC]

    def post(self, request, pk):
        req = get_or_404(reopen_requests_for(request.user), pk=pk)
        approve = request.data.get("approve")
        if not isinstance(approve, bool):
            raise ApiError(400, "invalid", "Choose approve or deny.", {"approve": ["Required."]})
        req, grant = svc.decide_reopen(request.user, req.pk, approve, request.data.get("reason"), request)
        return Response({**request_json(req), "grant": grant_json(grant, timezone.now()) if grant else None})


class ActiveGrantsView(APIView):
    """C9 banner source: own department's active grants with server time."""

    permission_classes = [IsDean]

    def get(self, request):
        at = timezone.now()
        grants = (ReopenGrant.objects.filter(submission__assignment__department_id=request.user.department_id,
                                             starts_at__lte=at, expires_at__gt=at)
                  .select_related("submission__assignment__kra", "submission__period")
                  .order_by("expires_at"))
        return Response({"server_time": at, "results": [
            {**grant_json(g, at), "submission_id": str(g.submission_id),
             "assignment_id": str(g.submission.assignment_id), "period_id": g.submission.period_id,
             "kra_number": g.submission.assignment.kra.number, "period": g.submission.period.label,
             "status": g.submission.status} for g in grants]})


# ---------- VC review + progress ----------

class ReviewView(APIView):
    permission_classes = [IsVC]

    def post(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        grant = request.data.get("grant_reopen", False)
        sub, _ = svc.review(request.user, sub.pk, request.data.get("revision"), request.data.get("decision"),
                            request.data.get("reason"), grant is True, request)
        return Response((vc_detail_json if request.user.role == 'VC' else detail_json)(sub, request.user))


class ProgressView(APIView):
    """VC progress table: filtered, paginated rows and status counts from one dataset (D-068)."""

    permission_classes = [IsVC]

    def get(self, request):
        f = progress.parse_filters(request.query_params)
        rows, counts = progress.build(f)
        try:
            page = max(int(request.query_params.get("page", 1) or 1), 1)
            size = min(max(int(request.query_params.get("page_size", 50) or 50), 10), 100)
        except ValueError:
            raise ApiError(400, "invalid_filter", "Page must be a number.")
        pending = reopen_requests_for(request.user).filter(state="PENDING").count()
        return Response({"server_time": timezone.now(), "period": period_json(f["period"]), "filters": progress.filters_json(f),
                         "counts": counts, "assigned": sum(counts.values()), "pending_reopen_requests": pending,
                         "total": len(rows), "page": page, "page_size": size, "results": rows[(page - 1) * size: page * size]})


class ProgressExportView(APIView):
    """VC-only PDF of ALL filtered rows. Rows and counts come from one statement snapshot; read-only; rendered by the
    internal renderer (no Chromium in API workers); returned directly, never cached on disk (D-068)."""

    permission_classes = [IsVC]

    def get(self, request):
        f = progress.parse_filters(request.query_params)
        rows, counts = progress.build(f)  # one SQL statement: rows and counts share a snapshot
        at = timezone.localtime()
        parts = progress_pdf_parts({"rows": rows, "counts": counts, "total": len(rows), "filters": progress.filters_json(f),
                                    "generated_at": at, "count_list": [(STATUS_LABELS[s], counts[s]) for s in progress.STATUSES]})
        data = call_renderer(parts)
        name = f'KRA_progress_{f["year"].label}_P{f["period"].index}_{at:%Y%m%d-%H%M}.pdf'
        resp = HttpResponse(data, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{name}"'
        resp["Cache-Control"] = "private, no-store"
        resp["X-Content-Type-Options"] = "nosniff"
        return resp
