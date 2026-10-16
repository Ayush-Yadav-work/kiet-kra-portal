"""Idempotent catalogue seed: departments, years/periods, KRAs, templates, 2026-27 assignments.

Never overwrites an assigned target: a differing seed value is reported and skipped (plan Phase 1 exit).
Contains no achievements, people or credentials.
"""
import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalogue.models import KRA, AcademicYear, AnnualAssignment, Department, ReportingPeriod, TemplateVersion
from apps.reports.families import BUILDERS
from apps.submissions.models import Submission

IST = ZoneInfo("Asia/Kolkata")
SEED = Path(settings.PROJECT_ROOT) / "seed" / "catalogue_2026-27.json"
SCHEMAS = Path(settings.BASE_DIR) / "apps" / "reports" / "schemas"
YEARS = ("2026-27", "2027-28", "2028-29")
# (start month, end month, label) — [opens, closes) at 00:00 IST (plan 2.3)
PERIODS = ((7, 9, "July – August"), (9, 11, "September – October"), (11, 1, "November – December"),
           (1, 3, "January – February"), (3, 5, "March – April"), (5, 7, "May – June"))
# KRA number -> (template key, version) available in this release.
TEMPLATE_FOR_KRA = {33: ("kra33", 1), 20: ("kra20", 1), 7: ("kra7", 1), 32: ("kra32", 1), 11: ("kra11", 1), 23: ("kra23", 1),
                    1: ("kra1", 1), 2: ("kra2", 1), 3: ("kra3", 1), 36: ("kra36", 1), 37: ("kra37", 1),
                    8: ("kra8", 1), 9: ("kra9", 1), 10: ("kra10", 1), 19: ("kra19", 1)}


def period_bounds(start_year, index):
    sm, em, label = PERIODS[index - 1]
    sy = start_year if index <= 3 else start_year + 1
    ey = sy + 1 if em < sm else sy
    opens = datetime.datetime(sy, sm, 1, tzinfo=IST)
    closes = datetime.datetime(ey, em, 1, tzinfo=IST)
    return opens, closes, f"P{index}: {label} {sy}"


class Command(BaseCommand):
    help = "Seed/refresh the reviewed KRA catalogue idempotently."

    @transaction.atomic
    def handle(self, *args, **opts):
        data = json.loads(SEED.read_text(encoding="utf-8"))
        depts = {}
        for d in data["departments"]:
            depts[d["code"]], _ = Department.objects.get_or_create(code=d["code"], defaults={"name": d["name"]})
        for label in YEARS:
            y0 = int(label[:4])
            year, _ = AcademicYear.objects.get_or_create(
                label=label, defaults={"start_date": datetime.date(y0, 7, 1), "end_date": datetime.date(y0 + 1, 6, 30)})
            for i in range(1, 7):
                opens, closes, plabel = period_bounds(y0, i)
                ReportingPeriod.objects.get_or_create(year=year, index=i, defaults={
                    "opens_at": opens, "closes_at": closes, "label": plabel})
        kras = {}
        for k in data["kras"]:
            kras[k["number"]], _ = KRA.objects.get_or_create(number=k["number"], defaults={
                "activity_text": k["activity_text"], "nba_ref": k["nba_ref"], "naac_ref": k["naac_ref"]})
        templates = {}
        for number, (key, version) in TEMPLATE_FOR_KRA.items():
            path = SCHEMAS / f"{key}_v{version}.json"
            schema = json.loads(path.read_text(encoding="utf-8")) if path.exists() else BUILDERS[key]()
            tv, created = TemplateVersion.objects.get_or_create(key=key, version=version, defaults={
                "title": schema["title"], "schema": schema,
                "renderer_template": schema.get("renderer", f"reports/{key}_v{version}.html"),
                "source_checksum": schema.get("source_checksum", "")})
            if not created and tv.schema != schema:
                if Submission.objects.filter(assignment__template_version=tv).exists():
                    self.stderr.write(f"Template {key} v{version} differs from file but is in use; versions are "
                                      f"immutable once used (plan 7) — add a new version instead. Kept the stored one.")
                else:  # not yet used by any submission: safe to refresh
                    tv.schema, tv.title = schema, schema["title"]
                    tv.save(update_fields=["schema", "title"])
            templates[number] = tv
        year = AcademicYear.objects.get(label=data["academic_year"])
        made = kept = conflicts = 0
        for code, targets in data["targets"].items():
            for number, target in targets.items():
                number = int(number)
                a, created = AnnualAssignment.objects.get_or_create(
                    department=depts[code], kra=kras[number], year=year,
                    defaults={"target_text": target, "template_version": templates.get(number)})
                if created:
                    made += 1
                    continue
                kept += 1
                if a.target_text != target:
                    conflicts += 1
                    self.stderr.write(f"{code} KRA {number}: stored target {a.target_text!r} kept "
                                      f"(seed has {target!r}); targets are fixed once assigned.")
                if a.template_version_id is None and number in templates:
                    a.template_version = templates[number]
                    a.save()
        self.stdout.write(self.style.SUCCESS(
            f"Catalogue: {len(depts)} departments, {len(kras)} KRAs, {len(YEARS)} years x 6 periods; "
            f"assignments created {made}, existing {kept}, target conflicts {conflicts}."))
