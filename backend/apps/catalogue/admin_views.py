"""Phase 5A — VC KRA management, draft assignments and next-year targets (D-065). Every view is VC-only."""
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsVC
from apps.audit.models import record
from apps.audit.errors import ApiError
from apps.reports.schema import validate_payload
from apps.submissions.scope import get_or_404

from .models import KRA, AcademicYear, AnnualAssignment, Department, DraftAssignment, TemplateVersion
from .views import kra_json

MAX_TARGET = 500


def err(code, message, status=400, field_errors=None):
    return ApiError(status, code, message, field_errors)


def today():
    return timezone.localdate()


def year_elapsed(y):
    """An ended academic year is read-only. The current and future years accept drafts for unassigned pairs; finalized
    assignments stay immutable in every year (D-066)."""
    return y.end_date < today()


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


def find_template(key, version):
    tv = TemplateVersion.objects.filter(key=key, version=version).first()
    if not tv:
        raise err("invalid", "Choose an installed template version.", field_errors={"template": ["Unknown template version."]})
    problem = template_problem(tv)
    if problem:
        raise err("invalid", problem, field_errors={"template": [problem]})
    return tv


def default_template(kra):
    if kra.default_template_id:
        return kra.default_template
    a = AnnualAssignment.objects.filter(kra=kra, template_version__isnull=False).order_by("-year__label").first()
    return a.template_version if a else None


def clean_target(value):
    """Target strings are stored exactly as typed (percentages, NA/Nil, policy wording); only emptiness and length are checked."""
    if not isinstance(value, str) or not value.strip():
        raise err("invalid", "Enter the target text.", field_errors={"target_text": ["Required."]})
    if len(value) > MAX_TARGET:
        raise err("invalid", f"Target text is limited to {MAX_TARGET} characters.", field_errors={"target_text": ["Too long."]})
    return value


def open_year(label, lock=False):
    qs = AcademicYear.objects.select_for_update() if lock else AcademicYear.objects
    y = get_or_404(qs, label=label)
    if year_elapsed(y):
        raise err("year_locked", f"{y.label} has ended; its assignments are read-only.",
                       status=409)
    return y


def draft_json(d):
    return {"id": str(d.id), "year": d.year.label, "department": {"code": d.department.code, "name": d.department.name},
            "kra": kra_json(d.kra), "target_text": d.target_text,
            "template": {"key": d.template_version.key, "version": d.template_version.version, "title": d.template_version.title},
            "copied_from_year": d.copied_from.year.label if d.copied_from_id else None,
            "finalized": d.finalized_assignment_id is not None, "updated_at": d.updated_at}


def drafts_qs():
    return DraftAssignment.objects.select_related("department", "kra", "year", "template_version", "copied_from__year")


class TemplatesView(APIView):
    permission_classes = [IsVC]

    def get(self, request):
        used = {}
        for key, version, n in AnnualAssignment.objects.values_list("template_version__key", "template_version__version", "kra__number").distinct():
            used.setdefault((key, version), set()).add(n)
        return Response([template_json(tv, sorted(used.get((tv.key, tv.version), []))) for tv in TemplateVersion.objects.order_by("key", "version")])


