"""VC annual assignments (VC features plan v2.3 Phase 1, D-073; replaces the Phase 5A whole-year finalize and VC KRA creation).
Every view is VC-only; every write goes through apps.catalogue.allocations. The KRA catalogue and report templates are
developer-installed: the VC can read them but not create, edit or delete them."""
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsVC
from apps.audit.errors import ApiError
from apps.reports.schema import validate_payload
from apps.submissions.scope import get_or_404

from . import allocations as svc
from .models import KRA, AcademicYear, AnnualAssignment, Department, DraftAssignment, TemplateVersion
from .views import kra_json


def template_problem(tv):
    """Why a stored template version cannot be used, or None. Checks the layout exists and the schema is usable."""
    try:
        get_template(tv.renderer_template)
    except TemplateDoesNotExist:
        return f"Report layout {tv.renderer_template} is not installed."
    schema = tv.schema or {}
    if not schema.get("sections") or not schema.get("activity"):
        return "Template schema is incomplete."
    if not isinstance(validate_payload(schema, {"activities": []}), dict):
        return "Template schema cannot be validated."
    return None


def template_json(tv, kras=None):
    return {"key": tv.key, "version": tv.version, "title": tv.title, "problem": template_problem(tv),
            **({"used_by_kras": kras} if kras is not None else {})}


def default_template(kra):
    if kra.default_template_id:
        return kra.default_template
    a = AnnualAssignment.objects.filter(kra=kra, template_version__isnull=False).order_by("-year__label").first()
    return a.template_version if a else None


def year_get(label):
    return get_or_404(AcademicYear.objects.prefetch_related("periods"), label=label or "")


def period_label(p):
    return {"index": p.index, "label": p.label} if p else None


def year_json(y, at):
    drafts = DraftAssignment.objects.filter(year=y, finalized_assignment__isnull=True)
    return {"label": y.label, "start_date": y.start_date, "end_date": y.end_date, "state": svc.year_state(y, at),
            "drafts": drafts.filter(removed_at__isnull=True).count(), "removed": drafts.filter(removed_at__isnull=False).count(),
            "finalised": AnnualAssignment.objects.filter(year=y).count()}


class TemplatesView(APIView):
    permission_classes = [IsVC]

    def get(self, request):
        used = {}
        for key, version, n in AnnualAssignment.objects.values_list("template_version__key", "template_version__version", "kra__number").distinct():
            used.setdefault((key, version), set()).add(n)
        return Response([template_json(tv, sorted(used.get((tv.key, tv.version), []))) for tv in TemplateVersion.objects.order_by("key", "version")])


class AdminKRAsView(APIView):
    """Read-only installed catalogue. New KRAs need a developer-built editor, preview, validation and PDF (plan §1)."""

    permission_classes = [IsVC]

    def get(self, request):
        out = []
        for k in KRA.objects.select_related("default_template").order_by("number"):
            tv = default_template(k)
            out.append({**kra_json(k), "active": k.active, "installed": bool(tv and not template_problem(tv)),
                        "default_template": tv and {"key": tv.key, "version": tv.version, "title": tv.title}})
        return Response(out)


class AdminYearsView(APIView):
    permission_classes = [IsVC]

    def get(self, request):
        at = timezone.now()
        return Response([year_json(y, at) for y in AcademicYear.objects.prefetch_related("periods").order_by("label")])


