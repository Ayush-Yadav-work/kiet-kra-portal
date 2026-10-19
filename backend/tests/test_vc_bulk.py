"""VC Phase 2 — bulk approval (plan v2.3 §9–9.0, D-075): full manifests, 50-item processing requests, exact revisions,
idempotency, concurrent reviews, interruption/resume and per-item outcomes."""
import threading
from datetime import timedelta
from unittest import mock

from django.db import DatabaseError, connection
from django.test import TransactionTestCase, override_settings

from apps.audit.models import AuditEvent
from apps.catalogue.models import AnnualAssignment
from apps.reports.models import ApprovalArtifact
from apps.submissions import bulk as bulk_svc
from apps.submissions.models import BulkApproval, BulkApprovalItem, ReviewDecision, Submission, SubmissionRevision
from apps.submissions.services import snapshot_of
from tests.base import PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1, 10)  # 2026-27 P2 open


def make_submitted(dean, period, n, kra_from=1):
    """n Submitted reports (one revision each) in `period`, ordered by KRA then department."""
    out = []
    for a in (AnnualAssignment.objects.filter(year=period.year, kra__number__gte=kra_from)
              .select_related("department", "kra", "year", "template_version").order_by("kra__number", "department__code")[:n]):
        s = Submission.objects.create(assignment=a, period=period, status="SUBMITTED", edit_version=2, created_by=dean,
                                      achievement_text="synthetic")
        s.period = period
        rev = SubmissionRevision.objects.create(submission=s, sequence=1, payload={}, is_nil=False, achievement_text="synthetic",
                                                snapshot=snapshot_of(s), evidence_manifest=[{"id": "x"}], manifest_hash="h",
                                                submitted_by=dean, submitted_at=NOW)
        s.current_revision = rev
        s.save()
        out.append(s)
    return out


def resubmit(s, dean):
    rev = SubmissionRevision.objects.create(submission=s, sequence=2, payload={}, is_nil=False, achievement_text="newer",
                                            snapshot=s.current_revision.snapshot, evidence_manifest=[], manifest_hash="h2",
                                            submitted_by=dean, submitted_at=NOW)
    s.current_revision = rev
    s.save()


