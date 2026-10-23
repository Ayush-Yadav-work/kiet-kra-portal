from django.conf import settings
from django.http import FileResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsDean, IsDeanOrVC
from apps.audit.errors import ApiError
from apps.submissions import services as sub_services
from apps.submissions.scope import get_or_404, submissions_for

from . import services
from .models import Evidence


def evidence_json(e):
    return {"id": str(e.id), "source_type": e.source_type, "category": e.category, "label": e.label,
            "description": e.description, "original_filename": e.original_filename, "mime": e.mime,
            "bytes": e.bytes, "drive_url": e.drive_url, "uploaded_at": e.uploaded_at,
            "uploaded_by": e.uploaded_by.display_name, "removed": e.removed, "removed_at": e.removed_at}


class SubmissionEvidenceView(APIView):
    def get_permissions(self):
        return [IsDean()] if self.request.method == "POST" else [IsDeanOrVC()]

    def get(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        items = sub.evidence.select_related("uploaded_by")
        if request.user.role == "VC":  # draft privacy (D-078): only what was submitted, never uploads made since
            ids = [m["id"] for m in sub.current_revision.evidence_manifest]
            return Response({"results": [evidence_json(e) for e in items.filter(pk__in=ids).order_by("uploaded_at")],
                             "editable": False, "usage": None, "categories": [], "required": [], "note": ""})
        if request.query_params.get("include_removed") != "1":
            items = items.filter(removed=False)
        active, history = sub_services.evidence_totals(sub)
        schema_ev = sub.assignment.template_version.schema.get("evidence", {})
        return Response({
            "results": [evidence_json(e) for e in items],
            "editable": sub_services.is_editable(sub),
            "usage": {"active_bytes": active, "history_bytes": history,
                      "max_file_bytes": settings.EVIDENCE_MAX_FILE_BYTES,
                      "max_active_bytes": settings.EVIDENCE_MAX_ACTIVE_BYTES,
                      "max_history_bytes": settings.EVIDENCE_MAX_HISTORY_BYTES},
            "categories": schema_ev.get("categories", []),
            "required": schema_ev.get("required", []),
            "note": schema_ev.get("note", ""),
        })

    def post(self, request, pk):
        sub = get_or_404(submissions_for(request.user), pk=pk)
        d = request.data
        if d.get("source_type") == "DRIVE_LINK":
            ev = services.add_link(request.user, sub.pk, d.get("drive_url"), d.get("category"), d.get("label"),
                                   d.get("description", ""), request)
        else:
            ev = services.add_file(request.user, sub.pk, request.FILES.get("file"), d.get("category"), d.get("label"),
                                   d.get("description", ""), request)
        return Response(evidence_json(ev), status=201)


def _scoped_evidence(user, pk):
    ev = get_or_404(Evidence.objects.select_related("uploaded_by", "submission")
                    .filter(submission__in=submissions_for(user)), pk=pk)
    if user.role == "VC" and not any(m["id"] == str(ev.pk) for r in ev.submission.revisions.all() for m in r.evidence_manifest):
        raise ApiError(404, "not_found", "Not found.")  # draft privacy (D-078): only evidence that was part of a submission
    return ev


class EvidenceItemView(APIView):
    permission_classes = [IsDean]

    def delete(self, request, pk):
        ev = _scoped_evidence(request.user, pk)
        ev = services.remove(request.user, ev, request)
        return Response(evidence_json(ev))


class EvidenceDownloadView(APIView):
    """Authorised streaming of private files; removed files stay downloadable for history."""

    permission_classes = [IsDeanOrVC]

    def get(self, request, pk):
        ev = _scoped_evidence(request.user, pk)
        if ev.source_type != Evidence.Source.FILE:
            raise ApiError(400, "not_a_file", "This evidence is a Drive link; open it in Google Drive.")
        inline = request.query_params.get("inline") == "1"
        resp = FileResponse(services.file_path(ev).open("rb"), content_type=ev.mime, as_attachment=not inline,
                            filename=ev.original_filename)
        resp["X-Content-Type-Options"] = "nosniff"
        resp["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
        resp["Cache-Control"] = "private, no-store"
        return resp
