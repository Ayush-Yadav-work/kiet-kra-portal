"""LOCAL ONLY: render synthetic sample PDFs to .work/renders/<kra>/ for visual comparison (docs/validation.md).

  python manage.py render_sample            # all piloted KRAs
  python manage.py render_sample --kra 20

Builds unsaved submissions in memory — nothing is written to the database. Samples are SYNTHETIC.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalogue.models import AnnualAssignment, ReportingPeriod
from apps.reports.pdf import call_renderer
from apps.reports.rendering import build_context, pdf_parts, render_html
from apps.submissions.models import Submission
from tests import fixtures as fx

CASES = {
    33: {"normal": lambda: fx.kra33_payload(events=1, rows=3),
         "long": lambda: fx.kra33_payload(events=3, rows=40, long_text=True)},
    20: {"normal": lambda: fx.kra20_payload(rows=5),
         "long": lambda: fx.kra20_payload(rows=100, long_text=True)},
    7: {"normal": lambda: fx.kra7_payload(), "long": lambda: fx.kra7_payload(long_text=True)},
    32: {"normal": lambda: fx.kra32_payload(rows=4), "long": lambda: fx.kra32_payload(rows=100, long_text=True)},
    11: {"normal": lambda: fx.kra11_payload(courses=2, modules=4),
         "long": lambda: fx.kra11_payload(courses=6, modules=40, long_text=True)},
    1: {"normal": lambda: fx.kra13_payload(1, courses=2)},
    2: {"normal": lambda: fx.kra13_payload(2, courses=2),
        "long": lambda: fx.kra13_payload(2, courses=6, modules=40, long_text=True)},
    3: {"normal": lambda: fx.kra13_payload(3, courses=2)},
    36: {"normal": lambda: fx.kra3637_payload(36, programmes=2, participants=4)},
    37: {"normal": lambda: fx.kra3637_payload(37, programmes=2, participants=4),
         "long": lambda: fx.kra3637_payload(37, programmes=3, participants=60, modules=30, long_text=True)},
    8: {"normal": lambda: fx.kra8_10_payload(8), "long": lambda: fx.kra8_10_payload(8, long_text=True)},
    10: {"normal": lambda: fx.kra8_10_payload(10)},
    9: {"normal": lambda: fx.kra9_payload(("9a", "9b")), "only9a": lambda: fx.kra9_payload(("9a",)),
        "only9b": lambda: fx.kra9_payload(("9b",)), "long": lambda: fx.kra9_payload(("9a", "9b"), long_text=True)},
    19: {"normal": lambda: fx.kra19_payload(1, sparse_matrix=True), "multi": lambda: fx.kra19_payload(3),
         "long": lambda: fx.kra19_payload(2, matrix_rows=20, long_text=True)},
    13: {"normal": lambda: fx.kra13iab_payload(1), "multi": lambda: fx.kra13iab_payload(3, 4, 3),
         "long": lambda: fx.kra13iab_payload(2, contributions=20, meetings=20, long_text=True)},
    17: {"normal": lambda: fx.kra17_payload(3), "long": lambda: fx.kra17_payload(25, long_text=True)},
    18: {"normal": lambda: fx.kra18_payload(1, 1), "multi": lambda: fx.kra18_payload(2, 2),
         "long": lambda: fx.kra18_payload(3, 4, long_text=True)},
    23: {"normal": lambda: fx.kra23_payload(programmes=1, programs=2, modules=4),
         "long": lambda: fx.kra23_payload(programmes=3, programs=30, modules=30, long_text=True)},
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--kra", type=int, action="append")

    def handle(self, *args, **o):
        if not settings.DEBUG:
            raise CommandError("render_sample is for local development only.")
        for number in o["kra"] or CASES:
            a = AnnualAssignment.objects.select_related("department", "kra", "year", "template_version").get(
                department__code="CSE", kra__number=number, year__label="2026-27")
            period = ReportingPeriod.objects.get(year=a.year, index=2)
            out = Path(settings.PROJECT_ROOT) / ".work" / "renders" / f"kra{number}"
            out.mkdir(parents=True, exist_ok=True)
            cases = {name: dict(payload=make(), achievement_text="Synthetic sample") for name, make in CASES[number].items()}
            cases["empty"] = dict(payload={"activities": [{}]})
            cases["nil"] = dict(is_nil=True, nil_reason="Synthetic: no activity this period.", achievement_text="Nil")
            for name, fields in cases.items():
                ctx = build_context(Submission(assignment=a, period=period, **fields))
                (out / f"{name}.html").write_text(render_html(ctx, "preview"), encoding="utf-8")
                (out / f"{name}.pdf").write_bytes(call_renderer(pdf_parts(ctx)))
                self.stdout.write(f"wrote {out / name}.pdf")
