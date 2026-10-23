from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsDeanOrVC
from apps.reports import capabilities
from apps.submissions.scope import assignments_for, get_or_404

from .models import KRA, AcademicYear, Department, ReportingPeriod, TemplateVersion


def period_json(p, at=None):
    at = at or timezone.now()
    return {"id": p.id, "index": p.index, "label": p.label, "year": p.year.label, "opens_at": p.opens_at,
            "closes_at": p.closes_at, "is_open": p.is_open(at), "is_closed": at >= p.closes_at}


def kra_json(k):
    return {"number": k.number, "activity_text": k.activity_text, "nba_ref": k.nba_ref, "naac_ref": k.naac_ref}


def assignment_json(a):
    tv = a.template_version
    return {"id": str(a.id), "department": {"code": a.department.code, "name": a.department.name},
            "kra": kra_json(a.kra), "year": a.year.label, "target_text": a.target_text,
            "template": {"key": tv.key, "version": tv.version, "title": tv.title} if tv else None,
            "effective_start_period": (lambda p: p and {"index": p.index, "label": p.label})(a.effective_start_period)}


class YearsView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request):
        return Response([{"label": y.label, "start_date": y.start_date, "end_date": y.end_date}
                         for y in AcademicYear.objects.order_by("label")])


class PeriodsView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request):
        qs = ReportingPeriod.objects.select_related("year")
        if request.query_params.get("year"):
            qs = qs.filter(year__label=request.query_params["year"])
        at = timezone.now()
        return Response({"server_time": at, "results": [period_json(p, at) for p in qs]})


class DepartmentsView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request):
        qs = Department.objects.filter(active=True).order_by("code")
        if request.user.role == "DEAN":
            qs = qs.filter(pk=request.user.department_id)
        return Response([{"code": d.code, "name": d.name} for d in qs])


class KRAsView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request):
        return Response([kra_json(k) for k in KRA.objects.filter(active=True)])


class TemplateView(APIView):
    """Read-only schema, only for templates the user is assigned (VC: any)."""

    permission_classes = [IsDeanOrVC]

    def get(self, request, key, version):
        tv = get_or_404(TemplateVersion.objects.all(), key=key, version=version)
        if not assignments_for(request.user).filter(template_version=tv).exists():
            return Response({"code": "not_found", "message": "Not found."}, status=404)
        dept = request.user.department.code if request.user.department else None  # year-of-study options (D-079)
        return Response({"key": tv.key, "version": tv.version, "title": tv.title, "schema": capabilities.apply(tv.schema, dept)})
