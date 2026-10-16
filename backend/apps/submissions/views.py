from django.db.models import Exists, OuterRef
from django.http import FileResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsDean, IsDeanOrVC, IsVC
from apps.audit.errors import ApiError
from apps.catalogue.models import ReportingPeriod
from apps.catalogue.views import assignment_json, period_json
from apps.evidence.models import Evidence
from apps.reports.pdf import export_pdf
from apps.reports.rendering import build_context, render_html
from apps.reports.schema import validate_payload

from . import services as svc
from .models import ReopenGrant, ReviewDecision, Status, Submission
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
            "period": r.submission.period.label, "year": a.year.label}


def latest_decision(sub):
    d = (ReviewDecision.objects.filter(revision__submission=sub).select_related("revision")
         .order_by("-created_at").first())
    return decision_json(d) if d else None


def summary_json(sub):
    """Compact per-period state used by dashboards (C11 display status)."""
    if sub is None:
        return {"id": None, "display_status": svc.NOT_SUBMITTED}
    out = {"id": str(sub.id), "display_status": svc.display_status(sub), "status": sub.status,
           "achievement_text": sub.achievement_text, "is_nil": sub.is_nil}
    if sub.status == Status.REJECTED:
        out["latest_decision"] = latest_decision(sub)
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
        "payload": sub.payload,
        "edit_version": sub.edit_version,
        "editable": svc.is_editable(sub, at),
        "active_grant": grant_json(active, at) if active else None,
        "grants": [grant_json(g, at) for g in grants],
        "reopen_requests": [request_json(r) for r in requests],
        "can_request_reopen": (user.role == "DEAN" and at >= sub.period.closes_at and active is None
                               and not pending and sub.status in svc.EDITABLE_STATUSES),
        "current_revision": ({"id": str(sub.current_revision.id), "sequence": sub.current_revision.sequence,
                              "submitted_at": sub.current_revision.submitted_at} if sub.current_revision else None),
        "latest_decision": latest_decision(sub),
        "grant_option_available": svc.grant_option_available(sub, at),
        "period_entries": [
            {"period": period_json(p, at), "submission_id": str(others[p.id].id) if p.id in others else None,
             "display_status": svc.display_status(others.get(p.id)),
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
        subs = {}
        if period:
            subs = {s.assignment_id: s for s in Submission.objects.filter(period=period, assignment__in=qs)}
        at = timezone.now()
        return Response({
            "server_time": at,
            "period": period_json(period, at) if period else None,
            "results": [{**assignment_json(a), "submission": summary_json(subs.get(a.id)) if period else None}
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
        body = {"assignment": assignment_json(a), "period": period_json(p, at), "server_time": at,
                "submission_id": str(sub.id) if sub else None}
        if sub is None:
            body["can_request_reopen"] = request.user.role == "DEAN" and at >= p.closes_at
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
        return Response(detail_json(sub, request.user))


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
        errors = svc.validation_errors(sub)
        return Response({"valid": not errors, "field_errors": errors})


class SubmitView(APIView):
    permission_classes = [IsDean]

    def post(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        sub = svc.submit(request.user, sub.pk, request.data.get("edit_version"), request)
        return Response(detail_json(sub, request.user))


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
                errors = validate_payload(sub.assignment.template_version.schema, draft["payload"], strict=False)
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
        ctx = build_context(sub, revision, draft)
        return Response({"html": render_html(ctx, "preview")})


class ExportView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        revision = None
        if request.query_params.get("revision"):
            revision = get_or_404(sub.revisions.all(), pk=request.query_params["revision"])
        doc, path, ctx = export_pdf(sub, revision)
        snap = ctx["snap"]
        name = f'KRA{snap["kra"]["number"]}_{snap["department"]["code"]}_{snap["year"]}_P{snap["period"]["index"]}'
        name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        if revision:
            name += f"_rev{revision.sequence}"
        resp = FileResponse(path.open("rb"), content_type="application/pdf",
                            as_attachment=request.query_params.get("inline") != "1", filename=f"{name}.pdf")
        resp["X-Content-Type-Options"] = "nosniff"
        return resp


class HistoryView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        at = timezone.now()
        revisions = []
        for rev in sub.revisions.select_related("submitted_by").prefetch_related("decisions"):
            revisions.append({"id": str(rev.id), "sequence": rev.sequence, "submitted_at": rev.submitted_at,
                              "submitted_by": rev.submitted_by.display_name, "is_nil": rev.is_nil,
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
        return Response(detail_json(sub, request.user))


class ProgressView(APIView):
    """VC status table + counts for year/period with filters; counts derived from the database (C11)."""

    permission_classes = [IsVC]
    STATUSES = (svc.NOT_SUBMITTED, Status.DRAFT, Status.SUBMITTED, Status.REJECTED, Status.APPROVED)

    def get(self, request):
        q = request.query_params
        year = q.get("year", "2026-27")
        period = get_or_404(ReportingPeriod.objects.filter(year__label=year), pk=q.get("period"))
        assignments = assignments_for(request.user).filter(year__label=year).order_by("kra__number", "department__code")
        if q.get("department"):
            assignments = assignments.filter(department__code=q["department"])
        if q.get("kra"):
            assignments = assignments.filter(kra__number=q["kra"])
        if q.get("search"):
            assignments = assignments.filter(kra__activity_text__icontains=q["search"][:100])
        active_ev = Evidence.objects.filter(submission=OuterRef("pk"), removed=False)
        subs = {s.assignment_id: s for s in Submission.objects.filter(period=period, assignment__in=assignments)
                .annotate(has_ev=Exists(active_ev))}
        rows, counts = [], {s: 0 for s in self.STATUSES}
        for a in assignments:
            s = subs.get(a.id)
            if s is None or (s.status == Status.DRAFT and s.edit_version == 0 and not s.has_ev):
                ds = svc.NOT_SUBMITTED
            else:
                ds = s.status
            counts[ds] += 1
            if q.get("status") and q["status"] != ds:
                continue
            rows.append({"assignment_id": str(a.id), "department": a.department.code, "kra_number": a.kra.number,
                         "kra_text": a.kra.activity_text, "target_text": a.target_text,
                         "has_template": a.template_version_id is not None,
                         "submission_id": str(s.id) if s else None, "display_status": ds,
                         "achievement_text": s.achievement_text if s else "", "is_nil": s.is_nil if s else False})
        page, size = max(int(q.get("page", 1) or 1), 1), 50
        pending = reopen_requests_for(request.user).filter(state="PENDING").count()
        return Response({"server_time": timezone.now(), "period": period_json(period), "counts": counts,
                         "assigned": sum(counts.values()), "pending_reopen_requests": pending,
                         "total": len(rows), "page": page, "page_size": size,
                         "results": rows[(page - 1) * size: page * size]})
