"""Synthetic workload data for e2e/run_perf.py (Phase 6B). Runs via `manage.py shell` on the disposable <db>_perf database only.

One Dean per department (the demo CSE/ECE Deans plus perf Deans for the other 11), and for every finalized 2026-27 assignment a
deterministic mix of statuses in P1 (closed) and P2 (open) with revisions, decisions and Drive-link evidence. P3–P6 have not
opened yet, so they hold no submissions. Long and wide reports are added for PDF checks. Nothing here is real data.
"""
import hashlib
import json
import os
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.catalogue.models import AnnualAssignment, Department, ReportingPeriod
from apps.evidence.models import Evidence
from apps.submissions.models import ReviewDecision, Submission, SubmissionRevision
from apps.submissions.services import snapshot_of
from tests import fixtures as fx

assert connection.settings_dict["NAME"].endswith("_perf"), "perf seed runs only on the disposable _perf database"
MARKER = os.environ["PERF_MARKER"]
PAYLOADS = {33: fx.kra33_payload, 20: fx.kra20_payload, 7: fx.kra7_payload, 32: fx.kra32_payload, 11: fx.kra11_payload,
            23: fx.kra23_payload, 19: fx.kra19_payload, 18: fx.kra18_payload, 17: fx.kra17_payload, 15: fx.kra15_payload,
            22: fx.kra22_payload, 31: fx.kra31_payload, 38: fx.kra38_payload, 24: fx.kra24_payload, 12: fx.kra12_payload,
            43: fx.kra43_payload, 44: fx.kra44_payload, 45: fx.kra45_payload, 21: fx.kra21_payload, 39: fx.kra39_payload,
            14: fx.kra14_payload, 16: fx.kra16_payload}

with open(os.environ["PERF_CREDENTIALS"], "a", encoding="utf-8") as out:
    for d in Department.objects.order_by("code"):
        if not User.objects.filter(role="DEAN", department=d).exists():
            password = secrets.token_urlsafe(12)
            u = User(username=f"perf.dean.{hashlib.sha1(d.code.encode()).hexdigest()[:6]}", role="DEAN", department=d,
                     first_name=f"Perf Dean {d.code}", must_change_password=False)
            u.set_password(password)
            u.save()
            out.write(f"DEAN  {u.username:16} {password}\n")

vc = User.objects.get(role="VC")
p1, p2 = (ReportingPeriod.objects.get(year__label="2026-27", index=i) for i in (1, 2))
now = timezone.now()
LONG = {("CSE", 33): lambda: fx.kra33_payload(events=3, rows=40, long_text=True),
        ("CSE", 31): lambda: fx.kra31_payload(rows=80, long_text=True)}  # wide 14-column table


def plan(i, period):
    if period == p1:
        return ["APPROVED"] * 6 + ["SUBMITTED"] * 2 + ["REJECTED", None]
    return ["DRAFT"] * 4 + ["SUBMITTED"] * 2 + ["APPROVED", "UNTOUCHED", None, None]


with transaction.atomic():
    subs, revs, decisions, evidence = [], [], [], []
    dean_of = {u.department_id: u for u in User.objects.filter(role="DEAN")}
    for i, a in enumerate(AnnualAssignment.objects.filter(year__label="2026-27").select_related(
            "department", "kra", "year", "template_version").order_by("kra__number", "department__code")):
        for period in (p1, p2):
            key = (a.department.code, a.kra.number)
            status = "SUBMITTED" if key in LONG and period == p2 else plan(i, period)[i % 10]
            if status is None:
                continue
            payload = LONG[key]() if key in LONG and period == p2 else PAYLOADS.get(a.kra.number, dict)()
            final = {"UNTOUCHED": "DRAFT"}.get(status, status)
            s = Submission(assignment=a, period=period, status=final, payload={} if status == "UNTOUCHED" else payload,
                           achievement_text="" if status == "UNTOUCHED" else (MARKER if key in LONG else f"{i % 7} activities (synthetic)"),
                           edit_version=0 if status == "UNTOUCHED" else 3, created_by=dean_of[a.department_id])
            subs.append(s)
            if final in ("SUBMITTED", "APPROVED", "REJECTED"):
                for n in range(2):
                    evidence.append(Evidence(submission=s, source_type=Evidence.Source.DRIVE_LINK, category="Other", label=f"Synthetic link {n}",
                                             drive_url="https://drive.google.com/synthetic", uploaded_by=s.created_by))
    Submission.objects.bulk_create(subs, batch_size=500)
    Evidence.objects.bulk_create(evidence, batch_size=500)
    for s in Submission.objects.filter(status__in=["SUBMITTED", "APPROVED", "REJECTED"]).select_related(
            "assignment__department", "assignment__kra", "assignment__year", "assignment__template_version", "period"):
        manifest = [{"id": str(e.id), "source_type": e.source_type, "category": e.category, "label": e.label, "original_filename": None,
                     "bytes": None, "checksum": None, "drive_url": e.drive_url, "uploaded_at": e.uploaded_at.isoformat()} for e in s.evidence.all()]
        r = SubmissionRevision(submission=s, sequence=1, payload=s.payload, is_nil=False, achievement_text=s.achievement_text,
                               snapshot=snapshot_of(s), evidence_manifest=manifest,
                               manifest_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                               submitted_by=s.created_by, submitted_at=now - timedelta(days=2))
        revs.append(r)
        s.current_revision = r
        if s.status != "SUBMITTED":
            decisions.append(ReviewDecision(revision=r, reviewer=vc, reviewer_name=vc.display_name, decision={"APPROVED": "APPROVE", "REJECTED": "REJECT"}[s.status],
                                            reason="" if s.status == "APPROVED" else "Synthetic reason", created_at=now - timedelta(days=1)))
    SubmissionRevision.objects.bulk_create(revs, batch_size=500)
    Submission.objects.bulk_update([r.submission for r in revs], ["current_revision"], batch_size=500)
    ReviewDecision.objects.bulk_create(decisions, batch_size=500)

print(json.dumps({"submissions": Submission.objects.count(), "revisions": SubmissionRevision.objects.count(),
                  "decisions": ReviewDecision.objects.count(), "evidence": Evidence.objects.count(),
                  "deans": User.objects.filter(role="DEAN").count(), "assignments": AnnualAssignment.objects.filter(year__label="2026-27").count(),
                  "periods": ReportingPeriod.objects.filter(year__label="2026-27").count()}))
