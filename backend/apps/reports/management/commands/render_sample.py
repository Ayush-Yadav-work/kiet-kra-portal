"""LOCAL ONLY: render synthetic KRA 33 PDFs to .work/renders/ for visual comparison (docs/validation.md).

Builds an unsaved submission in memory — nothing is written to the database.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalogue.models import AnnualAssignment, ReportingPeriod
from apps.reports.pdf import call_renderer
from apps.reports.rendering import build_context, pdf_parts, render_html
from apps.submissions.models import Submission
from tests.fixtures import kra33_payload

CASES = {
    "kra33_single": dict(events=1, rows=3),
    "kra33_multi_long": dict(events=3, rows=40, long_text=True),
    "kra33_empty": None,
}


class Command(BaseCommand):
    def handle(self, *args, **o):
        if not settings.DEBUG:
            raise CommandError("render_sample is for local development only.")
        a = AnnualAssignment.objects.select_related("department", "kra", "year", "template_version").get(
            department__code="CSE", kra__number=33, year__label="2026-27")
        period = ReportingPeriod.objects.get(year=a.year, index=2)
        out = Path(settings.PROJECT_ROOT) / ".work" / "renders"
        out.mkdir(parents=True, exist_ok=True)
        for name, spec in CASES.items():
            sub = Submission(assignment=a, period=period,
                             payload=kra33_payload(**spec) if spec else {"activities": [{}]},
                             achievement_text="Synthetic: 1 event" if spec else "")
            ctx = build_context(sub)
            (out / f"{name}.html").write_text(render_html(ctx, "preview"), encoding="utf-8")
            (out / f"{name}.pdf").write_bytes(call_renderer(pdf_parts(ctx)))
            self.stdout.write(f"wrote {out / name}.pdf")
        nil = Submission(assignment=a, period=period, is_nil=True, nil_reason="Synthetic: no alumni event this period.")
        (out / "kra33_nil.pdf").write_bytes(call_renderer(pdf_parts(build_context(nil))))
        self.stdout.write(f"wrote {out / 'kra33_nil.pdf'}")