class AdminKRAsView(APIView):
    permission_classes = [IsVC]

    def get(self, request):
        return Response([{**kra_json(k), "active": k.active,
                          "default_template": (lambda tv: tv and {"key": tv.key, "version": tv.version, "title": tv.title})(default_template(k))}
                         for k in KRA.objects.select_related("default_template").order_by("number")])

    def post(self, request):
        d = request.data
        title = d.get("title")
        if not isinstance(title, str) or not title.strip():
            raise err("invalid", "Enter the KRA activity text.", field_errors={"title": ["Required."]})
        tv = find_template(d.get("template_key"), d.get("template_version"))
        if d.get("confirm_layout") is not True:
            raise err("invalid", f"Confirm that this activity is reported with the existing layout \"{tv.title}\". A different layout "
                                      "needs a software update.", field_errors={"confirm_layout": ["Confirmation required."]})
        with transaction.atomic():
            number = d.get("number") or (KRA.objects.aggregate(m=Max("number"))["m"] or 0) + 1
            if not isinstance(number, int) or number < 1 or KRA.objects.filter(number=number).exists():
                raise err("invalid", f"KRA {number} already exists or is not a valid number.", field_errors={"number": ["Not available."]})
            kra = KRA.objects.create(number=number, activity_text=f"KRA {number}: {title.strip()}", nba_ref=str(d.get("nba_ref", ""))[:20],
                                     naac_ref=str(d.get("naac_ref", ""))[:20], default_template=tv)
            record(request.user, "kra.create", kra, {"number": number, "template": f"{tv.key} v{tv.version}"}, request)
        return Response({**kra_json(kra), "default_template": {"key": tv.key, "version": tv.version, "title": tv.title}}, status=201)


class AdminYearsView(APIView):
    permission_classes = [IsVC]

    def get(self, request):
        out = []
        for y in AcademicYear.objects.order_by("label"):
            drafts = DraftAssignment.objects.filter(year=y)
            out.append({"label": y.label, "start_date": y.start_date, "end_date": y.end_date, "locked": year_elapsed(y),
                        "current": y.start_date <= today() <= y.end_date,
                        "finalized_assignments": AnnualAssignment.objects.filter(year=y).count(),
                        "drafts_pending": drafts.filter(finalized_assignment__isnull=True).count(),
                        "drafts_finalized": drafts.filter(finalized_assignment__isnull=False).count()})
        return Response(out)


class DraftsView(APIView):
    permission_classes = [IsVC]

    def get(self, request):
        qs = drafts_qs().filter(year__label=request.query_params.get("year", ""))
        if request.query_params.get("department"):
            qs = qs.filter(department__code=request.query_params["department"])
        return Response([draft_json(d) for d in qs])

    def post(self, request):
        d = request.data
        with transaction.atomic():
            y = open_year(d.get("year", ""), lock=True)
            dept = get_or_404(Department.objects.filter(active=True), code=d.get("department"))
            kra = get_or_404(KRA.objects.filter(active=True), number=d.get("kra"))
            target = clean_target(d.get("target_text"))
            tv = find_template(d["template_key"], d.get("template_version")) if d.get("template_key") else default_template(kra)
            if tv is None:
                raise err("invalid", "Choose a template for this KRA.", field_errors={"template": ["Required."]})
            if AnnualAssignment.objects.filter(department=dept, kra=kra, year=y).exists():
                raise err("conflict", f"{dept.code} KRA {kra.number} is already finalized for {y.label}.", status=409)
            existing = DraftAssignment.objects.filter(department=dept, kra=kra, year=y).first()
            if existing:
                raise err("conflict", f"A draft for {dept.code} KRA {kra.number} in {y.label} already exists; edit it instead.",
                               status=409, field_errors={"draft": [str(existing.id)]})
            draft = DraftAssignment.objects.create(department=dept, kra=kra, year=y, target_text=target, template_version=tv,
                                                   created_by=request.user)
            record(request.user, "assignment_draft.create", draft, {"year": y.label, "department": dept.code, "kra": kra.number}, request)
        return Response(draft_json(draft), status=201)


