"""VC analytics API and exports (Phase 1, D-074). VC-only, read-only; no review or approval writes happen here."""
import csv
import io

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsVC
from apps.audit.errors import ApiError
from apps.reports.pdf import call_renderer
from apps.reports.rendering import analytics_pdf_parts

from . import analytics


def run(request):
    f = analytics.parse(request.query_params)
    as_of = timezone.now()  # one business time for every classification in this request
    return f, analytics.dataset(f, as_of)


class AnalyticsView(APIView):
    """Aggregates cover the whole selected dataset; only the detail table is paginated. The status filter narrows the
    detail table only — headline rates never depend on it (§6.3)."""

    permission_classes = [IsVC]

    def get(self, request):
        f, d = run(request)
        rows = d.pop("details")
        start = (f["page"] - 1) * f["page_size"]
        resp = Response({**d, "details": {"total": len(rows), "page": f["page"], "page_size": f["page_size"],
                                          "results": rows[start:start + f["page_size"]]}})
        resp["Cache-Control"] = "private, no-store"
        return resp


SPREADSHEET_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def cell(v):
    """Neutralise spreadsheet formulas in user-entered text (CSV injection)."""
    s = "" if v is None else str(v)
    return "'" + s if s.startswith(SPREADSHEET_TRIGGERS) else s


class AnalyticsExportView(APIView):
    permission_classes = [IsVC]

    def get(self, request):
        fmt = request.query_params.get("kind", "pdf")  # not "format": DRF reserves it for content negotiation
        if fmt not in ("pdf", "csv"):
            raise ApiError(400, "invalid_filter", "Choose PDF or CSV.", {"kind": ["pdf or csv"]})
        f, d = run(request)
        if len(d["details"]) > analytics.MAX_EXPORT_ROWS:
            raise ApiError(400, "too_many_rows", f"More than {analytics.MAX_EXPORT_ROWS} report slots match; narrow the filters.")
        at = timezone.localtime(d["as_of"])
        name = f'KRA_analytics_{f["year"].label}_{f["scope"]}_{at:%Y%m%d-%H%M}'
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["Department", "KRA", "Activity", "Period", "Annual target", "Status", "Achievement", "Achievement source", "Nil", "Reopened"])
            for r in d["details"]:
                w.writerow([cell(r["department"]), r["kra_number"], cell(r["kra_text"]), cell(r["period"]), cell(r["target_text"]),
                            r["status_label"], cell(r["achievement_text"]), r["achievement_source"], "Yes" if r["is_nil"] else "",
                            "Yes" if r["reopened"] else ""])
            resp = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
            resp["Content-Disposition"] = f'attachment; filename="{name}.csv"'
        else:
            pdf = call_renderer(analytics_pdf_parts({**d, "generated_at": at}))
            resp = HttpResponse(pdf, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{name}.pdf"'
        resp["Cache-Control"] = "private, no-store"
        resp["X-Content-Type-Options"] = "nosniff"
        return resp