class BulkTests(PortalTestCase):
    def setUp(self):
        self.vc_c = self.client_for(self.vc)

    def prepare(self, key="k1", **body):
        return self.vc_c.post("/api/v1/bulk-approvals/", {"idempotency_key": key, **body}, format="json")

    def filtered(self, key="k1", **filters):
        return self.prepare(key, scope="filtered", filters={"year": "2026-27", "period": str(self.p2.id), **filters})

    def run_all(self, bid):
        sizes, last = [], None
        while True:
            r = self.vc_c.post(f"/api/v1/bulk-approvals/{bid}/process/")
            self.assertEqual(r.status_code, 200, r.content)
            last = r.json()
            if not last["batch"]:
                return sizes, last
            sizes.append(len(last["batch"]))
            self.assertEqual(last["processed"], sum(sizes))  # accurate progress, never "done" after the first batch

    def test_180_reports_one_confirmation_batches_50_50_50_30(self):
        with frozen(NOW):
            make_submitted(self.dean_a, self.p2, 180)
            Submission.objects.create(assignment=AnnualAssignment.objects.filter(year=self.p2.year).order_by("-kra__number").first(),
                                      period=self.p2, status="DRAFT", created_by=self.dean_a)  # drafts are never eligible
            r = self.filtered(status="APPROVED")  # the shown status filter never widens eligibility
            self.assertEqual(r.status_code, 201, r.content)
            b = r.json()
            self.assertEqual((b["total"], b["processed"], b["scope"], b["confirmed_at"]), (180, 0, "FILTERED", None))
            self.assertEqual(self.prepare("k1", scope="filtered", filters={}).json()["id"], b["id"])  # same key: same manifest
            r = self.vc_c.post(f"/api/v1/bulk-approvals/{b['id']}/process/")
            self.assertEqual(r.json()["code"], "not_confirmed")
            make_submitted(self.dean_a, self.p2, 3, kra_from=40)  # submitted after selection: never added
            self.assertEqual(self.vc_c.post(f"/api/v1/bulk-approvals/{b['id']}/confirm/").status_code, 200)
            self.assertEqual(self.vc_c.post(f"/api/v1/bulk-approvals/{b['id']}/confirm/").status_code, 200)  # double confirm: no-op
            sizes, last = self.run_all(b["id"])
        self.assertEqual(sizes, [50, 50, 50, 30])
        self.assertEqual((last["counts"]["APPROVED"], last["remaining"]), (180, 0))
        self.assertIsNotNone(last["completed_at"])
        self.assertEqual(ReviewDecision.objects.filter(decision="APPROVE").count(), 180)
        self.assertEqual(ApprovalArtifact.objects.filter(state="PENDING").count(), 180)  # durable jobs, nothing rendered
        self.assertEqual(AuditEvent.objects.filter(action="review_approve").count(), 180)  # same audit as single approval
        self.assertEqual(Submission.objects.filter(status="SUBMITTED").count(), 3)  # the later submissions stay untouched

    def test_cap_refuses_without_truncation(self):
        with frozen(NOW), override_settings(BULK_MANIFEST_CAP=10):
            make_submitted(self.dean_a, self.p2, 11)
            r = self.filtered()
            self.assertEqual((r.status_code, r.json()["code"]), (400, "too_many"))
            self.assertFalse(BulkApproval.objects.exists())
            self.assertEqual(self.filtered(department="CSE").json()["total"], 1)  # narrower filters are accepted

    def test_selection_conflicts_skips_failures_and_retry(self):
        with frozen(NOW):
            subs = make_submitted(self.dean_a, self.p2, 6)
            draft = make_submitted(self.dean_a, self.p2, 1, kra_from=45)[0]
            draft.status = "DRAFT"
            draft.save()
            items = [{"submission": str(s.id), "revision": str(s.current_revision_id)} for s in subs + [draft]]
            r = self.prepare("sel", scope="selection", items=items)
            b = r.json()
            self.assertEqual(b["total"], 6)
            self.assertEqual(b["excluded"], [{"submission": str(draft.id), "reason": "not awaiting review (draft)"}])
            self.vc_c.post(f"/api/v1/bulk-approvals/{b['id']}/confirm/")
            # after confirmation: one report approved individually, one resubmitted (newer revision), one returned to draft
            first = subs[0]
            self.vc_c.post(f"/api/v1/submissions/{first.id}/review/", {"revision": str(first.current_revision_id), "decision": "APPROVE"},
                           format="json")
            resubmit(subs[1], self.dean_a)
            real = bulk_svc.svc.review
            calls = []

            def flaky(user, sid, *a, **k):  # the 3rd report hits a database error once
                calls.append(sid)
                if sid == subs[2].id and calls.count(sid) == 1:
                    raise DatabaseError("synthetic")
                return real(user, sid, *a, **k)
            with mock.patch.object(bulk_svc.svc, "review", flaky):
                _, last = self.run_all(b["id"])
            self.assertEqual(last["counts"], {"APPROVED": 3, "SKIPPED": 1, "CONFLICT": 1, "FAILED": 1})
            res = {i["submission"]: (i["outcome"], i["reason"]) for i in
                   self.vc_c.get(f"/api/v1/bulk-approvals/{b['id']}/?page=1").json()["items"]["results"]}
            self.assertEqual(res[str(first.id)], ("SKIPPED", "No longer awaiting review (now approved)."))
            self.assertEqual(res[str(subs[1].id)][0], "CONFLICT")
            subs[1].refresh_from_db()
            self.assertEqual(subs[1].status, "SUBMITTED")  # the newer revision was never approved silently
            self.assertEqual(ReviewDecision.objects.filter(revision__submission=subs[0]).count(), 1)  # no duplicate decision
            # retry: a new manifest of the failed item only, needing its own confirmation
            r = self.vc_c.post(f"/api/v1/bulk-approvals/{b['id']}/retry/", {"idempotency_key": "retry1"}, format="json")
            rb = r.json()
            self.assertEqual((rb["total"], rb["confirmed_at"]), (1, None))
            self.vc_c.post(f"/api/v1/bulk-approvals/{rb['id']}/confirm/")
            self.assertEqual(self.run_all(rb["id"])[1]["counts"]["APPROVED"], 1)
            again = self.vc_c.post(f"/api/v1/bulk-approvals/{b['id']}/process/").json()  # repeated request after completion
            self.assertEqual((again["batch"], again["counts"]["APPROVED"]), ([], 3))

    def test_interrupt_resume_expiry_ownership_and_permissions(self):
        with frozen(NOW):
            make_submitted(self.dean_a, self.p2, 70)
            b = self.filtered().json()
            self.vc_c.post(f"/api/v1/bulk-approvals/{b['id']}/confirm/")
            first = self.vc_c.post(f"/api/v1/bulk-approvals/{b['id']}/process/").json()
            self.assertEqual((first["processed"], first["resumable"]), (50, True))
            # the browser closed; a new session (same VC) finds and resumes the run
            other = self.client_for(self.vc)
            listed = [x for x in other.get("/api/v1/bulk-approvals/").json()["results"] if x["resumable"]]
            self.assertEqual([x["id"] for x in listed], [b["id"]])
            self.assertEqual(other.post(f"/api/v1/bulk-approvals/{b['id']}/process/").json()["processed"], 70)
            dean = self.client_for(self.dean_a)
            self.assertEqual(dean.post(f"/api/v1/bulk-approvals/{b['id']}/process/").status_code, 403)
            self.assertEqual(dean.post("/api/v1/bulk-approvals/", {}, format="json").status_code, 403)
            stranger = BulkApproval.objects.create(actor=self.dean_b, idempotency_key="x", scope="FILTERED", total=0,
                                                   created_at=NOW, expires_at=NOW)
            self.assertEqual(self.vc_c.get(f"/api/v1/bulk-approvals/{stranger.id}/").status_code, 404)
            make_submitted(self.dean_a, self.p2, 2, kra_from=44)
            late = self.prepare("late", scope="filtered", filters={"year": "2026-27", "period": str(self.p2.id), "kra": "44"}).json()
        with frozen(NOW + timedelta(minutes=16)):
            r = self.vc_c.post(f"/api/v1/bulk-approvals/{late['id']}/confirm/")
            self.assertEqual(r.json()["code"], "expired")  # unconfirmed selections expire; nothing approved
        self.assertEqual(Submission.objects.filter(status="SUBMITTED").count(), 2)