class DraftItemView(APIView):
    permission_classes = [IsVC]

    def _editable(self, pk, lock=True):
        draft = get_or_404(drafts_qs().select_for_update(of=("self",)) if lock else drafts_qs(), pk=pk)
        if draft.finalized_assignment_id:
            raise err("finalized", "This assignment is finalized; its target and template can no longer change.", status=409)
        if year_elapsed(draft.year):
            raise err("year_locked", f"{draft.year.label} has ended; drafts can no longer change.", status=409)
        return draft

    def patch(self, request, pk):
        with transaction.atomic():
            draft = self._editable(pk)
            changes = {}
            if "target_text" in request.data:
                draft.target_text = clean_target(request.data["target_text"]); changes["target_text"] = True
            if request.data.get("template_key"):
                draft.template_version = find_template(request.data["template_key"], request.data.get("template_version"))
                changes["template"] = f"{draft.template_version.key} v{draft.template_version.version}"
            draft.save()
            record(request.user, "assignment_draft.update", draft, changes, request)
        return Response(draft_json(draft))

    def delete(self, request, pk):
        with transaction.atomic():
            draft = self._editable(pk)
            record(request.user, "assignment_draft.delete", draft,
                   {"year": draft.year.label, "department": draft.department.code, "kra": draft.kra.number}, request)
            draft.delete()  # an unfinalized draft is referenced by nothing
        return Response(status=204)


class CopyYearView(APIView):
    """Copy a year's finalized assignments into drafts for a later, not-ended year. Never overwrites: existing drafts or
    finalized assignments are reported as conflicts and left unchanged."""

    permission_classes = [IsVC]

    def post(self, request, label):
        source = get_or_404(AcademicYear.objects.all(), label=request.data.get("source_year", ""))
        with transaction.atomic():
            target = open_year(label, lock=True)
            if source.label >= target.label:
                raise err("invalid", "Copy from an earlier year.", field_errors={"source_year": ["Must be before the target year."]})
            have_draft = set(DraftAssignment.objects.filter(year=target).values_list("department_id", "kra_id"))
            have_final = set(AnnualAssignment.objects.filter(year=target).values_list("department_id", "kra_id"))
            created, conflicts = 0, []
            src = AnnualAssignment.objects.filter(year=source, department__active=True, kra__active=True, template_version__isnull=False)
            for a in src.select_related("department", "kra", "template_version"):
                pair = (a.department_id, a.kra_id)
                if pair in have_final or pair in have_draft:
                    conflicts.append({"department": a.department.code, "kra": a.kra.number,
                                      "reason": "finalized" if pair in have_final else "draft exists"})
                    continue
                DraftAssignment.objects.create(department=a.department, kra=a.kra, year=target, target_text=a.target_text,
                                               template_version=a.template_version, copied_from=a, created_by=request.user)
                created += 1
            record(request.user, "assignments.copy", target, {"source_year": source.label, "created": created, "conflicts": len(conflicts)}, request)
        return Response({"year": target.label, "source_year": source.label, "created": created, "conflicts": conflicts})


class FinalizeYearView(APIView):
    """Turn every pending draft of a year into operational assignments in one transaction. The year row is locked, so a
    double click or a concurrent request waits and then finds nothing pending; expected_pending guards a stale review."""

    permission_classes = [IsVC]

    def post(self, request, label):
        expected = request.data.get("expected_pending")
        try:
            with transaction.atomic():
                y = open_year(label, lock=True)
                pending = list(drafts_qs().filter(year=y, finalized_assignment__isnull=True))
                if not pending:
                    raise err("nothing_pending", f"There are no draft assignments to finalize for {y.label}.", status=409)
                if expected != len(pending):
                    raise err("stale", f"The drafts changed since your review ({len(pending)} pending now). Review again before finalizing.",
                                   status=409)
                for d in pending:
                    a = AnnualAssignment.objects.create(department=d.department, kra=d.kra, year=y, target_text=d.target_text,
                                                        template_version=d.template_version)
                    d.finalized_assignment = a
                    d.save(update_fields=["finalized_assignment", "updated_at"])
                record(request.user, "assignments.finalize", y, {"finalized": len(pending)}, request)
        except IntegrityError:
            raise err("conflict", "An assignment for one of these department/KRA pairs already exists; nothing was finalized.", status=409)
        return Response({"year": y.label, "finalized": len(pending)})