class AllocationsView(APIView):
    """Everything the annual-assignments screen needs for one year: departments, installed KRAs and every allocation
    row (drafts, removed drafts, finalised assignments). Pairs without a row are Unallocated."""

    permission_classes = [IsVC]

    def get(self, request):
        y = year_get(request.query_params.get("year"))
        at = timezone.now()
        previous = AcademicYear.objects.filter(label__lt=y.label).order_by("-label").first()
        prev_targets = {(a.department_id, a.kra_id): a.target_text for a in AnnualAssignment.objects.filter(year=previous)} if previous else {}
        rows, seen = [], set()
        for d in (DraftAssignment.objects.filter(year=y).select_related("department", "kra", "source_year", "removed_by",
                  "finalized_assignment__finalised_by", "finalized_assignment__effective_start_period")):
            a = d.finalized_assignment
            seen.add((d.department_id, d.kra_id))
            rows.append({"id": str(d.pk), "assignment_id": str(a.id) if a else None, "state": svc.state_of(d),
                         "department": d.department.code, "kra": d.kra.number, "target_text": a.target_text if a else d.target_text,
                         "previous_target": d.source_target, "source_year": d.source_year.label if d.source_year_id else None,
                         "edit_version": d.edit_version, "removed_at": d.removed_at, "removed_by": d.removed_by.display_name if d.removed_by_id else None,
                         "finalised_at": a.finalised_at if a else None, "finalised_by": a.finalised_by.display_name if a and a.finalised_by_id else None,
                         "effective_start_period": period_label(a.effective_start_period) if a else None})
        for a in (AnnualAssignment.objects.filter(year=y).select_related("department", "kra", "finalised_by", "effective_start_period")):
            if (a.department_id, a.kra_id) in seen:
                continue
            rows.append({"id": None, "assignment_id": str(a.id), "state": "FINALISED", "department": a.department.code, "kra": a.kra.number,
                         "target_text": a.target_text, "previous_target": prev_targets.get((a.department_id, a.kra_id)),
                         "source_year": previous.label if (a.department_id, a.kra_id) in prev_targets else None, "edit_version": None,
                         "removed_at": None, "removed_by": None, "finalised_at": a.finalised_at or a.assigned_at,
                         "finalised_by": a.finalised_by.display_name if a.finalised_by_id else "Migrated assignment",
                         "effective_start_period": period_label(a.effective_start_period)})
        rows.sort(key=lambda r: (r["kra"], r["department"]))
        opts = svc.start_options(y, at)
        return Response({
            "year": year_json(y, at), "previous_year": previous.label if previous else None,
            "departments": [{"code": d.code, "name": d.name} for d in Department.objects.filter(active=True).order_by("code")],
            "kras": AdminKRAsView().get(request).data, "allocations": rows,
            "start": {"kind": opts["kind"], "default": opts["default"],
                      "choices": {k: {"period": svc.period_json_short(p), "grant": g} for k, (p, g) in opts["choices"].items()}},
            "server_time": at})


class DraftsView(APIView):
    """POST: create draft allocations for the explicitly selected departments of one KRA."""

    permission_classes = [IsVC]

    def post(self, request):
        d = request.data
        y = year_get(d.get("year"))
        kra = get_or_404(KRA.objects.filter(active=True), number=d.get("kra"))
        created, skipped = svc.add_departments(y, kra, d.get("departments"), request.user, d.get("target_text"), request)
        return Response({"created": [str(x.pk) for x in created], "skipped": skipped}, status=201)


class DraftItemView(APIView):
    permission_classes = [IsVC]

    def patch(self, request, pk):
        d = svc.edit_target(pk, request.data.get("edit_version"), request.data.get("target_text"), request.user, request)
        return Response({"id": str(d.pk), "target_text": d.target_text, "edit_version": d.edit_version})


class BulkTargetView(APIView):
    permission_classes = [IsVC]

    def post(self, request):
        apply = request.data.get("apply") is True
        rows = svc.bulk_target(request.data.get("items"), request.data.get("target_text"), request.user, apply, request)
        return Response({"applied": apply, "affected": rows})


class RemoveView(APIView):
    permission_classes = [IsVC]
    removed = True

    def post(self, request):
        rows = svc.set_removed(request.data.get("items"), self.removed, request.user, request)
        return Response({"changed": [{"id": str(d.pk), "edit_version": d.edit_version} for d in rows]})


class RestoreView(RemoveView):
    removed = False


class CopyYearView(APIView):
    """POST ?preview=1 → classification only; otherwise create drafts. Repeatable: existing drafts, removed drafts and
    finalised assignments are never overwritten or resurrected."""

    permission_classes = [IsVC]

    def post(self, request, label):
        target = year_get(label)
        source = get_or_404(AcademicYear.objects.all(), label=request.data.get("source_year", ""))
        if request.query_params.get("preview") == "1":
            if source.label >= target.label:
                raise ApiError(400, "invalid", "Copy from an earlier year.", {"source_year": ["Must be before the target year."]})
            plan = svc.copy_plan(source, target)
        else:
            plan = svc.copy(source, target, request.user, request)
        return Response({"year": target.label, "source_year": source.label, "preview": request.query_params.get("preview") == "1",
                         **svc.plan_json(plan), "created": len(plan["create"])})


class FinalisePreviewView(APIView):
    permission_classes = [IsVC]

    def post(self, request, label):
        return Response(svc.finalise_preview(year_get(label), request.data.get("items"), request.data.get("start"), request.user))


class FinaliseView(APIView):
    permission_classes = [IsVC]

    def post(self, request, label):
        return Response(svc.finalise(year_get(label), request.data.get("token"), request.user, request=request))