class ConcurrentTabsTests(TransactionTestCase):
    """Two tabs (two connections) process the same confirmed manifest at once: every item is reviewed exactly once."""

    def test_two_tabs_never_double_approve(self):
        import io

        from django.core.management import call_command
        from apps.catalogue.models import Department, ReportingPeriod

        call_command("seed_catalogue", stdout=io.StringIO())
        vc = PortalTestCase.make_user("t.vc", "VC")
        dean = PortalTestCase.make_user("t.dean", "DEAN", Department.objects.get(code="CSE"))
        p2 = ReportingPeriod.objects.get(year__label="2026-27", index=2)
        with frozen(NOW):
            make_submitted(dean, p2, 60)
            bulk, _ = bulk_svc.prepare(vc, {"idempotency_key": "t", "scope": "filtered", "filters": {"year": "2026-27", "period": str(p2.id)}})
            bulk_svc.confirm(vc, bulk.pk)
            errors, barrier = [], threading.Barrier(2)

            def tab():
                try:
                    barrier.wait()
                    while bulk_svc.process_next(vc, bulk.pk)["batch"]:
                        pass
                except Exception as e:  # noqa: BLE001
                    errors.append(e)
                finally:
                    connection.close()
            threads = [threading.Thread(target=tab) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(errors, [])
        self.assertEqual(BulkApprovalItem.objects.filter(outcome="APPROVED").count(), 60)
        self.assertEqual(ReviewDecision.objects.count(), 60)
        self.assertEqual(ApprovalArtifact.objects.count(), 60)
